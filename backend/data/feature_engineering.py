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
# Referee Strictness Regime (Z-score Percentile Classification)
# STRICT (top 33%), AVERAGE (middle 34%), LENIENT (bottom 33%)
# ---------------------------------------------------------------------------
def add_referee_regime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns STRICT / AVERAGE / LENIENT regime based on referee card & foul z-scores.
    Falls back to 'AVERAGE' if referee is unknown or has insufficient history.
    """
    df = df.copy()
    if "referee" not in df.columns:
        df["referee_regime"] = "AVERAGE"
        return df

    played = df[df.get("ftr", pd.Series()).notna()].copy() if "ftr" in df.columns else df.copy()
    if played.empty:
        df["referee_regime"] = "AVERAGE"
        return df

    total_cards = played.get("hy", pd.Series(0, index=played.index)).fillna(0) + \
                  played.get("ay", pd.Series(0, index=played.index)).fillna(0) + \
                  played.get("hr", pd.Series(0, index=played.index)).fillna(0) + \
                  played.get("ar", pd.Series(0, index=played.index)).fillna(0)
    total_fouls = played.get("hf", pd.Series(0, index=played.index)).fillna(0) + \
                  played.get("af", pd.Series(0, index=played.index)).fillna(0)

    mean_c, std_c = float(total_cards.mean()), float(total_cards.std())
    mean_f, std_f = float(total_fouls.mean()), float(total_fouls.std())

    ref_map = {}
    for ref, group in played.groupby("referee"):
        if pd.isna(ref) or len(group) <= 10:
            continue
        g_c = group.get("hy", pd.Series(0)).fillna(0) + group.get("ay", pd.Series(0)).fillna(0) + \
              group.get("hr", pd.Series(0)).fillna(0) + group.get("ar", pd.Series(0)).fillna(0)
        g_f = group.get("hf", pd.Series(0)).fillna(0) + group.get("af", pd.Series(0)).fillna(0)
        z_c = (g_c.mean() - mean_c) / std_c if std_c else 0
        z_f = (g_f.mean() - mean_f) / std_f if std_f else 0
        ref_map[ref] = float((z_c + z_f) / 2.0)

    z_vals = list(ref_map.values())
    if z_vals:
        p33 = np.percentile(z_vals, 33)
        p67 = np.percentile(z_vals, 67)
    else:
        p33, p67 = -0.5, 0.5

    regimes = []
    for ref in df["referee"]:
        z = ref_map.get(ref, 0.0)
        if z >= p67:
            regimes.append("STRICT")
        elif z <= p33:
            regimes.append("LENIENT")
        else:
            regimes.append("AVERAGE")

    df["referee_regime"] = regimes
    return df


# ---------------------------------------------------------------------------
# Referee Era (Historical Rule-Change Eras)
# Pre-Respect (<2008), Respect-Campaign (2008-2016), Webb-Era (2017+)
# ---------------------------------------------------------------------------
def add_referee_era(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "date" not in df.columns:
        df["referee_era"] = "Webb-Era"
        return df
    year = pd.to_datetime(df["date"]).dt.year
    conditions = [
        year < 2008,
        (year >= 2008) & (year < 2017),
        year >= 2017,
    ]
    choices = ["Pre-Respect", "Respect-Campaign", "Webb-Era"]
    df["referee_era"] = np.select(conditions, choices, default="Webb-Era")
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

    cols_home = ["date", "home_team", "fthg", "ftag", "hst", "ast", "hc", "ac", "hf", "af"]
    cols_away = ["date", "away_team", "ftag", "fthg", "ast", "hst", "ac", "hc", "af", "hf"]
    base_cols = ["GF", "GA", "STF", "STA", "CF", "CA", "FF", "FA"]

    if "hs" in df.columns:
        cols_home.extend(["hs", "as_"])
        cols_away.extend(["as_", "hs"])
        base_cols.extend(["HS", "AS"])

    if "hy" in df.columns:
        cols_home.extend(["hy", "ay", "hr", "ar"])
        cols_away.extend(["ay", "hy", "ar", "hr"])
        base_cols.extend(["HY", "AY", "HR", "AR"])

    home_df = df[cols_home].copy()
    home_df.columns = ["date", "Team"] + base_cols

    away_df = df[cols_away].copy()
    away_df.columns = ["date", "Team"] + base_cols

    all_games = pd.concat([home_df, away_df]).sort_values(["Team", "date"])

    for col in base_cols:
        all_games[f"Roll_{col}"] = (
            all_games.groupby("Team")[col]
            .transform(lambda x: x.shift(1).rolling(window, min_periods=1).mean())
        )

    roll_cols = [f"Roll_{c}" for c in base_cols]

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
# Master Feature Engineering Pipeline
# ---------------------------------------------------------------------------
def build_features(df: pd.DataFrame, existing_elo: Optional[dict] = None) -> tuple:
    """
    Full pipeline. Returns (feature_df, elo_dict).
    """
    print("[FE] Adding referee regime...")
    df = add_referee_regime(df)

    print("[FE] Adding referee era...")
    df = add_referee_era(df)

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

SHOTS_FEATURES = [
    "Home_Roll_HS", "Away_Roll_AS",
    "Home_Roll_HST", "Away_Roll_AST",
    "ELO_Diff",
]

SOT_FEATURES = [
    "Home_Roll_HST", "Away_Roll_AST",
    "Home_Roll_STF", "Away_Roll_STF",
    "ELO_Diff",
]

CARDS_FEATURES = [
    "Home_Roll_HY", "Away_Roll_AY",
    "Home_Roll_FF", "Away_Roll_FA",
]
