"""
INJURY SCRAPER — Phase 2 Data Integration
Scrapes injury and suspension data from Transfermarkt (publicly accessible).
Runs as a weekly cron (Monday 09:00 SAST) via APScheduler.

Data stored in InjuryReport table in soccer_oracle.db.
Used by model_registry.py to set home_key_out / away_key_out flags.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import difflib
import warnings
import pandas as pd
import soccerdata as sd

_FBREF_CACHE = {}
from typing import List, Dict, Optional
import time
import re

from .database import SessionLocal, InjuryReport

# ---------------------------------------------------------------------------
# Transfermarkt team page slugs for all 5 leagues
# ---------------------------------------------------------------------------
TEAM_SLUGS = {
    "premier-league": {
        "Arsenal":        "fc-arsenal/sperrenundverletzungen/verein/11",
        "Aston Villa":    "aston-villa/sperrenundverletzungen/verein/405",
        "Bournemouth":    "afc-bournemouth/sperrenundverletzungen/verein/989",
        "Brentford":      "brentford-fc/sperrenundverletzungen/verein/1148",
        "Brighton":       "brighton-hove-albion/sperrenundverletzungen/verein/1237",
        "Chelsea":        "fc-chelsea/sperrenundverletzungen/verein/631",
        "Crystal Palace": "crystal-palace/sperrenundverletzungen/verein/873",
        "Everton":        "fc-everton/sperrenundverletzungen/verein/29",
        "Fulham":         "fc-fulham/sperrenundverletzungen/verein/931",
        "Liverpool":      "fc-liverpool/sperrenundverletzungen/verein/31",
        "Man City":       "manchester-city/sperrenundverletzungen/verein/281",
        "Man Utd":        "manchester-united/sperrenundverletzungen/verein/985",
        "Newcastle":      "newcastle-united/sperrenundverletzungen/verein/762",
        "Nott'm Forest":  "nottingham-forest/sperrenundverletzungen/verein/703",
        "Tottenham":      "tottenham-hotspur/sperrenundverletzungen/verein/148",
        "West Ham":       "west-ham-united/sperrenundverletzungen/verein/379",
        "Wolves":         "wolverhampton-wanderers/sperrenundverletzungen/verein/543",
    },
    "la-liga": {
        "Real Madrid":  "real-madrid/sperrenundverletzungen/verein/418",
        "Barcelona":    "fc-barcelona/sperrenundverletzungen/verein/131",
        "Ath Madrid":   "atletico-de-madrid/sperrenundverletzungen/verein/13",
        "Ath Bilbao":   "athletic-club/sperrenundverletzungen/verein/621",
        "Sevilla":      "fc-sevilla/sperrenundverletzungen/verein/368",
        "Valencia":     "fc-valencia/sperrenundverletzungen/verein/1049",
        "Villarreal":   "villarreal-cf/sperrenundverletzungen/verein/383",
        "Sociedad":     "real-sociedad/sperrenundverletzungen/verein/681",
        "Betis":        "real-betis-balompie/sperrenundverletzungen/verein/150",
    },
    "serie-a": {
        "Inter":      "inter-mailand/sperrenundverletzungen/verein/46",
        "Milan":      "ac-mailand/sperrenundverletzungen/verein/5",
        "Juventus":   "juventus-turin/sperrenundverletzungen/verein/506",
        "Napoli":     "ssc-neapel/sperrenundverletzungen/verein/6195",
        "Roma":       "as-rom/sperrenundverletzungen/verein/12",
        "Lazio":      "lazio-rom/sperrenundverletzungen/verein/398",
        "Atalanta":   "atalanta-bergamo/sperrenundverletzungen/verein/800",
    },
    "ligue-1": {
        "Paris SG":  "paris-saint-germain/sperrenundverletzungen/verein/583",
        "Marseille": "olympique-marseille/sperrenundverletzungen/verein/244",
        "Monaco":    "as-monaco/sperrenundverletzungen/verein/162",
        "Lyon":      "olympique-lyon/sperrenundverletzungen/verein/1041",
        "Lille":     "losc-lille/sperrenundverletzungen/verein/1082",
    },
    "bundesliga": {
        "Bayern Munich": "fc-bayern-munchen/sperrenundverletzungen/verein/27",
        "Dortmund":      "borussia-dortmund/sperrenundverletzungen/verein/16",
        "Leverkusen":    "bayer-04-leverkusen/sperrenundverletzungen/verein/15",
        "RB Leipzig":    "rasenballsport-leipzig/sperrenundverletzungen/verein/23826",
        "Ein Frankfurt": "eintracht-frankfurt/sperrenundverletzungen/verein/24",
        "Wolfsburg":     "vfl-wolfsburg/sperrenundverletzungen/verein/82",
        "Freiburg":      "sc-freiburg/sperrenundverletzungen/verein/60",
    },
}

BASE_URL = "https://www.transfermarkt.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Specific positional categories for Phase 3 decoupling
FW_POSITIONS = {"Centre-Forward", "Left Winger", "Right Winger", "Second Striker"}
DF_POSITIONS = {"Centre-Back", "Left-Back", "Right-Back"}
MF_POSITIONS = {"Defensive Midfield", "Central Midfield", "Attacking Midfield", "Right Midfield", "Left Midfield"}
GK_POSITIONS = {"Goalkeeper"}

# All key positions for legacy schema support
KEY_POSITIONS = FW_POSITIONS | DF_POSITIONS | MF_POSITIONS | GK_POSITIONS

def _has_recent_starts(player_name: str, team: str, league: str) -> bool:
    """
    Check if player has started >60% of matches in the season.
    Uses FBref Starts / Team Matches Played > 0.6 as a proxy for recent starts.
    """
    if league not in _FBREF_CACHE:
        return False
        
    df = _FBREF_CACHE[league]
    
    try:
        fbref_teams = df.index.get_level_values("team").unique()
        best_team = difflib.get_close_matches(team, fbref_teams, n=1, cutoff=0.6)
        if not best_team:
            print(f"[Injury Gate] Unmatched team: {team}")
            return False
            
        fbref_team = best_team[0]
        team_df = df.xs(fbref_team, level="team")
        
        team_matches_played = team_df[("Playing Time", "MP")].max()
        if team_matches_played == 0 or pd.isna(team_matches_played):
            return False

        fbref_players = team_df.index.get_level_values("player").unique()
        best_player = difflib.get_close_matches(player_name, fbref_players, n=1, cutoff=0.8)
        
        if not best_player:
            print(f"[Injury Gate] Unmatched player: {player_name} (Team: {team})")
            return False
            
        fbref_player = best_player[0]
        player_stats = team_df.xs(fbref_player, level="player")
        
        starts = player_stats[("Starts", "Starts")].values[0]
        if pd.isna(starts):
            starts = 0
            
        ratio = starts / team_matches_played
        return ratio > 0.6
    except Exception as e:
        print(f"[Injury Gate] Error reading starts for {player_name}: {e}")
        return False


def _scrape_team_injuries(league: str, team: str, slug: str) -> List[Dict]:
    """Scrape injury list for one team from Transfermarkt."""
    url = f"{BASE_URL}/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[Injury] Failed to fetch {team}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    injuries = []

    # Transfermarkt injury table rows
    table = soup.select_one("table.items")
    if not table:
        return []

    rows = table.select("tbody tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue
        try:
            player_el = row.select_one("td.hauptlink a")
            if not player_el:
                continue
            player_name = player_el.get_text(strip=True)

            # Position is at cols[3]
            position = cols[3].get_text(strip=True) if len(cols) > 3 else ""

            # Injury type is at cols[5]
            injury_type = cols[5].get_text(strip=True) if len(cols) > 5 else ""

            # Return date is at cols[7] (or cols[6] in some tables)
            return_date_str = cols[7].get_text(strip=True) if len(cols) > 7 else (cols[6].get_text(strip=True) if len(cols) > 6 else "")
            return_date = None
            for fmt in ("%d/%m/%Y", "%b %d, %Y", "%Y-%m-%d"):
                try:
                    return_date = datetime.strptime(return_date_str, fmt).date()
                    break
                except ValueError:
                    pass

            is_gk = bool(GK_POSITIONS & {position})
            
            # Phase 3: Only flag as key if they actually play regularly
            is_key = bool(KEY_POSITIONS & {position}) and _has_recent_starts(player_name, team, league)

            injuries.append({
                "team": team,
                "league": league,
                "player_name": player_name,
                "position": position,
                "injury_type": injury_type,
                "out_from": date.today(),
                "expected_return": return_date,
                "is_key_player": is_key,
                "is_goalkeeper": is_gk,
            })
        except Exception:
            continue

    print(f"[Injury] {team}: {len(injuries)} players out")
    return injuries


def _upsert_injuries(injuries: List[Dict]):
    """Insert or update injury records in the DB."""
    db = SessionLocal()
    try:
        for inj in injuries:
            existing = db.query(InjuryReport).filter(
                InjuryReport.team == inj["team"],
                InjuryReport.player_name == inj["player_name"],
                InjuryReport.league == inj["league"],
            ).first()
            if existing:
                existing.injury_type = inj["injury_type"]
                existing.expected_return = inj.get("expected_return")
                existing.updated_at = datetime.utcnow()
            else:
                record = InjuryReport(**inj, updated_at=datetime.utcnow())
                db.add(record)
        db.commit()
        print(f"[Injury] Committed {len(injuries)} records to DB")
    except Exception as e:
        db.rollback()
        print(f"[Injury] DB error: {e}")
    finally:
        db.close()


def run_injury_scrape(leagues: Optional[List[str]] = None) -> Dict:
    """
    Scrape all teams across all leagues (or specified leagues).
    Throttles to 1 request/sec to be polite to Transfermarkt.
    """
    leagues = leagues or list(TEAM_SLUGS.keys())
    summary = {}
    total = 0
    print("[Injury] Starting weekly injury scrape...")
    for league in leagues:
        # Cache FBref playing time stats
        try:
            print(f"[Injury] Caching FBref playing time stats for {league}...")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # Using 2324 season for the live data gate as per current DB state
                df = sd.FBref(leagues=league, seasons="2324").read_player_season_stats(stat_type="playing_time")
                _FBREF_CACHE[league] = df
        except Exception as e:
            print(f"[Injury] Failed to cache FBref for {league}: {e}")

        teams = TEAM_SLUGS.get(league, {})
        league_count = 0
        for team, slug in teams.items():
            injuries = _scrape_team_injuries(league, team, slug)
            if injuries:
                _upsert_injuries(injuries)
                league_count += len(injuries)
            time.sleep(1.2)  # Polite rate limiting
        summary[league] = league_count
        total += league_count

    print(f"[Injury] Scrape complete. Total injuries: {total}")
    return summary


def get_team_injury_flags(team: str, league: str) -> Dict:
    """
    Query DB for current injuries for a team.
    Returns feature flags used by model_registry.py.
    """
    db = SessionLocal()
    try:
        today = date.today()
        injuries = db.query(InjuryReport).filter(
            InjuryReport.team == team,
            InjuryReport.league == league,
            (InjuryReport.expected_return == None) |
            (InjuryReport.expected_return >= today),
        ).all()

        any_in_league = db.query(InjuryReport).filter(InjuryReport.league == league).first()
        if not any_in_league:
            return {
                "miss_fw": False,
                "miss_df": False,
                "miss_mf": False,
                "miss_gk": False,
                "n_players_out": 0,
                "unavailable": True
            }

        has_miss_fw = any(i.is_key_player and i.position in FW_POSITIONS for i in injuries)
        has_miss_df = any(i.is_key_player and i.position in DF_POSITIONS for i in injuries)
        has_miss_mf = any(i.is_key_player and i.position in MF_POSITIONS for i in injuries)
        has_miss_gk = any(i.is_goalkeeper for i in injuries)
        n_out = len(injuries)

        return {
            "miss_fw": has_miss_fw,
            "miss_df": has_miss_df,
            "miss_mf": has_miss_mf,
            "miss_gk": has_miss_gk,
            "n_players_out": n_out,
            "unavailable": False,
        }
    finally:
        db.close()





