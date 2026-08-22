"""
DATA SCIENTIST AGENT — Outcome Model (1X2)
XGBoost classifier + Logistic Regression ensemble.
Target: Brier score < 0.19 on 2025/26 test set.
"""
import numpy as np
import pandas as pd
import joblib
import os
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
from typing import Tuple, Dict

from ..data.feature_engineering import OUTCOME_FEATURES

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

LABEL_MAP = {"H": 0, "D": 1, "A": 2}
INV_LABEL = {0: "H", 1: "D", 2: "A"}


def _prep(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    avail = [f for f in OUTCOME_FEATURES if f in df.columns]
    X = df[avail].copy().fillna(df[avail].median())
    y = df["ftr"].map(LABEL_MAP)
    return X, y


def train(df: pd.DataFrame) -> Tuple[float, float]:
    """Train XGBoost + Logistic ensemble. Returns (xgb_brier, lr_brier)."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year

    train_df = df[df["Year"] <= 2023]
    val_df   = df[df["Year"] == 2024]
    test_df  = df[df["Year"] >= 2025]

    X_train, y_train = _prep(train_df.dropna(subset=["ftr"]))
    X_val,   y_val   = _prep(val_df.dropna(subset=["ftr"]))

    # If current season test set is empty/too small, evaluate on val set
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
    xgb_proba = xgb_model.predict_proba(X_test)

    # --- Logistic Regression (calibrated) ---
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", CalibratedClassifierCV(
            LogisticRegression(C=1.0, max_iter=1000, random_state=42),
            method="isotonic", cv=3
        )),
    ])
    lr_pipe.fit(X_train, y_train)
    lr_proba = lr_pipe.predict_proba(X_test)

    # --- Ensemble blend (60/40) ---
    blend_proba = 0.6 * xgb_proba + 0.4 * lr_proba

    def brier(proba, y):
        oh = pd.get_dummies(y).reindex(columns=[0, 1, 2], fill_value=0).values
        return float(np.mean(np.sum((proba - oh) ** 2, axis=1)) / 2)

    xgb_b = brier(xgb_proba, y_test)
    blend_b = brier(blend_proba, y_test)
    print(f"[OutcomeModel] XGBoost Brier: {xgb_b:.4f} | Ensemble Brier: {blend_b:.4f}")

    # Save
    joblib.dump(xgb_model, os.path.join(MODEL_DIR, "outcome_xgb.joblib"))
    joblib.dump(lr_pipe,   os.path.join(MODEL_DIR, "outcome_lr.joblib"))
    return xgb_b, blend_b


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """
    Run inference. Input dicts must contain feature values.
    Returns probabilities for H, D, A.
    """
    xgb_model = joblib.load(os.path.join(MODEL_DIR, "outcome_xgb.joblib"))
    lr_pipe    = joblib.load(os.path.join(MODEL_DIR, "outcome_lr.joblib"))

    row = {**home_features, **away_features, **meta}
    avail = [f for f in OUTCOME_FEATURES if f in row]
    X = pd.DataFrame([{f: row.get(f, np.nan) for f in avail}]).fillna(0)

    xgb_proba   = xgb_model.predict_proba(X)[0]
    lr_proba    = lr_pipe.predict_proba(X)[0]
    blend_proba = 0.6 * xgb_proba + 0.4 * lr_proba

    return {
        "prob_home": round(float(blend_proba[0]), 4),
        "prob_draw": round(float(blend_proba[1]), 4),
        "prob_away": round(float(blend_proba[2]), 4),
        "implied_home_odds": round(1 / float(blend_proba[0]), 2) if blend_proba[0] > 0 else 99,
        "implied_draw_odds": round(1 / float(blend_proba[1]), 2) if blend_proba[1] > 0 else 99,
        "implied_away_odds": round(1 / float(blend_proba[2]), 2) if blend_proba[2] > 0 else 99,
    }
