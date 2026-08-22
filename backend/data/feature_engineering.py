"""
FEATURE ENGINEERING AGENT — Builds model-ready features from raw match data.
Ports and extends the notebook pipeline:
- ELO ratings per league
- 5-match rolling form (GF, GA, STF, STA) — shift(1) to prevent leakage
- Rest days + travel fatigue
- Referee strictness regime (Pre-Respect, Respect-Campaign, Webb-Era)
- Ghost-game flag (COVID empty stadiums)
"""
import pandas as pd
import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# ELO System (per league, K=20, home_adv=100)
# ---------------------------------------------------------------------------
def calculate_elo(df: pd.DataFrame, k: float = 20.0, home_adv: float = 100.0) -> pd.DataFrame:
    """
    Iterates chronologically and computes ELO before each match.
    Returns df with 'Home_ELO' and 'Away_ELO' columns added.
    Insight from notebook: 100 ELO diff ≈ 0.5 goal difference.
    """
    df = df.sort_values("date").reset_index(drop=True)
    teams = pd.concat([df["home_team"], df["away_team"]]).unique()
    elo_dict = {t: 1500.0 for t in teams}

    home_elos, away_elos = [], []

    for _, row in df.iterrows():
        ht, at = row["home_team"], row["away_team"]
        h_elo = elo_dict.get(ht, 1500.0)
        a_elo = elo_dict.get(at, 1500.0)

        home_elos.append(h_elo)
        away_elos.append(a_elo)

        # Expected probability with home advantage
        h_prob = 1.0 / (1.0 + 10.0 ** ((a_elo - (h_elo + home_adv)) / 400.0))

        ftr = row.get("ftr", None)
        if ftr == "H":
            h_actual = 1.0
        elif ftr == "D":
            h_actual = 0.5
        elif ftr == "A":
            h_actual = 0.0
        else:
            # Unknown result — skip update (future match)
            continue

        elo_dict[ht] = h_elo + k * (h_actual - h_prob)
        elo_dict[at] = a_elo + k * ((1.0 - h_actual) - (1.0 - h_prob))

    df["Home_ELO"] = home_elos
    df["Away_ELO"] = away_elos
    df["ELO_Diff"] = df["Home_ELO"] - df["Away_ELO"]
    return df, elo_dict


# ---------------------------------------------------------------------------
# Referee Strictness Regime (from notebook insight)
# Pre-Respect: before 2008, Respect-Campaign: 2008-2016, Webb-Era: 2017+
# ---------------------------------------------------------------------------
def add_referee_regime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    year = pd.to_datetime(df["date"]).dt.year
    conditions = [
        year < 2008,
        (year >= 2008) & (year < 2017),
        year >= 2017,
    ]
    choices = ["Pre-Respect", "Respect-Campaign", "Webb-Era"]
    df["referee_regime"] = np.select(conditions, choices, default="Webb-Era")
    return df


# ---------------------------------------------------------------------------
# Ghost Game Flag (COVID: March 2020 – May 2021)
# ---------------------------------------------------------------------------
def add_ghost_game_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date = pd.to_datetime(df["date"])
    df["is_ghost_game"] = (
        (date >= "2020-03-01") & (date <= "2021-05-31")
    ).astype(int)
    return df


# ---------------------------------------------------------------------------
# 5-Match Rolling Form (shift(1) prevents data leakage)
# Insight from notebook: rolling GF, GA, STF critical for XGBoost
# ---------------------------------------------------------------------------
def add_rolling_form(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)

    home_df = df[["date", "home_team", "fthg", "ftag", "hst", "ast", "hc", "ac", "hf", "af"]].copy()
    home_df.columns = ["date", "Team", "GF", "GA", "STF", "STA", "CF", "CA", "FF", "FA"]

    away_df = df[["date", "away_team", "ftag", "fthg", "ast", "hst", "ac", "hc", "af", "hf"]].copy()
    away_df.columns = ["date", "Team", "GF", "GA", "STF", "STA", "CF", "CA", "FF", "FA"]

    all_games = pd.concat([home_df, away_df]).sort_values(["Team", "date"])

    for col in ["GF", "GA", "STF", "STA", "CF", "CA", "FF", "FA"]:
        all_games[f"Roll_{col}"] = (
            all_games.groupby("Team")[col]
            .transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
        )

    roll_cols = [f"Roll_{c}" for c in ["GF", "GA", "STF", "STA", "CF", "CA", "FF", "FA"]]

    # Merge Home
    df = pd.merge(
        df,
        all_games[["date", "Team"] + roll_cols],
        left_on=["date", "home_team"],
        right_on=["date", "Team"],
        how="left",
    ).drop(columns=["Team"])
    df.rename(columns={c: f"Home_{c}" for c in roll_cols}, inplace=True)

    # Merge Away
    df = pd.merge(
        df,
        all_games[["date", "Team"] + roll_cols],
        left_on=["date", "away_team"],
        right_on=["date", "Team"],
        how="left",
    ).drop(columns=["Team"])
    df.rename(columns={c: f"Away_{c}" for c in roll_cols}, inplace=True)

    return df


