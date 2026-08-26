from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
import joblib
import pandas as pd
from typing import List, Dict, Any

from ...data.database import get_db, Match

router = APIRouter(prefix="/api/teams", tags=["teams"])

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "artifacts"
)
DC_PATH = os.path.join(MODEL_DIR, "goals_dc.joblib")

@router.get("/{league}")
def get_teams(league: str, db: Session = Depends(get_db)):
    """Returns a list of unique teams in a league, sorted alphabetically."""
    teams = db.query(Match.home_team).filter(Match.league == league).distinct().all()
    if not teams:
        raise HTTPException(status_code=404, detail="League not found or has no teams.")
    
    return sorted([t[0] for t in teams])

@router.get("/{team_name}/analytics")
def get_team_analytics(team_name: str, db: Session = Depends(get_db)):
    """
    Returns analytics for a team:
    - 15-match performance trend (ELO pre-match)
    - 5-match rolling form (W/D/L, GF, GA)
    - Attack/Defense profile (Dixon-Coles)
    - Referee regime impact (PPG under STRICT vs LENIENT)
    """
    matches = db.query(Match).filter(
        (Match.home_team == team_name) | (Match.away_team == team_name)
    ).order_by(Match.date.desc()).limit(15).all()
    
    if not matches:
        raise HTTPException(status_code=404, detail="Team not found.")
        
    matches = list(reversed(matches)) # chronological order for trend
    
    elo_trend = []
    for m in matches:
        if m.home_team == team_name:
            elo = m.home_elo_pre
            gf = m.fthg
            ga = m.ftag
            res = 'W' if m.ftr == 'H' else 'L' if m.ftr == 'A' else 'D'
            opp = m.away_team
            is_home = True
        else:
            elo = m.away_elo_pre
            gf = m.ftag
            ga = m.fthg
            res = 'W' if m.ftr == 'A' else 'L' if m.ftr == 'H' else 'D'
            opp = m.home_team
            is_home = False
            
        elo_trend.append({
            'date': m.date.strftime("%Y-%m-%d") if m.date else "",
            'elo': round(elo, 1) if elo else 1500.0,
            'gf': gf,
            'ga': ga,
            'result': res,
            'opponent': opp,
            'is_home': is_home
        })
        
    last_5 = elo_trend[-5:]
    form_results = [m['result'] for m in last_5]
    form_gf = sum([m['gf'] for m in last_5 if m['gf'] is not None])
    form_ga = sum([m['ga'] for m in last_5 if m['ga'] is not None])
    
    attack = 0.0
    defense = 0.0
    try:
        arts = joblib.load(DC_PATH)
        att_dict = arts.get("att") if "att" in arts else arts.get("params", {}).get("att", {})
        def_dict = arts.get("def") if "def" in arts else arts.get("params", {}).get("def", {})
        if team_name in att_dict:
            attack = att_dict[team_name]
        if team_name in def_dict:
            defense = def_dict[team_name]
    except FileNotFoundError:
        pass
        
    att_score = min(max((attack * 100) + 50, 0), 100)
    def_score = min(max((-defense * 100) + 50, 0), 100)
    
    all_matches = db.query(Match).filter(
        (Match.home_team == team_name) | (Match.away_team == team_name)
    ).all()
    
    regime_stats = {"STRICT": {"pts": 0, "m": 0}, "AVERAGE": {"pts": 0, "m": 0}, "LENIENT": {"pts": 0, "m": 0}}
    for m in all_matches:
        regime = m.referee_regime or "AVERAGE"
        
        pts = 0
        if m.home_team == team_name:
            if m.ftr == 'H': pts = 3
            elif m.ftr == 'D': pts = 1
        else:
            if m.ftr == 'A': pts = 3
            elif m.ftr == 'D': pts = 1
            
        if regime in regime_stats:
            regime_stats[regime]["pts"] += pts
            regime_stats[regime]["m"] += 1
            
    referee_impact = []
    for reg, data in regime_stats.items():
        ppg = (data["pts"] / data["m"]) if data["m"] > 0 else 0
        referee_impact.append({
            "regime": reg,
            "ppg": round(ppg, 2),
            "matches": data["m"]
        })
        
    is_sparse = len(all_matches) < 5

    return {
        "team": team_name,
        "is_sparse": is_sparse,
        "elo_trend": elo_trend,
        "form": {
            "results": form_results,
            "gf": form_gf,
            "ga": form_ga
        },
        "profile": {
            "attack_raw": round(attack, 3),
            "defense_raw": round(defense, 3),
            "attack_score": round(att_score, 0),
            "defense_score": round(def_score, 0)
        },
        "referee_impact": referee_impact
    }
