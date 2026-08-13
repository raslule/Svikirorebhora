"""
SOFTWARE DEVELOPER AGENT — Prediction API routes.
POST /api/predict — returns full 5-model prediction bundle.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ...models.model_registry import predict_match
from ..routes.auth import get_current_user
from ...data.database import User, SessionLocal, Prediction

router = APIRouter(prefix="/api/predict", tags=["predictions"])

VALID_LEAGUES = {"premier-league", "la-liga", "serie-a", "ligue-1", "bundesliga"}


class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    league: str
    match_date: Optional[str] = None


class PredictResponse(BaseModel):
    home_team: str
    away_team: str
    league: str
    match_date: Optional[str]
    outcome: dict
    goals: dict
    corners: dict
    fouls: dict
    meta: dict


@router.post("", response_model=PredictResponse)
def predict(req: PredictRequest, current_user: User = Depends(get_current_user)):
    if req.league.lower() not in VALID_LEAGUES:
        raise HTTPException(status_code=400, detail=f"Invalid league. Choose from: {VALID_LEAGUES}")

    match_date = None
    if req.match_date:
        try:
            match_date = datetime.fromisoformat(req.match_date)
        except ValueError:
            pass

    result = predict_match(
        home_team=req.home_team,
        away_team=req.away_team,
        league=req.league.lower(),
        match_date=match_date,
    )

    # Store prediction in DB
    db = SessionLocal()
    try:
        pred = Prediction(
            league=req.league.lower(),
            home_team=req.home_team,
            away_team=req.away_team,
            match_date=match_date,
            prob_home=result["outcome"].get("prob_home"),
            prob_draw=result["outcome"].get("prob_draw"),
            prob_away=result["outcome"].get("prob_away"),
            xg_home=result["goals"].get("xg_home"),
            xg_away=result["goals"].get("xg_away"),
            prob_btts=result["goals"].get("prob_btts"),
            prob_over_2_5=result["goals"].get("prob_over_2_5"),
            prob_over_3_5=result["goals"].get("prob_over_3_5"),
            exp_home_corners=result["corners"].get("exp_home_corners"),
            exp_away_corners=result["corners"].get("exp_away_corners"),
            prob_corners_over_9_5=result["corners"].get("prob_corners_over_9_5"),
            prob_corners_over_10_5=result["corners"].get("prob_corners_over_10_5"),
            prob_corners_over_11_5=result["corners"].get("prob_corners_over_11_5"),
            exp_home_fouls=result["fouls"].get("exp_home_fouls"),
            exp_away_fouls=result["fouls"].get("exp_away_fouls"),
            prob_fouls_over_20=result["fouls"].get("prob_fouls_over_20"),
            prob_fouls_over_25=result["fouls"].get("prob_fouls_over_25"),
        )
        db.add(pred)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return result
