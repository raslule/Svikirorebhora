# -*- coding: utf-8 -*-
import pandas as pd
import soccerdata as sd
import warnings
import re
warnings.filterwarnings('ignore')

print("Fetching Liverpool 23/24 data for GK spot-check...")
fb = sd.FBref(leagues='ENG-Premier League', seasons='2324')
schedule = fb.read_schedule()
schedule = schedule.dropna(subset=['home_team', 'away_team', 'score'])
schedule.reset_index(inplace=True)

# Parse goals using regex to avoid en-dash unicode issues
def get_ga(row, team):
    try:
        hg, ag = map(int, re.split(r'\D+', row['score'])[0:2])
        return ag if row['home_team'] == team else hg
    except:
        return None

liv_games = schedule[(schedule['home_team'] == 'Liverpool') | (schedule['away_team'] == 'Liverpool')].copy()
liv_games['GA'] = liv_games.apply(lambda r: get_ga(r, 'Liverpool'), axis=1)
liv_games['game_id'] = liv_games['game_id'].astype(str)

print("Fetching lineups to identify Alisson starts...")
lineups = fb.read_lineup(match_id=liv_games['game_id'].tolist())
lineups.reset_index(inplace=True)

liv_lineups = lineups[(lineups['team'] == 'Liverpool') & (lineups['is_starter'] == True)]
alisson_games = liv_lineups[liv_lineups['player'].str.contains("Alisson", na=False)]['game'].tolist()

liv_games['alisson_started'] = liv_games['game'].isin(alisson_games)

with_alisson = liv_games[liv_games['alisson_started'] == True]
without_alisson = liv_games[liv_games['alisson_started'] == False]

print("\n--- Spot Check 1: Liverpool 23/24 (Alisson vs. Kelleher) ---")
print(f"With Alisson: {len(with_alisson)} games, {with_alisson['GA'].sum()} GA ({with_alisson['GA'].mean():.2f} GA/game)")
print(f"Without Alisson: {len(without_alisson)} games, {without_alisson['GA'].sum()} GA ({without_alisson['GA'].mean():.2f} GA/game)")

print("\nFetching Real Madrid 23/24 data for GK spot-check...")
fb_rm = sd.FBref(leagues='ESP-La Liga', seasons='2324')
schedule_rm = fb_rm.read_schedule()
schedule_rm = schedule_rm.dropna(subset=['home_team', 'away_team', 'score'])
schedule_rm.reset_index(inplace=True)

rm_games = schedule_rm[(schedule_rm['home_team'] == 'Real Madrid') | (schedule_rm['away_team'] == 'Real Madrid')].copy()
rm_games['GA'] = rm_games.apply(lambda r: get_ga(r, 'Real Madrid'), axis=1)
rm_games['game_id'] = rm_games['game_id'].astype(str)

print("Fetching lineups to identify Courtois starts...")
lineups_rm = fb_rm.read_lineup(match_id=rm_games['game_id'].tolist())
lineups_rm.reset_index(inplace=True)

rm_lineups = lineups_rm[(lineups_rm['team'] == 'Real Madrid') & (lineups_rm['is_starter'] == True)]
courtois_games = rm_lineups[rm_lineups['player'].str.contains("Thibaut Courtois", na=False)]['game'].tolist()

rm_games['courtois_started'] = rm_games['game'].isin(courtois_games)

with_courtois = rm_games[rm_games['courtois_started'] == True]
without_courtois = rm_games[rm_games['courtois_started'] == False]

print("\n--- Spot Check 2: Real Madrid 23/24 (Courtois ACL injury) ---")
print(f"With Courtois: {len(with_courtois)} games, {with_courtois['GA'].sum()} GA ({with_courtois['GA'].mean():.2f} GA/game)")
print(f"Without Courtois: {len(without_courtois)} games, {without_courtois['GA'].sum()} GA ({without_courtois['GA'].mean():.2f} GA/game)")
