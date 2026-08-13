# Svikirorebhora — European Soccer Prediction System

> AI-powered soccer prediction platform covering **EPL · La Liga · Serie A · Ligue 1 · Bundesliga**

[![CI](https://github.com/[YOUR-USERNAME]/Svikirorebhora/actions/workflows/ci.yml/badge.svg)](https://github.com/[YOUR-USERNAME]/Svikirorebhora/actions)

---

## 🎯 What It Predicts

| Market | Model | Metric |
|---|---|---|
| **1X2 Winner** | XGBoost + Logistic Regression Ensemble | Brier Score < 0.19 |
| **Expected Goals (xG)** | Dixon-Coles Bivariate Poisson (MLE) | MAE on goals |
| **BTTS & Over/Under** | Poisson marginals from Dixon-Coles | Log-loss |
| **Corners** | Negative Binomial Regression | MAE < 2.5 |
| **Fouls** | Ridge Linear Regression + Referee Regimes | R² |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Git**

### Run Locally

```powershell
# Clone
git clone https://github.com/[YOUR-USERNAME]/Svikirorebhora.git
cd Svikirorebhora

# Start everything (creates venv, installs deps, launches both services)
.\start.ps1
```

- 🌐 **Frontend**: http://localhost:5173
- 🔧 **API Docs**: http://localhost:8000/docs

### First Run
On first launch, the system will automatically seed the database from your historical CSV files at:
`C:\Users\Liberty Marshall\Desktop\English_Premier_25_26\`

This takes ~2-3 minutes for 45,000+ matches.

---

## 🏗️ Architecture

```
SoccerOracle/
├── backend/
│   ├── data/           # Data Engineer Agent (ETL, DB, auto-updater)
│   ├── models/         # Data Scientist Agent (5 prediction models)
│   └── api/            # Software Developer Agent (FastAPI routes)
├── frontend/           # Software Developer Agent (React + Vite)
├── tests/              # QA Agent (pytest + integration tests)
├── docs/               # CEO + PM Agent (vision, spec)
└── start.ps1           # One-command launcher
```

### Agent Org Chart
```
CEO → Product Manager → Data Engineer → Data Scientist → Software Dev → QA
```

---

## 📡 Data Sources

| Source | Data | Update |
|---|---|---|
| [football-data.co.uk](https://football-data.co.uk) | Results, corners, fouls, shots | Every Monday 06:00 SAST (auto) |
| Your local CSVs | Historical seed (2000–2026) | One-time on first run |

**No subscriptions required.** All data sources are free.

---

## 🧠 Model Insights (from EDA)

- **ELO → xG mapping**: `xG_home = 1.4 + ELO_diff × 0.003` (100 ELO pts ≈ 0.5 goal diff)
- **Referee regimes**: Pre-Respect (<2008) · Respect-Campaign (2008-16) · Webb-Era (2017+)
- **Home advantage decay**: Significant drop post-COVID (ghost game flag)
- **Rolling form window**: 5-match shift(1) to prevent data leakage
- **Dixon-Coles ρ correction**: Adjusts low-score biases (0-0, 1-0, 0-1, 1-1)

---

## 🧪 Running Tests

```powershell
# Activate venv first
.venv\Scripts\Activate.ps1

# Run tests
python -m pytest tests/ -v
```

---

## 💰 Bet Tracker Features

- Log bets across all 5 leagues and 10 markets
- Auto P&L calculation (stake × odds – stake)
- Dashboard: Cumulative P&L chart, Monthly bars, ROI by market, ROI by league
- Filter by league, market, result

---

## 📄 License

MIT
