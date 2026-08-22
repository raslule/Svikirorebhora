"""
DATA SCIENTIST AGENT — Cards Model
Poisson GLMs with Referee Strictness Scaling.
Formula: Total Cards = Yellow Cards + 2 * Red Cards (European Bookmaker Convention).
Predicts: Expected Cards, Over 3.5, Over 4.5, Over 5.5.
"""
import numpy as np
import pandas as pd
import joblib
import os
import statsmodels.api as sm
from scipy.stats import poisson
from typing import Dict, Tuple

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

from ..data.feature_engineering import CARDS_FEATURES


def _prep_cards(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series, pd.Series]:
    avail = [f for f in CARDS_FEATURES if f in df.columns]
    X = df[avail].copy().fillna(df[avail].median())
    y_hy = df["hy"].fillna(1.8)
    y_ay = df["ay"].fillna(1.8)
    y_hr = df["hr"].fillna(0.1)
    y_ar = df["ar"].fillna(0.1)
    return X, y_hy, y_ay, y_hr, y_ar


def train(df: pd.DataFrame) -> Dict:
    """Train Poisson regressors for home/away yellow and red cards."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year

    train_df = df[df["Year"] <= 2023]
    val_df   = df[df["Year"] == 2024]
    test_df  = df[df["Year"] >= 2025]

    eval_df = test_df if len(test_df.dropna(subset=["hy"])) >= 10 else val_df

    X_train, y_hy_tr, y_ay_tr, y_hr_tr, y_ar_tr = _prep_cards(train_df.dropna(subset=["hy"]))
    X_test,  y_hy_te, y_ay_te, y_hr_te, y_ar_te = _prep_cards(eval_df.dropna(subset=["hy"]))

    X_train_const = sm.add_constant(X_train, has_constant='add')
    X_test_const  = sm.add_constant(X_test, has_constant='add')

    model_hy = sm.GLM(y_hy_tr, X_train_const, family=sm.families.Poisson()).fit()
    model_ay = sm.GLM(y_ay_tr, X_train_const, family=sm.families.Poisson()).fit()
    model_hr = sm.GLM(y_hr_tr, X_train_const, family=sm.families.Poisson()).fit()
    model_ar = sm.GLM(y_ar_tr, X_train_const, family=sm.families.Poisson()).fit()

    pred_hy = model_hy.predict(X_test_const)
    pred_ay = model_ay.predict(X_test_const)
    pred_hr = model_hr.predict(X_test_const)
    pred_ar = model_ar.predict(X_test_const)

    pred_total_cards = pred_hy + pred_ay + 2 * (pred_hr + pred_ar)
    actual_total_cards = y_hy_te + y_ay_te + 2 * (y_hr_te + y_ar_te)

    mae = float(np.mean(np.abs(pred_total_cards - actual_total_cards)))
    print(f"[CardsModel] Test MAE Total Cards: {mae:.4f}")

    joblib.dump(model_hy, os.path.join(MODEL_DIR, "cards_hy.joblib"))
    joblib.dump(model_ay, os.path.join(MODEL_DIR, "cards_ay.joblib"))
    joblib.dump(model_hr, os.path.join(MODEL_DIR, "cards_hr.joblib"))
    joblib.dump(model_ar, os.path.join(MODEL_DIR, "cards_ar.joblib"))

    return {"mae_total_cards": round(mae, 4)}


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """Run inference for home and away cards and compute total card probabilities."""
    hy_path = os.path.join(MODEL_DIR, "cards_hy.joblib")
    ay_path = os.path.join(MODEL_DIR, "cards_ay.joblib")
    hr_path = os.path.join(MODEL_DIR, "cards_hr.joblib")
    ar_path = os.path.join(MODEL_DIR, "cards_ar.joblib")

    row = {**home_features, **away_features, **meta}
    avail = [f for f in CARDS_FEATURES if f in row]
    X = pd.DataFrame([{f: row.get(f, 0.0) for f in avail}]).fillna(0)
    X_const = sm.add_constant(X, has_constant='add')
    if "const" not in X_const.columns:
        X_const["const"] = 1.0

    try:
        model_hy = joblib.load(hy_path)
        model_ay = joblib.load(ay_path)
        model_hr = joblib.load(hr_path)
        model_ar = joblib.load(ar_path)

        exp_hy = float(model_hy.predict(X_const)[0])
        exp_ay = float(model_ay.predict(X_const)[0])
        exp_hr = float(model_hr.predict(X_const)[0])
        exp_ar = float(model_ar.predict(X_const)[0])
    except Exception:
        exp_hy, exp_ay = 1.95, 2.10
        exp_hr, exp_ar = 0.08, 0.10

    exp_total_yellows = round(exp_hy + exp_ay, 2)
    exp_total_reds    = round(exp_hr + exp_ar, 2)
    exp_total_cards   = round(exp_hy + exp_ay + 2 * (exp_hr + exp_ar), 2)

    lam = max(exp_total_cards, 0.10)
    p_over_3_5 = round(float(1 - poisson.cdf(3, lam)), 4)
    p_over_4_5 = round(float(1 - poisson.cdf(4, lam)), 4)
    p_over_5_5 = round(float(1 - poisson.cdf(5, lam)), 4)

    return {
        "exp_home_yellows": round(exp_hy, 2),
        "exp_away_yellows": round(exp_ay, 2),
        "exp_total_yellows": exp_total_yellows,
        "exp_home_reds": round(exp_hr, 2),
        "exp_away_reds": round(exp_ar, 2),
        "exp_total_reds": exp_total_reds,
        "exp_total_cards": exp_total_cards,
        "prob_over_3_5": p_over_3_5,
        "prob_over_4_5": p_over_4_5,
        "prob_over_5_5": p_over_5_5,
    }
