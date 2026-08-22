"""
SOFTWARE DEVELOPER AGENT — FastAPI Main Application.
Registers all routers, starts the scheduler, seeds DB on first run.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from .routes import auth, predictions, matches, bets, teams
from ..data.database import init_db
from ..data.auto_updater import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Safeguard: Check models
    import os
    from ..models import outcome_model
    model_dir = os.path.join(os.path.dirname(os.path.abspath(outcome_model.__file__)), "artifacts")
    required_artifacts = [
        "outcome_xgb.joblib", 
        "goals_dc.joblib", 
        "corners_home.joblib", 
        "corners_away.joblib", 
        "fouls_home.joblib", 
        "fouls_away.joblib"
    ]
    
    missing = [m for m in required_artifacts if not os.path.exists(os.path.join(model_dir, m))]
    if missing:
        print(f"[App] Notice: Missing model artifacts {missing}. Application operating with default model fallbacks.")

    print("[App] Initializing database...")
    init_db()

    # Seed DB from historical CSVs if empty
    from ..data.database import SessionLocal, Match
    db = SessionLocal()
    count = db.query(Match).count()
    db.close()

    if count == 0:
        print("[App] No data found — seeding from historical CSVs...")
        from ..data.data_loader import seed_database
        try:
            seed_database()
        except Exception as e:
            print(f"[App] Seeding failed: {e}")
    else:
        print(f"[App] Database has {count:,} matches. Skipping seed.")

    # Start weekly auto-updater scheduler
    scheduler = start_scheduler()

    yield

    # Shutdown
    scheduler.shutdown()
    print("[App] Scheduler stopped.")


app = FastAPI(
    title="SoccerOracle — European Match Intelligence",
    description="AI-powered soccer prediction engine covering EPL, La Liga, Serie A, Ligue 1.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(predictions.router)
app.include_router(matches.router)
app.include_router(teams.router)
app.include_router(bets.router)


@app.get("/")
def root():
    return {"status": "SoccerOracle API running", "version": "1.0.0", "docs": "/docs"}


@app.post("/api/admin/retrain")
def retrain_models():
    """Admin endpoint to retrain all models on latest data."""
    from ..models.backtester import run_backtest
    results = run_backtest()
    return {"status": "retrain_complete", "metrics": results}


@app.post("/api/admin/update-data")
def trigger_update():
    """Admin endpoint to manually trigger data update."""
    from ..data.auto_updater import run_update
    result = run_update()
    return {"status": "update_complete", "summary": result}


@app.get("/api/models/info")
def get_models_info():
    """Returns dynamic single source of truth model architecture, targets, and artifact metadata."""
    import joblib, os
    from datetime import datetime

    artifact_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "artifacts")
    
    def get_artifact_meta(filename):
        filepath = os.path.join(artifact_dir, filename)
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            return {
                "exists": True,
                "last_modified": datetime.fromtimestamp(mtime).isoformat()
            }
        return {"exists": False, "last_modified": None}

    # Load goals_dc metadata
    goals_meta = get_artifact_meta("goals_dc.joblib")
    goals_params = {}
    if goals_meta["exists"]:
        try:
            dc_data = joblib.load(os.path.join(artifact_dir, "goals_dc.joblib"))
            goals_params = {
                "home_adv": round(dc_data.get("home_adv", 0.0), 4),
                "rho": round(dc_data.get("rho", 0.0), 4),
                "teams_count": len(dc_data.get("att", {}))
            }
        except Exception:
            pass

    outcome_meta = get_artifact_meta("outcome_xgb.joblib")
    outcome_arch = "XGBoost + Dixon-Coles (70/30 Fusion)"
    if outcome_meta["exists"]:
        try:
            o_info = joblib.load(os.path.join(artifact_dir, "outcome_meta.joblib"))
            weights = o_info.get("weights", (0.70, 0.30))
            gate = o_info.get("gate_status", "active")
            w_xgb = int(round(weights[0] * 100))
            w_dc = int(round(weights[1] * 100))
            outcome_arch = f"XGBoost + Dixon-Coles ({w_xgb}/{w_dc} {gate.capitalize()})"
            outcome_meta.update(o_info)
        except Exception:
            pass

    corners_meta = get_artifact_meta("corners_home.joblib")
    fouls_meta   = get_artifact_meta("fouls_home.joblib")
    cards_meta   = get_artifact_meta("cards_hy.joblib")
    shots_meta   = get_artifact_meta("shots_hs.joblib")

    return {
        "models": [
            {
                "id": "outcome",
                "name": "1X2 Outcome",
                "architecture": outcome_arch,
                "target": "Brier Score < 0.22",
                "badge": "badge-teal",
                "artifact": outcome_meta
            },
            {
                "id": "goals",
                "name": "xG & BTTS",
                "architecture": "Dixon-Coles Bivariate Poisson (MLE, L-BFGS-B)",
                "target": "BTTS Log-Loss",
                "badge": "badge-purple",
                "artifact": {**goals_meta, **goals_params}
            },
            {
                "id": "corners",
                "name": "Corners",
                "architecture": "Negative Binomial GLM",
                "target": "MAE < 2.5 corners",
                "badge": "badge-amber",
                "artifact": corners_meta
            },
            {
                "id": "fouls",
                "name": "Fouls",
                "architecture": "Poisson Regression + Referee Regime",
                "target": "MAE < 3.0 fouls",
                "badge": "badge-green",
                "artifact": fouls_meta
            },
            {
                "id": "cards",
                "name": "Cards",
                "architecture": "Poisson GLM + Referee Strictness Scaling",
                "target": "MAE < 1.5 cards",
                "badge": "badge-rose",
                "artifact": cards_meta
            },
            {
                "id": "shots",
                "name": "Total Shots & SOT",
                "architecture": "Negative Binomial GLM + Dixon-Coles xG",
                "target": "MAE < 4.0 shots",
                "badge": "badge-cyan",
                "artifact": shots_meta
            }
        ]
    }

