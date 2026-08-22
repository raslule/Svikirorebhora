"""
SOFTWARE DEVELOPER AGENT — Matches API routes.
Fixtures, results, and league standings.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import requests

from ...data.database import get_db, Match, Fixture
from ..routes.auth import get_current_user
from ...data.database import User
from ...utils.season import get_current_season, parse_season_start_year

router = APIRouter(prefix="/api/matches", tags=["matches"])

LEAGUE_CODES = {
    "premier-league": "E0",
    "la-liga": "SP1",
    "serie-a": "I1",
    "ligue-1": "F1",
    "bundesliga": "D1",
}


@router.get("/seasons")
def get_seasons(
    league: str = "premier-league",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return distinct seasons available for a given league."""
    # Query distinct seasons from matches
    results = db.query(Match.season).filter(
        Match.league == league.lower(),
        Match.season.isnot(None)
    ).distinct().all()
    
    seasons = [r[0] for r in results if r[0]]
    # Sort descending using integer parsing
    try:
        seasons.sort(key=lambda s: parse_season_start_year(s), reverse=True)
    except Exception:
        seasons.sort(reverse=True)
        
    return seasons


@router.get("/results")
def get_results(
    league: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Match).filter(Match.ftr.isnot(None))
    if league:
        q = q.filter(Match.league == league.lower())
    if season:
        if season.lower() == "current":
            season = get_current_season()
        q = q.filter(Match.season == season)
    matches = q.order_by(Match.date.desc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "date": m.date.isoformat() if m.date else None,
            "league": m.league,
            "home_team": m.home_team,
            "away_team": m.away_team,
            "fthg": m.fthg,
            "ftag": m.ftag,
            "ftr": m.ftr,
            "hc": m.hc,
            "ac": m.ac,
            "hf": m.hf,
            "af": m.af,
        }
        for m in matches
    ]


@router.get("/upcoming")
def get_upcoming_fixtures(
    league: Optional[str] = None,
    _: User = Depends(get_current_user),
):
    """
    Fetch upcoming fixtures from football-data.org free API.
    Returns list of {home_team, away_team, date, league}.
    """
    leagues_to_fetch = [league.lower()] if league else list(LEAGUE_CODES.keys())
    fixtures = []

    try:
        import pandas as pd
        from io import StringIO
        url = "https://www.football-data.co.uk/fixtures.csv"
        resp = requests.get(url, timeout=20, headers={"User-Agent": "SoccerOracle/1.0"})
        if resp.status_code == 200 and "<html" not in resp.text.lower()[:500]:
            df = pd.read_csv(StringIO(resp.content.decode("latin1")), low_memory=False)
            
            # Map Div back to league name
            div_to_league = {v: k for k, v in LEAGUE_CODES.items()}
            
            # Filter to our requested leagues
            if "Div" in df.columns:
                requested_divs = [LEAGUE_CODES[lg] for lg in leagues_to_fetch if lg in LEAGUE_CODES]
                df = df[df["Div"].isin(requested_divs)]
                
                for _, row in df.iterrows():
                    fixtures.append({
                        "league": div_to_league.get(row["Div"]),
                        "date": str(row.get("Date", "")),
                        "time": str(row.get("Time", "")),
                        "home_team": str(row.get("HomeTeam", "")),
                        "away_team": str(row.get("AwayTeam", "")),
                    })
    except Exception as e:
        print(f"[Fixtures] Error fetching fixtures.csv: {e}")

    return fixtures


@router.get("/standings")
def get_standings(
    league: str = "premier-league",
    season: str = "current",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Compute standings from match results in DB for a given season."""
    target_season = get_current_season() if season.lower() == "current" else season

    matches = db.query(Match).filter(
        Match.league == league.lower(),
        Match.season == target_season,
        Match.ftr.isnot(None),
    ).all()

    if not matches:
        # Fallback to Fixture table for pre-season
        fixtures = db.query(Fixture).filter(
            Fixture.league == league.lower(),
            Fixture.season == target_season
        ).all()
        
        if not fixtures:
            return {"status": "not_started", "standings": []}
            
        teams = set()
        for f in fixtures:
            if f.home_team: teams.add(f.home_team)
            if f.away_team: teams.add(f.away_team)
            
        standings = []
        for i, team in enumerate(sorted(teams)):
            standings.append({
                "team": team, "P": 0, "W": 0, "D": 0, "L": 0, 
                "GF": 0, "GA": 0, "GD": 0, "Pts": 0, "Pos": i + 1
            })
        return {"status": "not_started", "standings": standings}

    # Matches found, determine if season is final or live
    status = "live"
    try:
        current_year = parse_season_start_year(get_current_season())
        target_year = parse_season_start_year(target_season)
        if target_year < current_year:
            status = "final"
    except Exception:
        pass

    table = {}
    for m in matches:
        for team in [m.home_team, m.away_team]:
            if team not in table:
                table[team] = {"team": team, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 0}

        # Home team
        table[m.home_team]["P"] += 1
        table[m.home_team]["GF"] += m.fthg or 0
        table[m.home_team]["GA"] += m.ftag or 0
        # Away team
        table[m.away_team]["P"] += 1
        table[m.away_team]["GF"] += m.ftag or 0
        table[m.away_team]["GA"] += m.fthg or 0

        if m.ftr == "H":
            table[m.home_team]["W"] += 1
            table[m.home_team]["Pts"] += 3
            table[m.away_team]["L"] += 1
        elif m.ftr == "D":
            table[m.home_team]["D"] += 1
            table[m.home_team]["Pts"] += 1
            table[m.away_team]["D"] += 1
            table[m.away_team]["Pts"] += 1
        elif m.ftr == "A":
            table[m.away_team]["W"] += 1
            table[m.away_team]["Pts"] += 3
            table[m.home_team]["L"] += 1

    for team in table:
        table[team]["GD"] = table[team]["GF"] - table[team]["GA"]

    standings = sorted(table.values(), key=lambda x: (-x["Pts"], -x["GD"], -x["GF"]))
    for i, row in enumerate(standings):
        row["Pos"] = i + 1

    return {"status": status, "standings": standings}
