"""
MODEL REGISTRY — Unified predict() interface for all 5 models.
Loads pre-trained artifacts and provides a single prediction bundle.
"""
import numpy as np
import pandas as pd
import os
from typing import Dict, Optional
from datetime import datetime

from . import outcome_model, goals_model, corners_model, fouls_model, cards_model, shots_model
from ..data.feature_engineering import (
    build_features, OUTCOME_FEATURES, CORNERS_FEATURES, FOULS_FEATURES, SHOTS_FEATURES, SOT_FEATURES, CARDS_FEATURES
)
from ..data.database import SessionLocal, Match, TeamElo

# Lazy-loaded training DataFrame (rebuilt when models are retrained)
_training_df: Optional[pd.DataFrame] = None
_elo_dict: Optional[dict] = None


def _get_team_elo(team: str, league: str) -> float:
    """Fetch ELO from DB or fallback to 1500."""
    db = SessionLocal()
    try:
        record = db.query(TeamElo).filter(
            TeamElo.team == team, TeamElo.league == league
        ).first()
        return record.elo if record else 1500.0
    finally:
        db.close()


def _build_match_features(
    home_team: str,
    away_team: str,
    league: str,
    match_date: Optional[datetime] = None,
    n_recent: int = 10,
) -> Dict:
    """
    Pull recent match history for both teams from DB and compute features.
    Returns a flat feature dict for all models.
    """
    db = SessionLocal()
    try:
        # Fetch recent home team matches
        def _recent_matches(team: str):
            q = db.query(Match).filter(
                Match.league == league,
                Match.ftr.isnot(None),
                (Match.home_team == team) | (Match.away_team == team),
            ).order_by(Match.date.desc()).limit(n_recent).all()
            return q

        home_matches = _recent_matches(home_team)
        away_matches = _recent_matches(away_team)

        def _agg(matches, team, side):
            gf, ga, stf, cf, ff, hs, ast, hy, hr = [], [], [], [], [], [], [], [], []
            for m in matches:
                is_home = m.home_team == team
                if is_home:
                    gf.append(m.fthg or 0)
                    ga.append(m.ftag or 0)
                    stf.append(m.hst or 0)
                    cf.append(m.hc or 0)
                    ff.append(m.hf or 0)
                    hs.append(m.hs or 0)
                    ast.append(m.hst or 0)
                    hy.append(m.hy or 0)
                    hr.append(m.hr or 0)
                else:
                    gf.append(m.ftag or 0)
                    ga.append(m.fthg or 0)
                    stf.append(m.ast or 0)
                    cf.append(m.ac or 0)
                    ff.append(m.af or 0)
                    hs.append(m.as_ or 0)
                    ast.append(m.ast or 0)
                    hy.append(m.ay or 0)
                    hr.append(m.ar or 0)

            return {
                f"{side}_Roll_GF": float(np.mean(gf)) if gf else 1.4,
                f"{side}_Roll_GA": float(np.mean(ga)) if ga else 1.1,
                f"{side}_Roll_STF": float(np.mean(stf)) if stf else 4.5,
                f"{side}_Roll_CF": float(np.mean(cf)) if cf else 5.0,
                f"{side}_Roll_CA": float(np.mean(cf)) if cf else 4.8,
                f"{side}_Roll_FF": float(np.mean(ff)) if ff else 12.0,
                f"{side}_Roll_FA": float(np.mean(ff)) if ff else 12.0,
                f"{side}_Roll_HS": float(np.mean(hs)) if hs else 13.0,
                f"{side}_Roll_AS": float(np.mean(hs)) if hs else 11.0,
                f"{side}_Roll_HST": float(np.mean(ast)) if ast else 5.0,
                f"{side}_Roll_AST": float(np.mean(ast)) if ast else 4.0,
                f"{side}_Roll_HY": float(np.mean(hy)) if hy else 1.9,
                f"{side}_Roll_AY": float(np.mean(hy)) if hy else 2.1,
                f"{side}_Roll_HR": float(np.mean(hr)) if hr else 0.08,
                f"{side}_Roll_AR": float(np.mean(hr)) if hr else 0.10,
            }

        home_feats = _agg(home_matches, home_team, "Home")
        away_feats = _agg(away_matches, away_team, "Away")

        home_elo = _get_team_elo(home_team, league)
        away_elo = _get_team_elo(away_team, league)

        meta = {
            "Home_ELO": home_elo,
            "Away_ELO": away_elo,
            "ELO_Diff": home_elo - away_elo,
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "Home_DaysRest": 7.0,
            "Away_DaysRest": 7.0,
            "Home_TravelFatigue": 1,
            "Away_TravelFatigue": 0,
            "is_ghost_game": 0,
            "referee_regime": "Webb-Era",
            "ref_strictness": 4.5,
        }

        return home_feats, away_feats, meta

    finally:
        db.close()


