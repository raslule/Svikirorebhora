"""
DATA SCIENTIST AGENT — Fouls Model
Poisson Regression for foul prediction.
Features: rolling fouls, referee strictness index, regime, ELO.
Insight from notebook: referee strictness regimes & booking thresholds.
"""
import numpy as np
import pandas as pd
import joblib
import os
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from typing import Dict

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

from ..data.feature_engineering import FOULS_FEATURES

NUMERIC_FEATURES = FOULS_FEATURES
CATEGORICAL_FEATURES = ["referee_regime"]


def train(df: pd.DataFrame) -> Dict:
    """Train Poisson regression for home and away fouls."""
    df = df.sort_values("date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["date"]).dt.year
    df = df.dropna(subset=["hf", "af"]).copy()

    # Ensure regime column exists
    if "referee_regime" not in df.columns:
        df["referee_regime"] = "AVERAGE"

    num_feats = [f for f in NUMERIC_FEATURES if f in df.columns]
    cat_feats = ["referee_regime"]

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), num_feats),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_feats),
    ])

    train_df = df[df["Year"] <= 2023].dropna(subset=num_feats)
    test_df  = df[df["Year"] >= 2025].dropna(subset=num_feats)
    # Fall back to 2024 if current season has no settled data yet
    if len(test_df) < 10:
        test_df = df[df["Year"] == 2024].dropna(subset=num_feats)

    all_feats = num_feats + cat_feats
    results = {}

    for target, col in [("home", "hf"), ("away", "af")]:
        X_train = train_df[all_feats].fillna(0)
        y_train = train_df[col]
        X_test  = test_df[all_feats].fillna(0)
        y_test  = test_df[col]

        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("model", PoissonRegressor(alpha=1.0)),
        ])
        pipe.fit(X_train, y_train)

        preds = pipe.predict(X_test)
        mae = float(np.mean(np.abs(preds - y_test)))
        print(f"[FoulsModel] {target} fouls — MAE: {mae:.3f}")

        joblib.dump(pipe, os.path.join(MODEL_DIR, f"fouls_{target}.joblib"))
        joblib.dump({"mean_fouls": float(y_train.mean()), "std_fouls": float(y_train.std()), "features": all_feats},
                    os.path.join(MODEL_DIR, f"fouls_{target}_meta.joblib"))
        results[target] = {"mae": mae}

    return results


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """Predict fouls for home and away teams."""
    row = {**home_features, **away_features, **meta}
    row.setdefault("referee_regime", "AVERAGE")

    predictions = {}
    for target in ["home", "away"]:
        try:
            pipe = joblib.load(os.path.join(MODEL_DIR, f"fouls_{target}.joblib"))
            meta_info = joblib.load(os.path.join(MODEL_DIR, f"fouls_{target}_meta.joblib"))
            all_feats = meta_info.get("features", FOULS_FEATURES + ["referee_regime"])
        except FileNotFoundError:
            predictions[f"exp_{target}_fouls"] = 12.0
            continue

        X = pd.DataFrame([{f: row.get(f, 0.0) for f in all_feats}])
        # Fill NA for numeric feats, leaving regime intact
        num_feats = [f for f in all_feats if f != "referee_regime"]
        X[num_feats] = X[num_feats].fillna(0)
        
        mu = max(float(pipe.predict(X)[0]), 1.0)
        predictions[f"exp_{target}_fouls"] = round(mu, 2)

    total_mu = predictions.get("exp_home_fouls", 12.0) + predictions.get("exp_away_fouls", 12.0)
    predictions["exp_total_fouls"] = round(total_mu, 2)

    # Exact Poisson distribution for over/under probabilities
    from scipy.stats import poisson
    predictions["prob_fouls_over_20"] = round(float(poisson.sf(20, total_mu)), 4)
    predictions["prob_fouls_over_25"] = round(float(poisson.sf(25, total_mu)), 4)
    predictions["prob_fouls_over_30"] = round(float(poisson.sf(30, total_mu)), 4)

    return predictions
