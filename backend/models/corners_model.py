"""
DATA SCIENTIST AGENT — Corners Model
Negative Binomial Regression (handles overdispersion better than Poisson).
Predicts: Expected Home/Away Corners, Over 9.5, Over 10.5, Over 11.5.
"""
import numpy as np
import pandas as pd
import joblib
import os
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.base import BaseEstimator, RegressorMixin
import statsmodels.api as sm
from scipy.stats import nbinom
from typing import Dict

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

from ..data.feature_engineering import CORNERS_FEATURES

class StatsmodelsNB(BaseEstimator, RegressorMixin):
    def fit(self, X, y):
        # 1. Fit Poisson to get Pearson residuals
        X_const = sm.add_constant(X, has_constant='add')
        poisson_model = sm.GLM(y, X_const, family=sm.families.Poisson()).fit()
        
        # 2. Compute alpha
        # statsmodels NB variance is mu + alpha * mu^2
        mu = poisson_model.predict(X_const)
        dispersion_factor = poisson_model.pearson_chi2 / poisson_model.df_resid
        self.alpha_ = max((dispersion_factor - 1) / np.mean(mu), 0.01)
        
        # 3. Fit NB
        self.model_ = sm.GLM(y, X_const, family=sm.families.NegativeBinomial(alpha=self.alpha_)).fit()
        return self
        
    def predict(self, X):
        X_const = sm.add_constant(X, has_constant='add')
        return self.model_.predict(X_const)

def _nb_predict_proba(mu: float, dispersion: float, k_values: list) -> dict:
    """
    Negative Binomial PMF. mu = mean, dispersion = 1/r parameter.
    P(X > threshold) from NB distribution.
    """
    r = 1.0 / max(dispersion, 0.01)
    p = r / (r + mu)
    result = {}
    for k in k_values:
        # P(X > k) = 1 - P(X <= k)
        cdf = nbinom.cdf(int(k), r, p)
        result[f"prob_over_{str(k).replace('.', '_')}"] = round(float(1 - cdf), 4)
    return result


def train(df: pd.DataFrame) -> Dict:
    """Train separate NB regressors for home and away corners."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year
    df = df.dropna(subset=["hc", "ac"]).copy()

    avail = [f for f in CORNERS_FEATURES if f in df.columns]
    train_df = df[df["Year"] <= 2023]
    test_df  = df[df["Year"] >= 2025]
    # Fall back to 2024 data if 2025 test set is too small
    if len(test_df.dropna(subset=["hc","ac"])) < 10:
        test_df = df[df["Year"] == 2024]

    X_train = train_df[avail].fillna(0)
    X_test  = test_df[avail].fillna(0)

    results = {}
    for target, col in [("home", "hc"), ("away", "ac")]:
        y_train = train_df[col]
        y_test  = test_df[col]

        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("model", StatsmodelsNB()),
        ])
        pipe.fit(X_train, y_train)

        preds = pipe.predict(X_test)
        mae = float(np.mean(np.abs(preds - y_test)))
        print(f"[CornersModel] {target} corners MAE: {mae:.3f}")

        joblib.dump(pipe, os.path.join(MODEL_DIR, f"corners_{target}.joblib"))

        # The actual dispersion (r) parameter for scipy.stats.nbinom
        # statsmodels alpha = 1 / r
        alpha = pipe.named_steps["model"].alpha_
        joblib.dump({"dispersion": alpha, "mean_corners": float(y_train.mean()), "features": avail},
                    os.path.join(MODEL_DIR, f"corners_{target}_meta.joblib"))
        results[target] = {"mae": mae}

    return results


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """Predict corners distribution."""
    row = {**home_features, **away_features, **meta}

    predictions = {}
    for target in ["home", "away"]:
        try:
            pipe = joblib.load(os.path.join(MODEL_DIR, f"corners_{target}.joblib"))
            meta_info = joblib.load(os.path.join(MODEL_DIR, f"corners_{target}_meta.joblib"))
            avail = meta_info.get("features", CORNERS_FEATURES)
        except FileNotFoundError:
            # Fallback league averages
            predictions[f"exp_{target}_corners"] = 5.2 if target == "home" else 4.8
            continue

        X = pd.DataFrame([{f: row.get(f, 0.0) for f in avail}]).fillna(0)
        mu = max(float(pipe.predict(X)[0]), 0.5)
        disp = meta_info.get("dispersion", 0.5)
        predictions[f"exp_{target}_corners"] = round(mu, 2)

        nb_probs = _nb_predict_proba(mu, disp, [9, 10, 11])
        for k_str, prob in nb_probs.items():
            predictions[f"{target}_{k_str}"] = prob

    # Combined totals
    total_mu = predictions.get("exp_home_corners", 5.2) + predictions.get("exp_away_corners", 4.8)
    predictions["exp_total_corners"] = round(total_mu, 2)

    # Use NB for combined total
    try:
        h_meta = joblib.load(os.path.join(MODEL_DIR, "corners_home_meta.joblib"))
        a_meta = joblib.load(os.path.join(MODEL_DIR, "corners_away_meta.joblib"))
        avg_disp = (h_meta.get("dispersion", 0.5) + a_meta.get("dispersion", 0.5)) / 2
        total_probs = _nb_predict_proba(total_mu, avg_disp, [9, 10, 11])
        predictions["prob_corners_over_9_5"] = total_probs.get("prob_over_9", 0.50)
        predictions["prob_corners_over_10_5"] = total_probs.get("prob_over_10", 0.40)
        predictions["prob_corners_over_11_5"] = total_probs.get("prob_over_11", 0.30)
    except Exception:
        predictions["prob_corners_over_9_5"] = 0.50
        predictions["prob_corners_over_10_5"] = 0.40
        predictions["prob_corners_over_11_5"] = 0.30

    return predictions