# ---------------------------------------------------------------------------
# Rest Days & Travel Fatigue (from notebook insight)
# ---------------------------------------------------------------------------
def add_rest_and_fatigue(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)

    all_games = []
    for side, team_col, date_col in [("Home", "home_team", "date"), ("Away", "away_team", "date")]:
        g = df[[date_col, team_col]].copy()
        g.columns = ["date", "Team"]
        g["Side"] = side
        all_games.append(g)

    schedule = pd.concat(all_games).sort_values(["Team", "date"])
    schedule["DaysRest"] = schedule.groupby("Team")["date"].diff().dt.days.fillna(7)
    schedule["DaysRest"] = schedule["DaysRest"].clip(upper=30)

    # Merge rest days back
    home_rest = schedule[schedule["Side"] == "Home"][["date", "Team", "DaysRest"]].copy()
    away_rest = schedule[schedule["Side"] == "Away"][["date", "Team", "DaysRest"]].copy()

    df = pd.merge(df, home_rest, left_on=["date", "home_team"], right_on=["date", "Team"], how="left").drop("Team", axis=1)
    df.rename(columns={"DaysRest": "Home_DaysRest"}, inplace=True)

    df = pd.merge(df, away_rest, left_on=["date", "away_team"], right_on=["date", "Team"], how="left").drop("Team", axis=1)
    df.rename(columns={"DaysRest": "Away_DaysRest"}, inplace=True)

    # Travel fatigue: home team always plays at home (flag=1 means home advantage active)
    df["Home_TravelFatigue"] = 1
    df["Away_TravelFatigue"] = 0
    return df


# ---------------------------------------------------------------------------
# Referee Strictness Index (bookings rate per referee)
# Insight: referees with > 100 matches threshold
# ---------------------------------------------------------------------------
def build_referee_index(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df["TotalCards"] = (df.get("hy", 0) + df.get("ay", 0) + df.get("hr", 0) + df.get("ar", 0)).fillna(0)
    ref_stats = df.groupby("referee").agg(
        AvgCards=("TotalCards", "mean"),
        Matches=("TotalCards", "count"),
    )
    ref_stats = ref_stats[ref_stats["Matches"] >= 50]
    ref_index = ref_stats["AvgCards"].to_dict()
    return ref_index


# ---------------------------------------------------------------------------
# Master Feature Engineering Pipeline
# ---------------------------------------------------------------------------
def build_features(df: pd.DataFrame, existing_elo: Optional[dict] = None) -> tuple:
    """
    Full pipeline. Returns (feature_df, elo_dict).
    """
    print("[FE] Adding referee regime...")
    df = add_referee_regime(df)

    print("[FE] Adding ghost game flag...")
    df = add_ghost_game_flag(df)

    print("[FE] Adding rolling form features...")
    df = add_rolling_form(df)

    print("[FE] Adding rest days & travel fatigue...")
    df = add_rest_and_fatigue(df)

    print("[FE] Computing ELO ratings...")
    df, elo_dict = calculate_elo(df)

    return df, elo_dict


# ---------------------------------------------------------------------------
# Feature columns used by models
# ---------------------------------------------------------------------------
OUTCOME_FEATURES = [
    "Home_DaysRest", "Away_DaysRest",
    "Home_TravelFatigue", "Away_TravelFatigue",
    "Home_Roll_GF", "Home_Roll_GA", "Home_Roll_STF",
    "Away_Roll_GF", "Away_Roll_GA", "Away_Roll_STF",
    "Home_ELO", "Away_ELO", "ELO_Diff",
    "is_ghost_game",
]

CORNERS_FEATURES = [
    "Home_Roll_CF", "Home_Roll_CA",
    "Away_Roll_CF", "Away_Roll_CA",
    "Home_Roll_STF", "Away_Roll_STF",
    "Home_ELO", "Away_ELO", "ELO_Diff",
    "is_ghost_game",
]

FOULS_FEATURES = [
    "Home_Roll_FF", "Home_Roll_FA",
    "Away_Roll_FF", "Away_Roll_FA",
    "Home_DaysRest", "Away_DaysRest",
    "Home_ELO", "Away_ELO",
    "is_ghost_game",
]
