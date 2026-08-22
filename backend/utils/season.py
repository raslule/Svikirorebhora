from datetime import date, timedelta

def get_current_season(today: date = None) -> str:
    """
    Returns season string in 'YYZZ' format (e.g. '2627' for 2026/2027).
    European domestic season convention: season starts August 1st.
    """
    today = today or date.today()
    if today.month >= 8:  # season starts in August
        start_year = today.year
    else:  # Jan–Jul still belongs to season that started previous year
        start_year = today.year - 1
    end_year = start_year + 1
    return f"{str(start_year)[2:]}{str(end_year)[2:]}"

def get_next_season(today: date = None) -> str:
    """
    Returns the upcoming season string in 'YYZZ' format.
    Useful for look-ahead scenarios like fixture sync in June/July.
    """
    today = today or date.today()
    current = get_current_season(today)
    start_year = int(current[:2]) + 2000
    end_year = start_year + 1
    return f"{str(start_year+1)[2:]}{str(end_year+1)[2:]}"
def parse_season_start_year(season_str: str) -> int:
    """
    Extracts the 4-digit start year from a 'YYZZ' season string.
    E.g., '2627' -> 2026.
    Useful for robust chronological comparisons.
    """
    if not season_str or len(season_str) != 4:
        raise ValueError(f"Invalid season string format: {season_str}")
    return int(season_str[:2]) + 2000
