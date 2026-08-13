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


def _dc_log_likelihood(params, data, teams, time_weights):
    n_teams = len(teams)
    att = {t: params[i] for i, t in enumerate(teams)}
    dfe = {t: params[n_teams + i] for i, t in enumerate(teams)}
    home_adv = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    ll = 0.0
    for idx, row in data.iterrows():
        ht, at = row["home_team"], row["away_team"]
        hg, ag = int(row["fthg"]), int(row["ftag"])
        w = time_weights.get(idx, 1.0)

        lam = np.exp(att.get(ht, 0) + dfe.get(at, 0) + home_adv)
        mu  = np.exp(att.get(at, 0) + dfe.get(ht, 0))
        lam = max(lam, 0.01)
        mu  = max(mu, 0.01)

        tau = _tau(hg, ag, lam, mu, rho)
        if tau <= 0:
            continue
        ll += w * (np.log(tau) + poisson.logpmf(hg, lam) + poisson.logpmf(ag, mu))

    return -ll  # Minimise


def fit_dixon_coles(df: pd.DataFrame, half_life_days: float = 365.0):
    """Fit Dixon-Coles model on historical data. Returns (att, def, home_adv, rho)."""
    df = df.dropna(subset=["fthg", "ftag", "home_team", "away_team"]).copy()
    df["fthg"] = df["fthg"].astype(int)
    df["ftag"] = df["ftag"].astype(int)

    teams = sorted(pd.concat([df["home_team"], df["away_team"]]).unique())
    n_teams = len(teams)

    # Time decay weights
    max_date = df["Date"].max()
    df["days_ago"] = (max_date - df["Date"]).dt.days
    df["time_weight"] = np.exp(-df["days_ago"] / half_life_days)
    time_weights = df["time_weight"].to_dict()

    # Initial params: [att_team0..N, def_team0..N, home_adv, rho]
    x0 = np.zeros(2 * n_teams + 2)
    x0[2 * n_teams] = 0.3    # home advantage
    x0[2 * n_teams + 1] = -0.1  # rho (small negative)

    bounds = [(None, None)] * (2 * n_teams) + [(0, 1.5), (-0.5, 0.5)]

    result = minimize(
        _dc_log_likelihood,
        x0,
        args=(df.reset_index(), teams, time_weights),
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 500, "ftol": 1e-8},
    )

    params = result.x
    att = {t: params[i] for i, t in enumerate(teams)}
    dfe = {t: params[n_teams + i] for i, t in enumerate(teams)}
    home_adv = params[2 * n_teams]
    rho = params[2 * n_teams + 1]

    print(f"[GoalsModel] Dixon-Coles fitted. Home adv={home_adv:.3f}, rho={rho:.3f}")

    artifacts = {"att": att, "def": dfe, "home_adv": home_adv, "rho": rho, "teams": teams}
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


def predict(home_team: str, away_team: str, league: str, elo_diff: float = 0.0) -> Dict:
    """Predict xG, BTTS, Over/Under from Dixon-Coles parameters."""
    try:
        arts = joblib.load(os.path.join(MODEL_DIR, "goals_dc.joblib"))
    except FileNotFoundError:
        # Fallback: ELO-based xG from notebook formula
        arts = None

    base_h = LEAGUE_HOME_BASE.get(league, 1.40)
    base_a = LEAGUE_AWAY_BASE.get(league, 1.10)

    if arts:
        att = arts["att"]
        dfe = arts["def"]
        home_adv = arts["home_adv"]
        rho = arts["rho"]
        lam = np.exp(att.get(home_team, 0) + dfe.get(away_team, 0) + home_adv)
        mu  = np.exp(att.get(away_team, 0) + dfe.get(home_team, 0))
    else:
        # ELO fallback from notebook: xG = base + ELO_diff * 0.003
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
