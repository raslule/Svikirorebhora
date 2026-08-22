"""
INJURIES API — Phase 2 Data Integration
GET /api/injuries?league=premier-league&team=Arsenal
Returns current injury list for a team.
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel

from ...data.database import SessionLocal, InjuryReport
from ..routes.auth import get_current_user
from ...data.database import User

router = APIRouter(prefix="/api/injuries", tags=["injuries"])


class InjuryOut(BaseModel):
    player_name: str
    position: Optional[str]
    injury_type: Optional[str]
    expected_return: Optional[str]
    is_key_player: bool
    is_goalkeeper: bool

    class Config:
        from_attributes = True


@router.get("", response_model=List[InjuryOut])
def get_injuries(
    league: str = Query(..., description="League slug e.g. premier-league"),
    team: Optional[str] = Query(None, description="Team name (optional)"),
    current_user: User = Depends(get_current_user),
):
    """Return current injury reports for a team or all teams in a league."""
    db = SessionLocal()
    try:
        today = date.today()
        q = db.query(InjuryReport).filter(InjuryReport.league == league)
        if team:
            q = q.filter(InjuryReport.team == team)
        # Only active injuries (no return date yet or return date in future)
        injuries = q.all()
        return [
            InjuryOut(
                player_name=i.player_name,
                position=i.position,
                injury_type=i.injury_type,
                expected_return=i.expected_return.strftime("%Y-%m-%d") if i.expected_return else None,
                is_key_player=i.is_key_player,
                is_goalkeeper=i.is_goalkeeper,
            )
            for i in injuries
        ]
    finally:
        db.close()


@router.post("/scrape")
def trigger_scrape(
    league: Optional[str] = Query(None, description="Scrape specific league only"),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger injury scrape (admin use). Runs asynchronously."""
    from ...data.injury_scraper import run_injury_scrape
    import threading
    leagues = [league] if league else None
    t = threading.Thread(target=run_injury_scrape, args=(leagues,), daemon=True)
    t.start()
    return {"status": "scrape_started", "leagues": leagues or "all"}
