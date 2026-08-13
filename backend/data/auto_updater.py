"""
AUTO-UPDATER AGENT — Fetches latest match data from football-data.co.uk
and appends only new matches to the SQLite database.
Runs as a background scheduler (every Monday 06:00 SAST).
"""
import os
import requests
import pandas as pd
from datetime import datetime
from io import StringIO
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from .database import SessionLocal, Match, init_db
from .data_loader import CORE_COLS, DIV_MAP, _normalise

# ---------------------------------------------------------------------------
# League → football-data.co.uk URL mapping
# Season format: "2526" → URL segment "2526"
# ---------------------------------------------------------------------------
CURRENT_SEASON = "2526"
NEXT_SEASON = "2627"

LEAGUE_URLS = {
    "premier-league": f"https://www.football-data.co.uk/mmz4281/{CURRENT_SEASON}/E0.csv",
    "la-liga":        f"https://www.football-data.co.uk/mmz4281/{CURRENT_SEASON}/SP1.csv",
    "serie-a":        f"https://www.football-data.co.uk/mmz4281/{CURRENT_SEASON}/I1.csv",
    "ligue-1":        f"https://www.football-data.co.uk/mmz4281/{CURRENT_SEASON}/F1.csv",
    "bundesliga":     f"https://www.football-data.co.uk/mmz4281/{CURRENT_SEASON}/D1.csv",
}

NEXT_SEASON_URLS = {
    "premier-league": f"https://www.football-data.co.uk/mmz4281/{NEXT_SEASON}/E0.csv",
    "la-liga":        f"https://www.football-data.co.uk/mmz4281/{NEXT_SEASON}/SP1.csv",
    "serie-a":        f"https://www.football-data.co.uk/mmz4281/{NEXT_SEASON}/I1.csv",
    "ligue-1":        f"https://www.football-data.co.uk/mmz4281/{NEXT_SEASON}/F1.csv",
    "bundesliga":     f"https://www.football-data.co.uk/mmz4281/{NEXT_SEASON}/D1.csv",
}

HEADERS = {"User-Agent": "SoccerOracle/1.0"}


def _fetch_csv(url: str) -> pd.DataFrame:
    """Download CSV from URL, return DataFrame."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        content = response.content.decode("latin1")
        df = pd.read_csv(StringIO(content), low_memory=False)
        return df
    except Exception as e:
        print(f"[Updater] Failed to fetch {url}: {e}")
        return pd.DataFrame()


def _insert_new_matches(df: pd.DataFrame, league: str, db: Session) -> int:
    """Insert only matches not already in DB. Returns count of inserted rows."""
    inserted = 0
    for _, row in df.iterrows():
        existing = db.query(Match).filter(
            Match.league == league,
            Match.date == row["Date"],
            Match.home_team == row.get("home_team"),
            Match.away_team == row.get("away_team"),
        ).first()

        if existing:
            continue

        match = Match(
            league=league,
            season=CURRENT_SEASON,
            date=row["Date"],
            home_team=row.get("home_team"),
            away_team=row.get("away_team"),
            fthg=row.get("FTHG"),
            ftag=row.get("FTAG"),
            ftr=row.get("FTR"),
            hthg=row.get("HTHG"),
            htag=row.get("HTAG"),
            htr=row.get("HTR"),
            hs=row.get("HS"),
            as_=row.get("AS"),
            hst=row.get("HST"),
            ast=row.get("AST"),
            hc=row.get("HC"),
            ac=row.get("AC"),
            hf=row.get("HF"),
            af=row.get("AF"),
            hy=row.get("HY"),
            ay=row.get("AY"),
            hr=row.get("HR"),
            ar=row.get("AR"),
            referee=row.get("Referee"),
        )
        db.add(match)
        inserted += 1

    db.commit()
    return inserted


def run_update(next_season: bool = False) -> dict:
    """
    Main update function. Downloads current season data for all leagues
    and inserts new matches into the DB.
    Returns summary dict.
    """
    url_map = NEXT_SEASON_URLS if next_season else LEAGUE_URLS
    summary = {}

    db: Session = SessionLocal()
    try:
        for league, url in url_map.items():
            print(f"[Updater] Fetching {league} from {url}...")
            raw = _fetch_csv(url)

            if raw.empty:
                summary[league] = {"status": "error", "inserted": 0}
                continue

            # Keep only available core columns
            keep = [c for c in CORE_COLS if c in raw.columns]
            raw = raw[keep].copy()
            raw["league"] = league
            raw["season"] = CURRENT_SEASON

            df = _normalise(raw)

            # Only take rows where FTR is set (completed matches)
            df = df[df["ftr"].isin(["H", "D", "A"])].copy()

            if df.empty:
                summary[league] = {"status": "no_completed_matches", "inserted": 0}
                continue

            n = _insert_new_matches(df, league, db)
            summary[league] = {"status": "ok", "inserted": n}
            print(f"[Updater] {league}: {n} new matches inserted.")

    finally:
        db.close()

    print(f"[Updater] Update complete: {summary}")
    return summary


# ---------------------------------------------------------------------------
# Scheduler (runs every Monday 06:00 SAST = 04:00 UTC)
# ---------------------------------------------------------------------------
def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Africa/Johannesburg")
    scheduler.add_job(
        func=run_update,
        trigger=CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="weekly_data_update",
        name="Weekly football-data.co.uk update",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Auto-updater scheduled: every Monday 06:00 SAST")
    return scheduler


if __name__ == "__main__":
    print("Running manual update...")
    result = run_update()
    print(result)
