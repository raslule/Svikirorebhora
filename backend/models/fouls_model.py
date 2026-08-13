"""
DATA SCIENTIST AGENT — Fouls Model
Ridge Linear Regression for foul prediction.
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
from sklearn.linear_model import Ridge
from typing import Dict

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

from ..data.feature_engineering import FOULS_FEATURES, build_referee_index

NUMERIC_FEATURES = FOULS_FEATURES
CATEGORICAL_FEATURES = ["referee_regime"]


def train(df: pd.DataFrame) -> Dict:
    """Train ridge regression for home and away fouls."""
    df = df.sort_values("Date").reset_index(drop=True)
    df["Year"] = pd.to_datetime(df["Date"]).dt.year
    df = df.dropna(subset=["hf", "af"]).copy()

    # Add referee strictness index
    ref_index = build_referee_index(df)
    df["ref_strictness"] = df["referee"].map(ref_index).fillna(
        df.get("hf", pd.Series()).mean() + df.get("af", pd.Series()).mean()
    )

    # Ensure regime column exists
    if "referee_regime" not in df.columns:
        df["referee_regime"] = "Webb-Era"

    num_feats = [f for f in NUMERIC_FEATURES if f in df.columns] + ["ref_strictness"]
    cat_feats = ["referee_regime"]

    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), num_feats),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_feats),
    ])

    train_df = df[df["Year"] <= 2023].dropna(subset=num_feats)
    test_df  = df[df["Year"] >= 2025].dropna(subset=num_feats)

    all_feats = num_feats + cat_feats
    results = {}

    for target, col in [("home", "hf"), ("away", "af")]:
        X_train = train_df[all_feats].fillna(0)
        y_train = train_df[col]
        X_test  = test_df[all_feats].fillna(0)
        y_test  = test_df[col]

        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("model", Ridge(alpha=5.0)),
        ])
        pipe.fit(X_train, y_train)

        preds = pipe.predict(X_test)
        mae = float(np.mean(np.abs(preds - y_test)))
        r2 = float(1 - np.sum((preds - y_test) ** 2) / np.sum((y_test - y_test.mean()) ** 2))
        print(f"[FoulsModel] {target} fouls — MAE: {mae:.3f}, R²: {r2:.3f}")

        joblib.dump(pipe, os.path.join(MODEL_DIR, f"fouls_{target}.joblib"))
        joblib.dump({"mean_fouls": float(y_train.mean()), "std_fouls": float(y_train.std())},
                    os.path.join(MODEL_DIR, f"fouls_{target}_meta.joblib"))
        results[target] = {"mae": mae, "r2": r2}

    return results


def predict(home_features: dict, away_features: dict, meta: dict) -> Dict:
    """Predict fouls for home and away teams."""
    row = {**home_features, **away_features, **meta}
    row.setdefault("referee_regime", "Webb-Era")
    row.setdefault("ref_strictness", 4.5)

    num_feats = FOULS_FEATURES + ["ref_strictness"]
    cat_feats = ["referee_regime"]
    all_feats = num_feats + cat_feats

    X = pd.DataFrame([{f: row.get(f, 0.0) for f in all_feats}])
    X[num_feats] = X[num_feats].fillna(0)

    predictions = {}
    for target in ["home", "away"]:
        try:
            pipe = joblib.load(os.path.join(MODEL_DIR, f"fouls_{target}.joblib"))
            meta_info = joblib.load(os.path.join(MODEL_DIR, f"fouls_{target}_meta.joblib"))
        except FileNotFoundError:
            predictions[f"exp_{target}_fouls"] = 12.0
            continue

        mu = max(float(pipe.predict(X)[0]), 1.0)
        predictions[f"exp_{target}_fouls"] = round(mu, 2)

    total_mu = predictions.get("exp_home_fouls", 12.0) + predictions.get("exp_away_fouls", 12.0)
    predictions["exp_total_fouls"] = round(total_mu, 2)

    # Normal approximation for over/under probabilities
    from scipy.stats import norm
    std = 5.0  # Conservative std estimate
    predictions["prob_fouls_over_20"] = round(float(1 - norm.cdf(20.5, total_mu, std)), 4)
    predictions["prob_fouls_over_25"] = round(float(1 - norm.cdf(25.5, total_mu, std)), 4)
    predictions["prob_fouls_over_30"] = round(float(1 - norm.cdf(30.5, total_mu, std)), 4)

    return predictions
