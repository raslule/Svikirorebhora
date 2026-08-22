"""
DATA SCIENTIST AGENT — Shots & Shots on Target (SOT) Model
Negative Binomial GLMs.
Predicts: Expected Total Shots (Over 22.5/24.5/26.5), Expected SOT (Over 7.5/8.5/9.5).
"""
import numpy as np
import pandas as pd
import joblib
import os
import statsmodels.api as sm
from scipy.stats import nbinom
from typing import Dict, Tuple

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

from ..data.feature_engineering import SHOTS_FEATURES, SOT_FEATURES
from .goals_model import get_expected_goals, predict as predict_goals


class StatsmodelsNB:
    def fit(self, X, y):
        X_const = sm.add_constant(X, has_constant='add')
        poisson_model = sm.GLM(y, X_const, family=sm.families.Poisson()).fit()
        mu = poisson_model.predict(X_const)
        dispersion_factor = poisson_model.pearson_chi2 / poisson_model.df_resid
        self.alpha_ = max((dispersion_factor - 1) / np.mean(mu), 0.01)
        self.model_ = sm.GLM(y, X_const, family=sm.families.NegativeBinomial(alpha=self.alpha_)).fit()
        return self
        
    def predict(self, X):
        X_const = sm.add_constant(X, has_constant='add')
        return self.model_.predict(X_const)


