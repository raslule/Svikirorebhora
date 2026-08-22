# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import soccerdata as sd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import warnings
import sys
import logging
from datetime import datetime
warnings.filterwarnings('ignore')

# Set up detailed logging for the scrape
logging.basicConfig(
    filename='fbref_scrape.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

def run_empirical_analysis(sample_mode=True):
    logging.info("Starting FBref data acquisition via soccerdata...")
    leagues = ['ENG-Premier League', 'ESP-La Liga', 'ITA-Serie A', 'GER-Bundesliga', 'FRA-Ligue 1']
    seasons = ['2122', '2223', '2324']
    
    if sample_mode:
        leagues = ['ENG-Premier League']
        seasons = ['2324']
        
    fb = sd.FBref(leagues=leagues, seasons=seasons)
    
    logging.info("Fetching match schedule...")
    schedule = fb.read_schedule()
    schedule = schedule.dropna(subset=['home_team', 'away_team', 'score'])
    schedule.reset_index(inplace=True)
    schedule['game_id'] = schedule['game_id'].astype(str)
    
    if sample_mode:
        logging.info("SAMPLE MODE: Restricting to first 15 matches to prove pipeline...")
        schedule = schedule.head(15)
        
    logging.info("Fetching lineups...")
    try:
        lineups = fb.read_lineup(match_id=schedule['game_id'].tolist() if sample_mode else None)
        lineups.reset_index(inplace=True)
    except Exception as e:
        logging.error(f"Error fetching lineups: {e}")
        sys.exit(1)

    logging.info(f"Loaded {len(schedule)} matches and {len(lineups)} lineup records.")

    logging.info("Fetching player season stats to identify key players...")
    player_stats = fb.read_player_season_stats(stat_type="standard")
    player_stats.reset_index(inplace=True)
    player_stats['Min'] = pd.to_numeric(player_stats['Min'], errors='coerce').fillna(0)

    # Identify Key Players (>1500 mins)
    key_players = {}
    for (season, team), group in player_stats.groupby(['season', 'team']):
        group = group.copy()
        group['Pos_main'] = group['Pos'].astype(str).apply(lambda x: x.split(',')[0])
        
        key_dict = {}
        for pos in ['FW', 'MF', 'DF', 'GK']:
            pos_players = group[group['Pos_main'] == pos]
            if not pos_players.empty:
                top_player = pos_players.sort_values('Min', ascending=False).iloc[0]
                if top_player['Min'] > 1500 or sample_mode: 
                    key_dict[pos] = top_player['player']
        key_players[(season, team)] = key_dict

    logging.info("Annotating matches with injury/absence flags and validating starter counts...")
    starters = lineups[lineups['is_starter'] == True]
    
    # Validation check: Ensure exactly 11 starters
    starter_counts = starters.groupby(['league', 'season', 'game', 'team']).size()
    valid_games = []
    
    # Log lineup validation
    for (l_league, l_season, l_game, l_team), count in starter_counts.items():
        if count != 11:
            logging.warning(f"VALIDATION FAILED: {l_league} {l_season} {l_game} {l_team} has {count} starters instead of 11. Dropping match from dataset.")
        else:
            logging.debug(f"Validation passed: {l_league} {l_season} {l_game} {l_team} (11 starters)")
            valid_games.append(l_game)
            
    valid_games_set = set(valid_games)
    schedule = schedule[schedule['game'].isin(valid_games_set)]
    starters = starters[starters['game'].isin(valid_games_set)]

    starter_set = set(zip(starters['season'], starters['game'], starters['team'], starters['player']))

    missing_flags = []
    for idx, row in schedule.iterrows():
        season = row['season']
        game = row['game']
        row_flags = {}
        
        try:
            import re; home_goals, away_goals = map(int, re.split(r'\D+', row['score'])[0:2])
            row_flags['home_goals'] = home_goals
            row_flags['away_goals'] = away_goals
        except:
            row_flags['home_goals'] = np.nan
            row_flags['away_goals'] = np.nan
            
        for side in ['home', 'away']:
            team = row[f'{side}_team']
            kp = key_players.get((season, team), {})
            for pos_key, pos_str in [('fw', 'FW'), ('mf', 'MF'), ('df', 'DF'), ('gk', 'GK')]:
                player_name = kp.get(pos_str)
                row_flags[f'{side}_miss_{pos_key}'] = 0
                if player_name and (season, game, team, player_name) not in starter_set:
                    row_flags[f'{side}_miss_{pos_key}'] = 1
        missing_flags.append(row_flags)

    flags_df = pd.DataFrame(missing_flags)
    df_model = pd.concat([schedule.reset_index(drop=True), flags_df.reset_index(drop=True)], axis=1)
    df_model = df_model.dropna(subset=['home_goals', 'away_goals'])

    records = []
    for idx, row in df_model.iterrows():
        records.append({
            'goals': int(row['home_goals']),
            'goals_conceded': int(row['away_goals']),
            'team': row['home_team'],
            'opponent': row['away_team'],
            'is_home': 1,
            'miss_fw': row['home_miss_fw'],
            'miss_mf': row['home_miss_mf'],
            'miss_df': row['home_miss_df'],
            'miss_gk': row['home_miss_gk'],
        })
        records.append({
            'goals': int(row['away_goals']),
            'goals_conceded': int(row['home_goals']),
            'team': row['away_team'],
            'opponent': row['home_team'],
            'is_home': 0,
            'miss_fw': row['away_miss_fw'],
            'miss_mf': row['away_miss_mf'],
            'miss_df': row['away_miss_df'],
            'miss_gk': row['away_miss_gk'],
        })

    df_reg = pd.DataFrame(records)

    logging.info(f"Sample Sizes (Total team-matches: {len(df_reg)}):")
    logging.info(f"Key FW missing: {df_reg['miss_fw'].sum()}")
    logging.info(f"Key MF missing: {df_reg['miss_mf'].sum()}")
    logging.info(f"Key DF missing: {df_reg['miss_df'].sum()}")
    logging.info(f"Key GK missing: {df_reg['miss_gk'].sum()}")

    if df_reg['miss_fw'].sum() < 2 or df_reg['miss_df'].sum() < 2:
        logging.warning("Sample size too small to run Poisson regression. Run without sample_mode.")
        return

    # Helper function to extract and gate multipliers
    # Minimum 50 missing-player matches required to apply multiplier. P-value < 0.05 required for significance.
    def get_gated_multiplier(row, n_missing):
        multiplier = np.exp(row['Coef.']) - 1
        ci_lower = np.exp(row['[0.025']) - 1
        ci_upper = np.exp(row['0.975]']) - 1
        p_val = row['P>|z|']
        
        applied_multiplier = 0.0
        if n_missing >= 50 and p_val < 0.05:
            applied_multiplier = multiplier
        
        return {
            'multiplier': multiplier, 'ci_lower': ci_lower, 'ci_upper': ci_upper, 
            'p_val': p_val, 'applied': applied_multiplier
        }

    derived_multipliers = {}

    logging.info("Running Poisson Regression for Goals For (Attacking Impact)...")
    try:
        model_gf = smf.poisson("goals ~ C(team) + C(opponent) + is_home + miss_fw + miss_mf", data=df_reg).fit(disp=0)
        res_gf = model_gf.summary2().tables[1]
        
        for idx in ['miss_fw', 'miss_mf']:
            n_missing = df_reg[idx].sum()
            stats = get_gated_multiplier(res_gf.loc[idx], n_missing)
            derived_multipliers[idx] = stats
            
            logging.info(f"[{idx}] Raw: {stats['multiplier']*100:+.2f}% | CI: {stats['ci_lower']*100:+.2f}% to {stats['ci_upper']*100:+.2f}% | p: {stats['p_val']:.3f} | APPLIED ADJUSTMENT: {stats['applied']*100:+.2f}%")
            
    except Exception as e:
        logging.error(f"Goals For regression failed: {e}")

    logging.info("Running Poisson Regression for Goals Conceded (Defensive Impact)...")
    try:
        model_ga = smf.poisson("goals_conceded ~ C(team) + C(opponent) + is_home + miss_df + miss_gk", data=df_reg).fit(disp=0)
        res_ga = model_ga.summary2().tables[1]
        
        for idx in ['miss_df', 'miss_gk']:
            n_missing = df_reg[idx].sum()
            stats = get_gated_multiplier(res_ga.loc[idx], n_missing)
            derived_multipliers[idx] = stats
            
            logging.info(f"[{idx}] Raw: {stats['multiplier']*100:+.2f}% | CI: {stats['ci_lower']*100:+.2f}% to {stats['ci_upper']*100:+.2f}% | p: {stats['p_val']:.3f} | APPLIED ADJUSTMENT: {stats['applied']*100:+.2f}%")
            
    except Exception as e:
        logging.error(f"Goals Conceded regression failed: {e}")
        
    logging.info("Saving empirical multipliers to disk for Phase 2 integration...")
    np.save('injury_multipliers.npy', derived_multipliers)

if __name__ == "__main__":
    run_full = len(sys.argv) > 1 and sys.argv[1] == '--full'
    run_empirical_analysis(sample_mode=not run_full)


