"""
SOFTWARE DEVELOPER AGENT — FastAPI Main Application.
Registers all routers, starts the scheduler, seeds DB on first run.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from .routes import auth, predictions, matches, bets
from ..data.database import init_db
from ..data.auto_updater import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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
