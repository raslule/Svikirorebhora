"""Calibration comparison script: BEFORE vs AFTER the cutoff_days fix."""
import joblib
import numpy as np
import pandas as pd
import sqlite3
from backend.data.feature_engineering import build_features
from backend.models import goals_model

# ── Load data ──────────────────────────────────────────────────────────────
conn = sqlite3.connect("data/soccer_oracle.db")
df = pd.read_sql("SELECT * FROM matches", conn)
conn.close()

df["date"] = pd.to_datetime(df["date"])
df, elo_dict = build_features(df)
df["Year"] = df["date"].dt.year
train_df = df[df["Year"] <= 2022].copy()
test_df  = df[(df["Year"] >= 2025) & (df["fthg"].notna()) & (df["ftag"].notna())].copy()

print(f"Train rows : {len(train_df):,}")
print(f"Train range: {train_df['date'].min().date()} -> {train_df['date'].max().date()}")
print(f"Test  rows : {len(test_df):,}")
print(f"Half-life  : 365 days (fixed in fit_dixon_coles)")
print()

btts_actual = ((test_df["fthg"] >= 1) & (test_df["ftag"] >= 1)).astype(int)

# ── BEFORE: load current saved artifact ────────────────────────────────────
arts_before = joblib.load("backend/models/artifacts/goals_dc.joblib")
print(f"BEFORE — artifact teams : {len(arts_before['att'])}", flush=True)
print(f"BEFORE — home_adv={arts_before['home_adv']:.4f}, rho={arts_before['rho']:.4f}", flush=True)

btts_before = []
for _, row in test_df.iterrows():
    p = goals_model.predict(
        row["home_team"], row["away_team"],
        row.get("league", "premier-league"),
        elo_diff=row.get("ELO_Diff", 0.0)
    )
    btts_before.append(p["prob_btts"])
btts_before = np.clip(btts_before, 1e-6, 1 - 1e-6)
ll_before = float(-np.mean(
    btts_actual * np.log(btts_before) + (1 - btts_actual) * np.log(1 - btts_before)
))
# MAE on xg_home as secondary calibration check
xg_pred_before = [
    goals_model.predict(row["home_team"], row["away_team"],
                        row.get("league", "premier-league"),
                        elo_diff=row.get("ELO_Diff", 0.0))["xg_home"]
    for _, row in test_df.iterrows()
]
mae_before = float(np.mean(np.abs(test_df["fthg"].values - xg_pred_before)))
print(f"BEFORE — BTTS log-loss : {ll_before:.4f}", flush=True)
print(f"BEFORE — xG_home MAE   : {mae_before:.4f}", flush=True)
print(flush=True)

# ── AFTER: refit with no cutoff (backtester-correct behaviour) ─────────────
print("Fitting AFTER (full train_df, no cutoff_days)...", flush=True)
arts_after = goals_model.fit_dixon_coles(train_df, cutoff_days=None)
print(f"AFTER  — artifact teams : {len(arts_after['att'])}")
print(f"AFTER  — home_adv={arts_after['home_adv']:.4f}, rho={arts_after['rho']:.4f}")

btts_after = []
for _, row in test_df.iterrows():
    p = goals_model.predict(
        row["home_team"], row["away_team"],
        row.get("league", "premier-league"),
        elo_diff=row.get("ELO_Diff", 0.0)
    )
    btts_after.append(p["prob_btts"])
btts_after = np.clip(btts_after, 1e-6, 1 - 1e-6)
ll_after = float(-np.mean(
    btts_actual * np.log(btts_after) + (1 - btts_actual) * np.log(1 - btts_after)
))
xg_pred_after = [
    goals_model.predict(row["home_team"], row["away_team"],
                        row.get("league", "premier-league"),
                        elo_diff=row.get("ELO_Diff", 0.0))["xg_home"]
    for _, row in test_df.iterrows()
]
mae_after = float(np.mean(np.abs(test_df["fthg"].values - xg_pred_after)))
print(f"AFTER  — BTTS log-loss : {ll_after:.4f}")
print(f"AFTER  — xG_home MAE   : {mae_after:.4f}")
print()

# ── Summary ────────────────────────────────────────────────────────────────
print("=" * 50)
print(f"BTTS log-loss delta : {ll_after - ll_before:+.4f}  ({'better' if ll_after < ll_before else 'worse' if ll_after > ll_before else 'same'})")
print(f"xG MAE delta        : {mae_after - mae_before:+.4f}  ({'better' if mae_after < mae_before else 'worse' if mae_after > mae_before else 'same'})")
