"""
DATA SCIENTIST AGENT — Goals Model
Dixon-Coles Bivariate Poisson with MLE (scipy L-BFGS-B).
Predicts: xG Home, xG Away, BTTS, Over 2.5, Over 3.5.
Extended from notebook's ELO → xG mapping with full attack/defense parameters.
"""
import numpy as np
import pandas as pd
import joblib
import os
from scipy.optimize import minimize
from scipy.stats import poisson
from scipy.special import gammaln
from typing import Dict, Optional

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
os.makedirs(MODEL_DIR, exist_ok=True)

# League-level home advantage baselines (from notebook EDA)
LEAGUE_HOME_BASE = {
    "premier-league": 1.40,
    "la-liga":        1.35,
    "serie-a":        1.30,
    "ligue-1":        1.32,
    "bundesliga":     1.38,
}
LEAGUE_AWAY_BASE = {
    "premier-league": 1.10,
    "la-liga":        1.05,
    "serie-a":        1.00,
    "ligue-1":        1.08,
    "bundesliga":     1.12,
}


# ---------------------------------------------------------------------------
# Dixon-Coles rho correction for low-score scorelines
# ---------------------------------------------------------------------------
def _tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    elif x == 0 and y == 1:
        return 1.0 + lam * rho
    elif x == 1 and y == 0:
        return 1.0 + mu * rho
    elif x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _dc_log_likelihood_vec(params, home_idx, away_idx, fthg, ftag, weights, n_teams):
    att = params[:n_teams]
    dfe = params[n_teams:2 * n_teams]
    home_adv = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    lam = np.exp(att[home_idx] + dfe[away_idx] + home_adv)
    mu  = np.exp(att[away_idx] + dfe[home_idx])
    lam = np.maximum(lam, 0.01)
    mu  = np.maximum(mu, 0.01)

    tau = np.ones_like(lam)
    
    m00 = (fthg == 0) & (ftag == 0)
    m01 = (fthg == 0) & (ftag == 1)
    m10 = (fthg == 1) & (ftag == 0)
    m11 = (fthg == 1) & (ftag == 1)

    tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
    tau[m01] = 1.0 + lam[m01] * rho
    tau[m10] = 1.0 + mu[m10] * rho
    tau[m11] = 1.0 - rho

    valid = tau > 0
    if not np.all(valid):
        lam = lam[valid]
        mu = mu[valid]
        tau = tau[valid]
        fthg = fthg[valid]
        ftag = ftag[valid]
        weights = weights[valid]

    log_pmf_h = fthg * np.log(lam) - lam - gammaln(fthg + 1)
    log_pmf_a = ftag * np.log(mu) - mu - gammaln(ftag + 1)

    ll = np.sum(weights * (np.log(tau) + log_pmf_h + log_pmf_a))
    return -ll