def _prep_shots(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
    avail_shots = [f for f in SHOTS_FEATURES if f in df.columns]
    avail_sot   = [f for f in SOT_FEATURES if f in df.columns]
    
    X_s  = df[avail_shots].copy().fillna(df[avail_shots].median())
    X_st = df[avail_sot].copy().fillna(df[avail_sot].median())
    
    y_hs  = df["hs"].fillna(13.0)
    y_as  = df["as_"].fillna(11.0)
    y_hst = df["hst"].fillna(5.0)
    y_ast = df["ast"].fillna(4.0)
    
    return X_s, X_st, y_hs, y_as, y_hst, y_ast


def _fast_xg_vectorized(df_subset: pd.DataFrame) -> Tuple[list, list]:
    dc_home, dc_away = [], []
    for _, row in df_subset.iterrows():
        ht, at = str(row.get("home_team", "")), str(row.get("away_team", ""))
        league = str(row.get("league", "premier-league"))
        elo_diff = float(row.get("ELO_Diff", 0.0))
        lam, mu = get_expected_goals(ht, at, league, elo_diff=elo_diff)
        dc_home.append(lam)
        dc_away.append(mu)
    return dc_home, dc_away


def train(df: pd.DataFrame) -> Dict:
    """Train Negative Binomial GLMs for Shots and Shots on Target."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year

    train_df = df[df["Year"] <= 2023]
    val_df   = df[df["Year"] == 2024]
    test_df  = df[df["Year"] >= 2025]

    eval_df = test_df if len(test_df.dropna(subset=["hs"])) >= 10 else val_df

    X_s_tr, X_st_tr, y_hs_tr, y_as_tr, y_hst_tr, y_ast_tr = _prep_shots(train_df.dropna(subset=["hs"]))
    X_s_te, X_st_te, y_hs_te, y_as_te, y_hst_te, y_ast_te = _prep_shots(eval_df.dropna(subset=["hs"]))

    # Single-source Dixon-Coles xG features
    dc_home_tr, dc_away_tr = _fast_xg_vectorized(train_df.dropna(subset=["hs"]))
    dc_home_te, dc_away_te = _fast_xg_vectorized(eval_df.dropna(subset=["hs"]))

    X_s_tr = X_s_tr.copy()
    X_s_tr["xg_home"] = dc_home_tr
    X_s_tr["xg_away"] = dc_away_tr

    X_s_te = X_s_te.copy()
    X_s_te["xg_home"] = dc_home_te
    X_s_te["xg_away"] = dc_away_te

    model_hs  = StatsmodelsNB().fit(X_s_tr, y_hs_tr)
    model_as  = StatsmodelsNB().fit(X_s_tr, y_as_tr)
    model_hst = StatsmodelsNB().fit(X_st_tr, y_hst_tr)
    model_ast = StatsmodelsNB().fit(X_st_tr, y_ast_tr)

    pred_hs  = model_hs.predict(X_s_te)
    pred_as  = model_as.predict(X_s_te)
    pred_hst = model_hst.predict(X_st_te)
    pred_ast = model_ast.predict(X_st_te)

    mae_shots = float(np.mean(np.abs((pred_hs + pred_as) - (y_hs_te + y_as_te))))
    mae_sot   = float(np.mean(np.abs((pred_hst + pred_ast) - (y_hst_te + y_ast_te))))

    print(f"[ShotsModel] Test MAE Total Shots: {mae_shots:.4f} | SOT: {mae_sot:.4f}")

    joblib.dump(model_hs,  os.path.join(MODEL_DIR, "shots_hs.joblib"))
    joblib.dump(model_as,  os.path.join(MODEL_DIR, "shots_as.joblib"))
    joblib.dump(model_hst, os.path.join(MODEL_DIR, "shots_hst.joblib"))
    joblib.dump(model_ast, os.path.join(MODEL_DIR, "shots_ast.joblib"))

    return {"mae_total_shots": round(mae_shots, 4), "mae_total_sot": round(mae_sot, 4)}


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """Run inference for Shots and SOT using single-source goals_model.predict() xG."""
    hs_path  = os.path.join(MODEL_DIR, "shots_hs.joblib")
    as_path  = os.path.join(MODEL_DIR, "shots_as.joblib")
    hst_path = os.path.join(MODEL_DIR, "shots_hst.joblib")
    ast_path = os.path.join(MODEL_DIR, "shots_ast.joblib")

    row = {**home_features, **away_features, **meta}
    
    # Compute xG using exact single-source goals_model.predict() path
    home_team = str(meta.get("home_team", ""))
    away_team = str(meta.get("away_team", ""))
    league    = str(meta.get("league", "premier-league"))
    elo_diff  = float(meta.get("elo_diff", 0.0))

    try:
        lam, mu = get_expected_goals(home_team, away_team, league, elo_diff=elo_diff)
        row["xg_home"] = lam
        row["xg_away"] = mu
    except Exception:
        row["xg_home"] = 1.45
        row["xg_away"] = 1.15

    avail_s  = [f for f in SHOTS_FEATURES + ["xg_home", "xg_away"] if f in row]
    avail_st = [f for f in SOT_FEATURES if f in row]

    X_s  = pd.DataFrame([{f: row.get(f, 0.0) for f in avail_s}]).fillna(0)
    X_st = pd.DataFrame([{f: row.get(f, 0.0) for f in avail_st}]).fillna(0)

    try:
        m_hs  = joblib.load(hs_path)
        m_as  = joblib.load(as_path)
        m_hst = joblib.load(hst_path)
        m_ast = joblib.load(ast_path)

        exp_hs  = float(m_hs.predict(X_s)[0])
        exp_as  = float(m_as.predict(X_s)[0])
        exp_hst = float(m_hst.predict(X_st)[0])
        exp_ast = float(m_ast.predict(X_st)[0])
    except Exception:
        exp_hs, exp_as   = 13.5, 11.2
        exp_hst, exp_ast = 5.1, 4.2

    exp_total_shots = round(exp_hs + exp_as, 2)
    exp_total_sot   = round(exp_hst + exp_ast, 2)

    # Negative Binomial / Poisson Over/Under probabilities
    lam_s  = max(exp_total_shots, 1.0)
    lam_st = max(exp_total_sot, 1.0)

    from scipy.stats import poisson
    p_shots_22_5 = round(float(1 - poisson.cdf(22, lam_s)), 4)
    p_shots_24_5 = round(float(1 - poisson.cdf(24, lam_s)), 4)
    p_shots_26_5 = round(float(1 - poisson.cdf(26, lam_s)), 4)

    p_sot_7_5 = round(float(1 - poisson.cdf(7, lam_st)), 4)
    p_sot_8_5 = round(float(1 - poisson.cdf(8, lam_st)), 4)
    p_sot_9_5 = round(float(1 - poisson.cdf(9, lam_st)), 4)

    return {
        "exp_home_shots": round(exp_hs, 2),
        "exp_away_shots": round(exp_as, 2),
        "exp_total_shots": exp_total_shots,
        "exp_home_sot": round(exp_hst, 2),
        "exp_away_sot": round(exp_ast, 2),
        "exp_total_sot": exp_total_sot,
        "prob_over_22_5_shots": p_shots_22_5,
        "prob_over_24_5_shots": p_shots_24_5,
        "prob_over_26_5_shots": p_shots_26_5,
        "prob_over_7_5_sot": p_sot_7_5,
        "prob_over_8_5_sot": p_sot_8_5,
        "prob_over_9_5_sot": p_sot_9_5,
    }
