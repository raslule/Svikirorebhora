"""
SOFTWARE DEVELOPER AGENT — Bet Tracker API routes.
Full CRUD for bets + P&L analytics.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import numpy as np

from ...data.database import get_db, Bet, User
from ..routes.auth import get_current_user

router = APIRouter(prefix="/api/bets", tags=["bets"])


class BetCreate(BaseModel):
    match_date: str
    league: str
    home_team: str
    away_team: str
    market: str       # "1X2" | "BTTS" | "Over 2.5" | "Over 3.5" | "Corners O9.5" | "Fouls O20" etc.
    selection: str    # "Home" | "Draw" | "Away" | "Yes" | "No" | "Over" | "Under"
    odds: float
    stake: float
    notes: Optional[str] = None


class BetUpdate(BaseModel):
    result: Optional[str] = None    # "WON" | "LOST" | "VOID"
    notes: Optional[str] = None


class BetOut(BaseModel):
    id: int
    match_date: Optional[datetime]
    league: str
    home_team: str
    away_team: str
    market: str
    selection: str
    odds: float
    stake: float
    result: Optional[str]
    profit_loss: Optional[float]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=BetOut)
def create_bet(bet: BetCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    match_date = None
    try:
        match_date = datetime.fromisoformat(bet.match_date)
    except Exception:
        pass

    new_bet = Bet(
        user_id=user.id,
        match_date=match_date,
        league=bet.league,
        home_team=bet.home_team,
        away_team=bet.away_team,
        market=bet.market,
        selection=bet.selection,
        odds=bet.odds,
        stake=bet.stake,
        notes=bet.notes,
    )
    db.add(new_bet)
    db.commit()
    db.refresh(new_bet)
    return new_bet


@router.get("", response_model=List[BetOut])
def list_bets(
    league: Optional[str] = None,
    market: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Bet).filter(Bet.user_id == user.id)
    if league:
        q = q.filter(Bet.league == league)
    if market:
        q = q.filter(Bet.market == market)
    if result:
        q = q.filter(Bet.result == result)
    return q.order_by(Bet.match_date.desc()).limit(limit).all()


@router.put("/{bet_id}", response_model=BetOut)
def update_bet(
    bet_id: int,
    update: BetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    bet = db.query(Bet).filter(Bet.id == bet_id, Bet.user_id == user.id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    if update.result is not None:
        bet.result = update.result
        if update.result == "WON":
            bet.profit_loss = round((bet.odds - 1) * bet.stake, 2)
        elif update.result == "LOST":
            bet.profit_loss = -round(bet.stake, 2)
        elif update.result == "VOID":
            bet.profit_loss = 0.0

    if update.notes is not None:
        bet.notes = update.notes

    db.commit()
    db.refresh(bet)
    return bet


@router.delete("/{bet_id}")
def delete_bet(bet_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bet = db.query(Bet).filter(Bet.id == bet_id, Bet.user_id == user.id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    db.delete(bet)
    db.commit()
    return {"message": "Deleted"}


@router.get("/analytics/summary")
def bet_analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Full P&L, ROI and market breakdown analytics."""
    bets = db.query(Bet).filter(Bet.user_id == user.id).all()

    if not bets:
        return {"message": "No bets found"}

    total_bets = len(bets)
    settled = [b for b in bets if b.result in ("WON", "LOST", "VOID")]
    pending = [b for b in bets if b.result is None]
    won = [b for b in settled if b.result == "WON"]
    lost = [b for b in settled if b.result == "LOST"]

    total_stake = sum(b.stake for b in settled) if settled else 0
    total_pl = sum(b.profit_loss or 0 for b in settled)
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    win_rate = (len(won) / len(settled) * 100) if settled else 0
    avg_odds = float(np.mean([b.odds for b in settled])) if settled else 0

    # Strike rate by market
    market_stats = {}
    markets = set(b.market for b in settled)
    for mkt in markets:
        m_bets = [b for b in settled if b.market == mkt]
        m_won = [b for b in m_bets if b.result == "WON"]
        m_pl = sum(b.profit_loss or 0 for b in m_bets)
        m_stake = sum(b.stake for b in m_bets)
        market_stats[mkt] = {
            "bets": len(m_bets),
            "won": len(m_won),
            "win_rate": round(len(m_won) / len(m_bets) * 100, 1) if m_bets else 0,
            "profit_loss": round(m_pl, 2),
            "roi": round(m_pl / m_stake * 100, 2) if m_stake > 0 else 0,
        }

    # League stats
    league_stats = {}
    leagues = set(b.league for b in settled)
    for lg in leagues:
        lg_bets = [b for b in settled if b.league == lg]
        lg_won = [b for b in lg_bets if b.result == "WON"]
        lg_pl = sum(b.profit_loss or 0 for b in lg_bets)
        lg_stake = sum(b.stake for b in lg_bets)
        league_stats[lg] = {
            "bets": len(lg_bets),
            "win_rate": round(len(lg_won) / len(lg_bets) * 100, 1) if lg_bets else 0,
            "profit_loss": round(lg_pl, 2),
            "roi": round(lg_pl / lg_stake * 100, 2) if lg_stake > 0 else 0,
        }

    # Monthly P&L (for chart)
    monthly = {}
    for b in settled:
        if b.match_date:
            key = b.match_date.strftime("%Y-%m")
            monthly.setdefault(key, {"pl": 0, "stake": 0, "bets": 0})
            monthly[key]["pl"] += b.profit_loss or 0
            monthly[key]["stake"] += b.stake
            monthly[key]["bets"] += 1

    return {
        "summary": {
            "total_bets": total_bets,
            "settled": len(settled),
            "pending": len(pending),
            "won": len(won),
            "lost": len(lost),
            "win_rate": round(win_rate, 2),
            "total_stake": round(total_stake, 2),
            "total_profit_loss": round(total_pl, 2),
            "roi": round(roi, 2),
            "avg_odds": round(avg_odds, 2),
        },
        "by_market": market_stats,
        "by_league": league_stats,
        "monthly_pl": monthly,
    }