def fit_dixon_coles(df: pd.DataFrame, half_life_days: float = 365.0, cutoff_days: int = None):
    """Fit Dixon-Coles model on historical data. Returns (att, def, home_adv, rho)."""
    df = df.dropna(subset=["fthg", "ftag", "home_team", "away_team"]).copy()
    df["fthg"] = df["fthg"].astype(int)
    df["ftag"] = df["ftag"].astype(int)

    # Time decay weights
    max_date = df["date"].max()
    df["days_ago"] = (max_date - df["date"]).dt.days
    
    if cutoff_days is not None:
        df = df[df["days_ago"] <= cutoff_days].copy()
        print(f"[GoalsModel] Applied {cutoff_days}-day recency cutoff: {len(df):,} matches remain.")
    
    if df.empty:
        raise ValueError("fit_dixon_coles: DataFrame is empty after filtering.")

    df["time_weight"] = np.exp(-df["days_ago"] / half_life_days)

    teams = sorted(pd.concat([df["home_team"], df["away_team"]]).unique())
    n_teams = len(teams)
    team_map = {t: i for i, t in enumerate(teams)}

    home_idx = df["home_team"].map(team_map).values
    away_idx = df["away_team"].map(team_map).values
    fthg = df["fthg"].values
    ftag = df["ftag"].values
    weights = df["time_weight"].values

    x0 = np.zeros(2 * n_teams + 2)
    x0[2 * n_teams] = 0.3
    x0[2 * n_teams + 1] = -0.1

    bounds = [(None, None)] * (2 * n_teams) + [(0, 1.5), (-0.5, 0.5)]

    result = minimize(
        _dc_log_likelihood_vec,
        x0,
        args=(home_idx, away_idx, fthg, ftag, weights, n_teams),
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 300, "ftol": 1e-8},
    )

    params = result.x
    att = {t: params[i] for i, t in enumerate(teams)}
    dfe = {t: params[n_teams + i] for i, t in enumerate(teams)}
    home_adv = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    print(f"[GoalsModel] Dixon-Coles fitted. Home adv={home_adv:.3f}, rho={rho:.3f}")

    artifacts = {"att": att, "def": dfe, "home_adv": home_adv, "rho": rho, "teams": teams}
    global _GOALS_MODEL_CACHE
    _GOALS_MODEL_CACHE = artifacts
    joblib.dump(artifacts, os.path.join(MODEL_DIR, "goals_dc.joblib"))
    return artifacts


def _score_probs(lam: float, mu: float, rho: float, max_goals: int = 9):
    """Return P(home=h, away=a) for all h, a in [0, max_goals]."""
    probs = np.zeros((max_goals + 1, max_goals + 1))
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            tau = _tau(h, a, lam, mu, rho)
            probs[h, a] = tau * poisson.pmf(h, lam) * poisson.pmf(a, mu)
    # Normalise
    probs /= probs.sum()
    return probs


_GOALS_MODEL_CACHE = None

def _load_model_artifacts():
    global _GOALS_MODEL_CACHE
    if _GOALS_MODEL_CACHE is None:
        try:
            _GOALS_MODEL_CACHE = joblib.load(os.path.join(MODEL_DIR, "goals_dc.joblib"))
        except FileNotFoundError:
            _GOALS_MODEL_CACHE = None
    return _GOALS_MODEL_CACHE

def predict(home_team: str, away_team: str, league: str, elo_diff: float = 0.0) -> Dict:
    """Predict xG, BTTS, Over/Under from Dixon-Coles parameters."""
    arts = _load_model_artifacts()

    base_h = LEAGUE_HOME_BASE.get(league, 1.40)
    base_a = LEAGUE_AWAY_BASE.get(league, 1.10)

    if arts and (home_team in arts.get("att", {})) and (away_team in arts.get("def", {})):
        att = arts["att"]
        dfe = arts["def"]
        home_adv = arts["home_adv"]
        rho = arts["rho"]
        lam = np.exp(att[home_team] + dfe[away_team] + home_adv)
        mu  = np.exp(att[away_team] + dfe[home_team])
    else:
        # ELO fallback: xG = base + ELO_diff * 0.003
        lam = base_h + elo_diff * 0.003
        mu  = base_a - elo_diff * 0.003
        rho = -0.1

    lam = max(float(lam), 0.10)
    mu  = max(float(mu),  0.10)

    probs = _score_probs(lam, mu, rho)

    prob_btts  = float(sum(probs[h, a] for h in range(1, 10) for a in range(1, 10)))
    prob_over25 = float(sum(probs[h, a] for h in range(10) for a in range(10) if h + a > 2))
    prob_over35 = float(sum(probs[h, a] for h in range(10) for a in range(10) if h + a > 3))

    return {
        "xg_home":       round(lam, 3),
        "xg_away":       round(mu, 3),
        "prob_btts":     round(prob_btts, 4),
        "prob_over_2_5": round(prob_over25, 4),
        "prob_over_3_5": round(prob_over35, 4),
        "implied_btts_yes_odds":  round(1 / prob_btts, 2) if prob_btts > 0 else 99,
        "implied_over25_odds":    round(1 / prob_over25, 2) if prob_over25 > 0 else 99,
    }
