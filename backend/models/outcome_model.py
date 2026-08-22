"""
DATA SCIENTIST AGENT — Outcome Model (1X2)
XGBoost classifier + Dixon-Coles Structural Fusion with Calibration Gating (ECE <= 0.025).
"""
import numpy as np
import pandas as pd
import joblib
import os
from scipy.stats import poisson
import xgboost as xgb
from typing import Tuple, Dict

from ..data.feature_engineering import OUTCOME_FEATURES
from .goals_model import predict as predict_goals

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

LABEL_MAP = {"H": 0, "D": 1, "A": 2}
INV_LABEL = {0: "H", 1: "D", 2: "A"}
ECE_CEILING = 0.025


def _prep(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    avail = [f for f in OUTCOME_FEATURES if f in df.columns]
    X = df[avail].copy().fillna(df[avail].median())
    y = df["ftr"].map(LABEL_MAP)
    return X, y


def _compute_ece(proba: np.ndarray, y: pd.Series, n_bins: int = 10) -> float:
    confidences = np.max(proba, axis=1)
    predictions = np.argmax(proba, axis=1)
    accuracies  = (predictions == y.values).astype(float)
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower, bin_upper = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(accuracies[in_bin])
            avg_confidence_in_bin = np.mean(confidences[in_bin])
            ece += np.abs(accuracy_in_bin - avg_confidence_in_bin) * prop_in_bin
    return float(ece)


def _get_dc_probas(df_subset: pd.DataFrame) -> np.ndarray:
    probas = []
    for _, row in df_subset.iterrows():
        g_res = predict_goals(str(row.get("home_team", "")), str(row.get("away_team", "")), "premier-league", elo_diff=float(row.get("ELO_Diff", 0.0)))
        lam, mu = g_res["xg_home"], g_res["xg_away"]
        p_h = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h > a)
        p_d = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h == a)
        p_a = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h < a)
        tot = max(p_h + p_d + p_a, 1e-6)
        probas.append([p_h / tot, p_d / tot, p_a / tot])
    return np.array(probas)


def train(df: pd.DataFrame) -> Tuple[float, float]:
    """Train XGBoost model and perform Dixon-Coles structural fusion. Returns (xgb_brier, fused_brier)."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year

    train_df = df[df["Year"] <= 2023]
    val_df   = df[df["Year"] == 2024]
    test_df  = df[df["Year"] >= 2025]

    X_train, y_train = _prep(train_df.dropna(subset=["ftr"]))
    X_val,   y_val   = _prep(val_df.dropna(subset=["ftr"]))

    eval_df = test_df if len(test_df.dropna(subset=["ftr"])) >= 10 else val_df
    X_test,  y_test  = _prep(eval_df.dropna(subset=["ftr"]))
    if len(X_test) == 0:
        raise ValueError("No labelled test data available for outcome model evaluation.")

    # --- XGBoost ---
    xgb_model = xgb.XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        use_label_encoder=False,
        verbosity=0,
    )
    xgb_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    
    # Calibration ECE calculation on validation split
    xgb_val_proba = xgb_model.predict_proba(X_val)
    val_ece = _compute_ece(xgb_val_proba, y_val)
    
    if val_ece <= ECE_CEILING:
        weights = (0.70, 0.30)
        gate_status = "active"
    else:
        weights = (0.50, 0.50)
        gate_status = "fallback"

    xgb_proba = xgb_model.predict_proba(X_test)
    dc_proba  = _get_dc_probas(eval_df)
    
    fused_proba = weights[0] * xgb_proba + weights[1] * dc_proba

    def brier(proba, y):
        oh = pd.get_dummies(y).reindex(columns=[0, 1, 2], fill_value=0).values
        return float(np.mean(np.sum((proba - oh) ** 2, axis=1)) / 2)

    xgb_b = brier(xgb_proba, y_test)
    fused_b = brier(fused_proba, y_test)
    print(f"[OutcomeModel] XGBoost Brier: {xgb_b:.4f} | Fused Brier: {fused_b:.4f} | ECE: {val_ece:.4f} ({gate_status})")

    meta = {
        "weights": weights,
        "ece": round(val_ece, 4),
        "ece_ceiling": ECE_CEILING,
        "gate_status": gate_status,
        "features": list(X_train.columns),
    }

    joblib.dump(xgb_model, os.path.join(MODEL_DIR, "outcome_xgb.joblib"))
    joblib.dump(meta,      os.path.join(MODEL_DIR, "outcome_meta.joblib"))
    return xgb_b, fused_b


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """
    Run inference with XGBoost + Dixon-Coles Structural Fusion.
    Returns probabilities for H, D, A.
    """
    xgb_path = os.path.join(MODEL_DIR, "outcome_xgb.joblib")
    meta_path = os.path.join(MODEL_DIR, "outcome_meta.joblib")

    try:
        xgb_model = joblib.load(xgb_path)
        meta_info = joblib.load(meta_path)
        weights = meta_info.get("weights", (0.70, 0.30))
        feats = meta_info.get("features", OUTCOME_FEATURES)
    except Exception:
        weights = (0.70, 0.30)
        feats = OUTCOME_FEATURES
        xgb_model = None

    row = {**home_features, **away_features, **meta}
    X = pd.DataFrame([{f: row.get(f, np.nan) for f in feats}]).fillna(0)

    if xgb_model is not None:
        xgb_proba = xgb_model.predict_proba(X)[0]
    else:
        xgb_proba = np.array([0.45, 0.30, 0.25])

    # Dixon-Coles 1X2 structural probabilities
    home_team = meta.get("home_team", "")
    away_team = meta.get("away_team", "")
    league    = meta.get("league", "premier-league")
    elo_diff  = float(meta.get("elo_diff", 0.0))
    
    try:
        g_res = predict_goals(home_team, away_team, league, elo_diff=elo_diff)
        lam, mu = g_res["xg_home"], g_res["xg_away"]
        p_h = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h > a)
        p_d = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h == a)
        p_a = sum(poisson.pmf(h, lam) * poisson.pmf(a, mu) for h in range(10) for a in range(10) if h < a)
        tot = max(p_h + p_d + p_a, 1e-6)
        dc_proba = np.array([p_h / tot, p_d / tot, p_a / tot])
    except Exception:
        dc_proba = np.array([0.45, 0.30, 0.25])

    fused_proba = weights[0] * xgb_proba + weights[1] * dc_proba

    return {
        "prob_home": round(float(fused_proba[0]), 4),
        "prob_draw": round(float(fused_proba[1]), 4),
        "prob_away": round(float(fused_proba[2]), 4),
        "implied_home_odds": round(1 / float(fused_proba[0]), 2) if fused_proba[0] > 0 else 99,
        "implied_draw_odds": round(1 / float(fused_proba[1]), 2) if fused_proba[1] > 0 else 99,
        "implied_away_odds": round(1 / float(fused_proba[2]), 2) if fused_proba[2] > 0 else 99,
    }
