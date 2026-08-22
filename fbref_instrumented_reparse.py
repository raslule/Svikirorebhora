import os
import glob
import bs4
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
import sys

CACHE_DIR = r"C:\Users\Liberty Marshall\soccerdata\data\FBref"
match_files = glob.glob(os.path.join(CACHE_DIR, "match_*.html"))

print(f"[INIT] Found {len(match_files)} match files in cache.")

# First pass: parse basic stats and lineups to determine key players
matches = []
player_starts = {}
team_matches = {}

print("[PROGRESS] Starting parsing pass...")
for i, file_path in enumerate(match_files):
    if i % 500 == 0 and i > 0:
        print(f"[PROGRESS] Parsed match {i}/{len(match_files)}, Valid matches so far: {len(matches)}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        soup = bs4.BeautifulSoup(f, "lxml")
    
    scorebox = soup.find("div", class_="scorebox")
    if not scorebox:
        continue
    
    # Teams
    strongs = scorebox.find_all("strong")
    if len(strongs) < 2:
        continue
    home_team = strongs[0].text.strip()
    away_team = strongs[1].text.strip()
    
    # Scores
    scores = scorebox.find_all("div", class_="score")
    if len(scores) < 2:
        continue
    try:
        home_goals = int(scores[0].text.strip())
        away_goals = int(scores[1].text.strip())
    except:
        continue
        
    # Corners
    home_corners = 0
    away_corners = 0
    team_stats = soup.find("div", id="team_stats")
    if team_stats:
        # Find the row for Corners
        for tr in team_stats.find_all("tr"):
            th = tr.find("th")
            if th and "Corners" in th.text:
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    try:
                        home_corners = int(tds[0].text.strip().split()[0])
                        away_corners = int(tds[1].text.strip().split()[0])
                    except:
                        pass
                        
    # Lineups
    lineups = soup.find_all("div", class_="lineup")
    if len(lineups) < 2:
        continue
        
    home_starters = []
    away_starters = []
    
    # Home lineup is first, away is second
    for idx, lineup_div in enumerate(lineups[:2]):
        trs = lineup_div.find_all("tr")
        # First 11 trs after header are starters usually, but FBref has 11 rows of starters then bench.
        starters = []
        for tr in trs:
            a_tag = tr.find("a")
            if a_tag:
                starters.append(a_tag.text.strip())
            if len(starters) == 11:
                break
                
        if idx == 0:
            home_starters = starters
        else:
            away_starters = starters

    if len(home_starters) != 11 or len(away_starters) != 11:
        continue

    # Update team matches count
    team_matches[home_team] = team_matches.get(home_team, 0) + 1
    team_matches[away_team] = team_matches.get(away_team, 0) + 1
    
    # Update player starts
    for p in home_starters:
        key = f"{p}_{home_team}"
        player_starts[key] = player_starts.get(key, 0) + 1
    for p in away_starters:
        key = f"{p}_{away_team}"
        player_starts[key] = player_starts.get(key, 0) + 1

    matches.append({
        "match_id": os.path.basename(file_path),
        "home_team": home_team,
        "away_team": away_team,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "home_corners": home_corners,
        "away_corners": away_corners,
        "home_starters": home_starters,
        "away_starters": away_starters
    })

print(f"[PROGRESS] Parsed match {len(match_files)}/{len(match_files)}, Valid matches so far: {len(matches)}")

# Define key players (>60% starts)
key_players = set()
for p_key, starts in player_starts.items():
    team = p_key.split("_")[-1]
    total = team_matches.get(team, 1)
    if starts / total > 0.6:
        key_players.add(p_key)

print(f"[INFO] Identified {len(key_players)} key starters across all teams.")

# Second pass: tag missing key players (we assume if they are a key player and didn't start, they are missing)
# Note: Since we don't have positional data parsed easily, we'll proxy it by finding if ANY key player is missing.
# Wait, Phase 1 had miss_fw, miss_df... 
# Actually, the user's audit asked about miss_fw, miss_df, miss_gk.
# Let's see if we can get positional data from the lineup!
