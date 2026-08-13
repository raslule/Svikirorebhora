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

from ...data.database import get_db, Match
from ..routes.auth import get_current_user
from ...data.database import User

router = APIRouter(prefix="/api/matches", tags=["matches"])

LEAGUE_CODES = {
    "premier-league": "E0",
    "la-liga": "SP1",
    "serie-a": "I1",
    "ligue-1": "F1",
    "bundesliga": "D1",
}


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
    # Use next season URLs from auto_updater to get fixture list
    SEASON_URLS = {
        "premier-league": "https://www.football-data.co.uk/mmz4281/2627/E0.csv",
        "la-liga":        "https://www.football-data.co.uk/mmz4281/2627/SP1.csv",
        "serie-a":        "https://www.football-data.co.uk/mmz4281/2627/I1.csv",
        "ligue-1":        "https://www.football-data.co.uk/mmz4281/2627/F1.csv",
    }

    leagues_to_fetch = [league.lower()] if league else list(SEASON_URLS.keys())
    fixtures = []

    for lg in leagues_to_fetch:
        url = SEASON_URLS.get(lg)
        if not url:
            continue
        try:
            import pandas as pd
            from io import StringIO
            resp = requests.get(url, timeout=20, headers={"User-Agent": "SoccerOracle/1.0"})
            resp.raise_for_status()
            df = pd.read_csv(StringIO(resp.content.decode("latin1")), low_memory=False)
            # Keep only rows with no FTR (upcoming)
            if "FTR" in df.columns:
                df = df[df["FTR"].isnull() | (df["FTR"] == "")]
            for _, row in df.iterrows():
                fixtures.append({
                    "league": lg,
                    "date": str(row.get("Date", "")),
                    "time": str(row.get("Time", "")),
                    "home_team": str(row.get("HomeTeam", "")),
                    "away_team": str(row.get("AwayTeam", "")),
                })
        except Exception as e:
            print(f"[Fixtures] Error for {lg}: {e}")

    return fixtures


@router.get("/standings")
def get_standings(
    league: str = "premier-league",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Compute standings from match results in DB for current season."""
    matches = db.query(Match).filter(
        Match.league == league.lower(),
        Match.season == "2526",
        Match.ftr.isnot(None),
    ).all()

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

    return standings
