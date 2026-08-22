import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from backend.data.injury_scraper import _has_recent_starts, _FBREF_CACHE, run_injury_scrape
    import soccerdata as sd

print("Caching FBref data for ENG-Premier League...")
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    _FBREF_CACHE["ENG-Premier League"] = sd.FBref(leagues="ENG-Premier League", seasons="2324").read_player_season_stats(stat_type="playing_time")

def test_player(name, team, expected):
    res = _has_recent_starts(name, team, "ENG-Premier League")
    status = "PASS" if res == expected else "FAIL"
    print(f"[{status}] {name} ({team}) -> Expected: {expected}, Got: {res}")

print("\n--- Testing Live Signal Gate ---")
test_player("Bukayo Saka", "Arsenal", True)       # Regular starter
test_player("Erling Haaland", "Man City", True)   # Regular starter
test_player("Emile Smith Rowe", "Arsenal", False) # Bench player
test_player("Aaron Ramsdale", "Arsenal", False)   # Lost spot mid-season
test_player("Unmatched Name XYZ", "Arsenal", False) # Unmatched name