def predict_match(
    home_team: str,
    away_team: str,
    league: str,
    match_date: Optional[datetime] = None,
) -> Dict:
    """
    Full prediction bundle for a single match.
    Returns outcome, goals, corners, fouls, cards, and shots market predictions.
    """
    home_feats, away_feats, meta = _build_match_features(
        home_team, away_team, league, match_date
    )

    # 1. Outcome (1X2)
    try:
        outcome = outcome_model.predict(home_feats, away_feats, meta)
    except Exception as e:
        print(f"[Registry] Outcome model error: {e}")
        outcome = {"prob_home": 0.45, "prob_draw": 0.25, "prob_away": 0.30,
                   "implied_home_odds": 2.22, "implied_draw_odds": 4.00, "implied_away_odds": 3.33}

    # 2. Goals (xG, BTTS, Over/Under)
    try:
        goals = goals_model.predict(
            home_team=home_team,
            away_team=away_team,
            league=league,
            elo_diff=meta.get("ELO_Diff", 0.0),
        )
    except Exception as e:
        print(f"[Registry] Goals model error: {e}")
        goals = {"xg_home": 1.4, "xg_away": 1.1, "prob_btts": 0.50,
                 "prob_over_2_5": 0.55, "prob_over_3_5": 0.30}

    # 3. Corners
    try:
        corners = corners_model.predict(home_feats, away_feats, meta)
    except Exception as e:
        print(f"[Registry] Corners model error: {e}")
        corners = {"exp_home_corners": 5.2, "exp_away_corners": 4.8, "exp_total_corners": 10.0,
                   "prob_corners_over_9_5": 0.55, "prob_corners_over_10_5": 0.42, "prob_corners_over_11_5": 0.30}

    # 4. Fouls
    try:
        fouls = fouls_model.predict(home_feats, away_feats, meta)
    except Exception as e:
        print(f"[Registry] Fouls model error: {e}")
        fouls = {"exp_home_fouls": 12.0, "exp_away_fouls": 12.0, "exp_total_fouls": 24.0,
                 "prob_fouls_over_20": 0.60, "prob_fouls_over_25": 0.30, "prob_fouls_over_30": 0.10}

    # 5. Cards
    try:
        cards = cards_model.predict(home_feats, away_feats, meta)
    except Exception as e:
        print(f"[Registry] Cards model error: {e}")
        cards = {"exp_total_yellows": 4.0, "exp_total_reds": 0.18, "exp_total_cards": 4.36,
                 "prob_over_3_5": 0.62, "prob_over_4_5": 0.44, "prob_over_5_5": 0.26}

    # 6. Shots & SOT
    try:
        shots = shots_model.predict(home_feats, away_feats, meta)
    except Exception as e:
        print(f"[Registry] Shots model error: {e}")
        shots = {"exp_total_shots": 24.7, "exp_total_sot": 9.3,
                 "prob_over_22_5_shots": 0.65, "prob_over_24_5_shots": 0.51, "prob_over_26_5_shots": 0.35,
                 "prob_over_7_5_sot": 0.71, "prob_over_8_5_sot": 0.58, "prob_over_9_5_sot": 0.44}

    return {
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "match_date": match_date.isoformat() if match_date else None,
        "outcome": outcome,
        "goals": goals,
        "corners": corners,
        "fouls": fouls,
        "cards": cards,
        "shots": shots,
        "meta": {
            "home_elo": meta.get("Home_ELO"),
            "away_elo": meta.get("Away_ELO"),
            "elo_diff": meta.get("ELO_Diff"),
        },
    }
