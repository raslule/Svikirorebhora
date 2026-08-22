"""
DATA LOADER AGENT — Imports historical CSVs from English_Premier_25_26 as seed data.
Handles EPL, La Liga, Serie A, Ligue 1, Bundesliga.
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session
from .database import Match, SessionLocal, init_db

# ---------------------------------------------------------------------------
# Source directory (the user's existing research data)
# ---------------------------------------------------------------------------
SOURCE_DIR = r"C:\Users\Liberty Marshall\Desktop\English_Premier_25_26"

LEAGUE_DIRS = {
    "premier-league": os.path.join(SOURCE_DIR, "epl_dataset"),
    "la-liga":        os.path.join(SOURCE_DIR, "laliga_dataset"),
    "serie-a":        os.path.join(SOURCE_DIR, "serie_a_dataset"),
    "ligue-1":        os.path.join(SOURCE_DIR, "ligue_1_dataset"),
    "bundesliga":     os.path.join(SOURCE_DIR, "bundesliga"),
}

# Div codes → League names
DIV_MAP = {
    "E0": "premier-league",
    "SP1": "la-liga",
    "I1": "serie-a",
    "F1": "ligue-1",
    "D1": "bundesliga",
}

CORE_COLS = [
    "Div", "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR",
    "Referee", "HS", "AS", "HST", "AST",
    "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR",
]


def _load_csv_dir(directory: str, league: str) -> pd.DataFrame:
    """Load all season CSVs from a league directory."""
    frames = []
    if not os.path.isdir(directory):
        print(f"[Loader] Directory not found: {directory}")
        return pd.DataFrame()

    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(directory, fname)
        try:
            df = pd.read_csv(fpath, low_memory=False, encoding="latin1")
            # Keep only available core columns
            keep = [c for c in CORE_COLS if c in df.columns]
            df = df[keep].copy()
            # Extract season from filename e.g. season-2526.csv → "2025-26"
            base = os.path.splitext(fname)[0]
            parts = base.split("-")
            season = parts[-1] if len(parts) > 1 else "unknown"
            df["season"] = season
            df["league"] = league
            frames.append(df)
        except Exception as e:
            print(f"[Loader] Error reading {fpath}: {e}")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_master_csv() -> pd.DataFrame:
    """Load the pre-merged historical_football_data.csv if it exists."""
    master = os.path.join(SOURCE_DIR, "historical_football_data.csv")
    if os.path.exists(master):
        print("[Loader] Loading master historical CSV...")
        df = pd.read_csv(master, low_memory=False, encoding="latin1")
        keep = [c for c in CORE_COLS + ["League", "Season"] if c in df.columns]
        df = df[keep].copy()
        if "League" in df.columns:
            df.rename(columns={"League": "league", "Season": "season"}, inplace=True)
        return df
    return pd.DataFrame()


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates, numeric cols, infer league from Div if missing."""
    df = df.copy()

    # Parse date
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    # League from Div if not set
    if "league" not in df.columns or df["league"].isnull().all():
        df["league"] = df["Div"].map(DIV_MAP)
    df = df.dropna(subset=["league"])

    # Numeric columns
    num_cols = ["FTHG", "FTAG", "HTHG", "HTAG", "HS", "AS", "HST", "AST",
                "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop rows missing both teams or result
    # Rename teams
    if "HomeTeam" in df.columns:
        df.rename(columns={"HomeTeam": "home_team", "AwayTeam": "away_team"}, inplace=True)

    # Convert all stat/categorical columns to lowercase to match DB/FE expectations
    rename_map = {c: c.lower() for c in num_cols + ["FTR", "HTR", "Referee", "Date"]}
    df.rename(columns=rename_map, inplace=True)

    return df.sort_values("date").reset_index(drop=True)


def load_all_historical() -> pd.DataFrame:
    """Return a clean, combined DataFrame of all historical match data."""
    # 1) Try master CSV first (fastest path)
    master = _load_master_csv()
    if not master.empty:
        df = _normalise(master)
        print(f"[Loader] Loaded {len(df):,} matches from master CSV.")
        return df

    # 2) Fall back to per-league directories
    frames = []
    for league, directory in LEAGUE_DIRS.items():
        ldf = _load_csv_dir(directory, league)
        if not ldf.empty:
            frames.append(ldf)
            print(f"[Loader] {league}: {len(ldf):,} rows")

    if not frames:
        print("[Loader] No data found!")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    df = _normalise(combined)
    print(f"[Loader] Total: {len(df):,} matches from per-league directories.")
    return df


def seed_database():
    """One-time seed of historical data into the SQLite DB."""
    init_db()
    df = load_all_historical()
    if df.empty:
        print("[Loader] Nothing to seed.")
        return

    db: Session = SessionLocal()
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        # Check for existing record
        existing = db.query(Match).filter(
            Match.league == row.get("league"),
            Match.date == row["date"],
            Match.home_team == row.get("home_team"),
            Match.away_team == row.get("away_team"),
        ).first()

        if existing:
            skipped += 1
            continue

        match = Match(
            league=row.get("league"),
            season=str(row.get("season", "")),
            date=row["date"],
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

        if inserted % 5000 == 0:
            db.commit()
            print(f"[Loader] Committed {inserted} rows...")

    db.commit()
    db.close()
    print(f"[Loader] Seeding complete. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    seed_database()
