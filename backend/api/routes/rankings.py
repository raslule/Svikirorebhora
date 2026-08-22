"""
SOFTWARE DEVELOPER AGENT — Rankings API routes.
GET /api/rankings — returns Dixon-Coles attack/defense power rankings.
"""
from fastapi import APIRouter
import joblib
import os

router = APIRouter(prefix="/api/rankings", tags=["rankings"])

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "artifacts"
)
DC_PATH = os.path.join(MODEL_DIR, "goals_dc.joblib")

@router.get("")
def get_power_rankings():
    try:
        arts = joblib.load(DC_PATH)
    except FileNotFoundError:
        return {"rankings": {}}

    att_dict = arts.get("att", {})
    def_dict = arts.get("def", {})
    teams = arts.get("teams", [])

    rankings = {}
    for team in teams:
        att = float(att_dict.get(team, 0.0))
        dfe = float(def_dict.get(team, 0.0))
        power = att - dfe
        rankings[team] = {
            "attack": att,
            "defense": dfe,
            "power": power
        }

    return {"rankings": rankings}
