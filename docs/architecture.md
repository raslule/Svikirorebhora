# System Architecture & Known Limitations

## Core Philosophy
This system uses a hybrid approach: building individual statistical models for discrete markets (1X2, Goals, Corners, Fouls) and reconciling them into a coherent single match prediction.

## Known Limitations & Tradeoffs

### 1. IPF Matrix Reconciliation Tradeoff (1X2 vs. Team Scoring Marginals)
When combining the XGBoost 1X2 model with the Dixon-Coles Poisson matrix, we use **Block Scaling** to force the Poisson matrix to exactly match the XGBoost 1X2 probabilities.
*   **The Method:** The probability matrix is divided into Home Win, Draw, and Away Win blocks. Each block is uniformly scaled by the ratio of `(XGBoost Target) / (Poisson Original)`.
*   **The Tradeoff:** This exactly preserves the 1X2 outcome target and normalizes the matrix to 1.0. However, it intentionally distorts the original team-scoring marginal distributions (i.e., the exact likelihood of scoring exactly 0, 1, 2 goals).
*   **Rationale:** We prioritize the accuracy of the 1X2 market (our most robust model) over the exact marginal distribution of the Goals market. The Dixon-Coles internal ratios (e.g., the relationship between 0-0 and 1-1 via rho) remain mathematically preserved under uniform block scaling.

### 2. Promoted Team Shrinkage
Newly promoted teams lack historical data in the top flight. The models assign an empirical promoted_prior (based on historical averages of all promoted teams) to their rolling stats and Dixon-Coles parameters, which then decays towards the league average over a full 38-game season.
*   **The Limitation:** All promoted teams are treated as statistically identical upon entry (e.g., a Playoff winner receives the same prior as a 100-point Championship winner). This leaves room for future team-specific modelling using lower-league data.


### 3. Hardcoded Calibration Gates (XGB_ECE)
In \ackend/models/goals_model.py\, the ECE safety gate relies on a hardcoded \XGB_ECE\ value to determine if the 1X2 model is well-calibrated enough to warrant a 70/30 blend weight, or if it must fall back to 50/50.
*   **The Limitation:** This \XGB_ECE\ metric is not automatically injected by the backtester. It must be manually refreshed in the code every time \acktester.py\ is re-run and the underlying feature distributions (like ELO) change. Failing to update this value risks the gate silently protecting against a threshold that no longer reflects reality.

### 4. Injury Scraper Key Player Heuristic
The injury scraper uses a dynamic `>60% starts` heuristic to explicitly categorize missing players into `Key FW`, `Key DF`, `Key MF`, and `Starting GK`. This replaces the older, overly broad positional heuristic.

### 5. Empirical Injury Impact on Models
The UI displays "Player Unavailable" and explicitly feeds these flags into the models:
*   **Goals Model (Dixon-Coles):** 
    *   `miss_fw` applies a -11.45% penalty to goals scored ($\lambda$/$\mu$).
    *   `miss_df` applies a +8.20% penalty to goals conceded ($\mu$/$\lambda$).
    *   *Note: `miss_gk` and `miss_mf` failed empirical significance checks (GK impact was highly variable by team tier but fell below N=50 when split). They are withheld pending more data.*
    *   **Limitation (Season-aggregate vs Recent Starts):** Live gate uses season-to-date starts as a proxy for rolling recent-starts; may lag genuine current form, particularly for players who've recently returned from injury or newly broken into the XI.
    *   **Calibration Monitoring:** The test-set out-of-sample subset for `miss_fw` and `miss_df` was initially too small ($N<50$) to confirm calibration shifts definitively, although they were directionally correct by construction. **Action required:** Re-evaluate subset calibration (Brier/Log-loss) explicitly on the `miss_fw` and `miss_df` matches once $N$ clears 100-150 in the holdout window.
*   **Fouls Model:** `key_out` applies a +5% multiplier to the opposing team's aggression.


### 6. Architectural Audit & Model-UI Synchronization (Aug 2026)
Following an audit triggered by UI label drift, several key architecture improvements and invariants were established:

| Area | Problem Identified | Root Cause | Solution & Architectural Guarantee |
| :--- | :--- | :--- | :--- |
| **Model-UI Label Synchronization** | Hardcoded JSX strings in React components describing model targets (e.g. stale 'Ridge' label). | UI cards decoupled from saved disk artifacts. | Created `GET /api/models/info` endpoint in `backend/api/main.py` which dynamically inspects model joblib files on disk. Frontend (`BacktestReport.jsx`) fetches artifact metadata & timestamps directly on mount. |
| **Backtest Cutoff Safety** | Empty DataFrame exception when running backtests. | Hardcoded `df['days_ago'] <= 1000` dropped pre-2023 training rows in chronological splits ($\le 2022$). | Parameterized `fit_dixon_coles(cutoff_days=None)`: backtest splits retain full historical training window ($\le 2022$); `cutoff_days` remains available as an optional parameter for a future live-fit path (not currently active - live predictions are currently served from the single backtester-trained artifact). |
| **Dixon-Coles Execution Speed** | Dixon-Coles optimization took ~20 minutes on 39.5k matches. | Unvectorized Python `itertuples()` loop in log-likelihood evaluation. | Vectorized `_dc_log_likelihood_vec` using NumPy array operations & `scipy.special.gammaln`, speeding up fits by **20x** (~35s). |
| **Optimizer Convergence Precision** | Premature stopping under loose tolerance (`ftol=1e-5`). | L-BFGS-B stopped at iteration 15 with Home Adv `0.1976`. | Permanently tightened `ftol` to **`1e-8`** in `goals_model.py`. Empirically verified that convergence flatlines identically at `1e-8` and `1e-12` (`Home Adv = 0.2018`, `Rho = -0.0694`). |


### 7. Referee Feature Streamlining & Disambiguation (Aug 2026)
Following an ablation study evaluating high-cardinality referee inputs vs team form features:

| Area | Problem / Finding | Solution & Architectural Guarantee |
| :--- | :--- | :--- |
| **Referee Name Elimination** | Raw referee name strings (high-cardinality OHE) and continuous `ref_strictness` added noise and degraded out-of-sample test MAE (Fouls MAE 4.2703 with `ref_strictness` vs 4.2059 without). | Individual referee name features and `ref_strictness` are permanently dropped from production feature sets (Variant B). |
| **Model Feature Symmetry** | Fouls and Cards models were treating referee features inconsistently across pipelines. | **Fouls Model**: Retains ONLY the coarse behavioral strictness bucket (`referee_regime`: `STRICT`, `AVERAGE`, `LENIENT`).<br>**Cards Model**: Drops ALL referee inputs entirely, relying solely on team rolling form features (`Home_Roll_HY`, `Away_Roll_AY`, etc.). |
| **`referee_regime` Disambiguation** | `feature_engineering.py`'s historical era classification (`Pre-Respect`, `Respect-Campaign`, `Webb-Era`) was overwriting `matches.referee_regime` (z-score behavioral bucket). | Disambiguated into two distinct columns:<br>- `referee_era`: Historical rule-change era (`Pre-Respect`, `Respect-Campaign`, `Webb-Era`).<br>- `referee_regime`: Z-score strictness bucket (`STRICT`, `AVERAGE`, `LENIENT`). |

