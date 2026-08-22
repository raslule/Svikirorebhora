"""
WEATHER CLIENT — Phase 3 Data Integration
Fetches match-day weather forecast at a venue using Open-Meteo API.
No API key required. Completely free.

API: https://api.open-meteo.com
Used at prediction time to enrich corners and fouls model features.
Results are cached per (lat, lon, date) for 6 hours to avoid redundant calls.
"""
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Tuple
import time

# ---------------------------------------------------------------------------
# In-memory cache: (lat, lon, date_str) -> weather_dict, timestamp
# ---------------------------------------------------------------------------
_CACHE: Dict[Tuple, Tuple[Dict, float]] = {}
_CACHE_TTL_SECONDS = 6 * 3600  # 6 hours


def get_match_weather(
    lat: float,
    lon: float,
    match_date: Optional[date] = None,
    kickoff_hour: int = 15,
) -> Dict:
    """
    Fetch hourly weather at (lat, lon) for match_date at kickoff_hour.
    Returns a dict with keys:
        precip_mm   - precipitation (mm) at kickoff
        wind_kmh    - wind speed (km/h) at kickoff
        temp_c      - temperature (degC) at kickoff
        is_wet      - bool: precip >= 2mm
        is_windy    - bool: wind >= 25 km/h
        is_cold     - bool: temp < 5C
    Falls back to neutral values on any network error.
    """
    match_date = match_date or date.today()
    cache_key = (round(lat, 3), round(lon, 3), str(match_date))

    # Return cached result if fresh
    if cache_key in _CACHE:
        cached_data, cached_at = _CACHE[cache_key]
        if time.time() - cached_at < _CACHE_TTL_SECONDS:
            return cached_data

    try:
        from datetime import date as _date_type
        today = _date_type.today()
        delta_days = (match_date - today).days if hasattr(match_date, "toordinal") else 0
        # Open-Meteo free tier: use forecast_days (1-16) instead of start_date
        forecast_days = max(1, min(16, delta_days + 1)) if delta_days >= 0 else 1
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=precipitation,windspeed_10m,temperature_2m"
            f"&forecast_days={forecast_days}"
            "&timezone=auto"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip_series = hourly.get("precipitation", [])
        wind_series = hourly.get("windspeed_10m", [])
        temp_series = hourly.get("temperature_2m", [])

        # Find the index for the correct date and kickoff_hour
        target_hour = f"{match_date}T{kickoff_hour:02d}:00"
        idx = 0
        best_diff = None
        for i, t in enumerate(times):
            try:
                from datetime import datetime as _dt
                t_dt = _dt.fromisoformat(t)
                diff = abs((t_dt.hour * 60 + t_dt.minute) - kickoff_hour * 60)
                t_date = t_dt.date()
                if t_date == match_date and (best_diff is None or diff < best_diff):
                    best_diff = diff
                    idx = i
            except Exception:
                pass

        precip = float(precip_series[idx]) if precip_series else 0.0
        wind = float(wind_series[idx]) if wind_series else 0.0
        temp = float(temp_series[idx]) if temp_series else 15.0

        result = {
            "precip_mm": round(precip, 2),
            "wind_kmh": round(wind, 1),
            "temp_c": round(temp, 1),
            "is_wet": precip >= 2.0,
            "is_windy": wind >= 25.0,
            "is_cold": temp < 5.0,
            "source": "open-meteo",
        }
        _CACHE[cache_key] = (result, time.time())
        print(f"[Weather] {match_date} ({lat},{lon}): {precip}mm, {wind}km/h, {temp}C")
        return result

    except Exception as e:
        print(f"[Weather] API error for ({lat},{lon}) on {match_date}: {e}")
        return _neutral_weather()


def _neutral_weather() -> Dict:
    """Return neutral weather features when the API is unavailable."""
    return {
        "precip_mm": 0.0,
        "wind_kmh": 10.0,
        "temp_c": 12.0,
        "is_wet": False,
        "is_windy": False,
        "is_cold": False,
        "source": "fallback",
    }


def weather_adjustment_factor(weather: Dict) -> Dict:
    """
    Convert raw weather into multipliers for corners/fouls predictions.
    Based on published research on weather effects in football:
      - Heavy rain: -8% corners, +6% fouls
      - High wind:  -5% corners, -3% goals
      - Cold:       +3% fouls (more physicality)
    Returns dict with multipliers for each model.
    """
    corners_mult = 1.0
    fouls_mult = 1.0
    goals_mult = 1.0

    if weather.get("is_wet"):
        corners_mult *= 0.92   # Wet pitch = fewer corners
        fouls_mult *= 1.06     # More fouls in slippery conditions
        goals_mult *= 0.96     # Slightly fewer goals

    if weather.get("is_windy"):
        corners_mult *= 0.95   # Wind disrupts set pieces
        goals_mult *= 0.97     # Harder to score against strong wind

    if weather.get("is_cold"):
        fouls_mult *= 1.03     # More physical in cold conditions

    return {
        "corners_multiplier": round(corners_mult, 4),
        "fouls_multiplier": round(fouls_mult, 4),
        "goals_multiplier": round(goals_mult, 4),
    }

