import pandas as pd
from sqlalchemy.orm import Session
from backend.data.database import engine, get_db, Match, TeamElo

# Empirically derived from 410 promoted team-seasons: -0.437 avg GD/match deficit.
# ELO-to-GD conversion: linear regression of actual match GD (fthg-ftag) against pre-match
# ELO differential (home_elo_pre - away_elo_pre) across all 45,869 historical matches.
# Result: slope = 0.00818 GD per ELO point (i.e., 100 ELO advantage ~ 0.82 GD/match).
# => -0.437 GD / 0.00818 = -53 ELO penalty => seed = 1500 - 53 = 1447
PROMOTED_PRIOR_ELO = 1447.0

def get_referee_zscores(df: pd.DataFrame):
    """
    Computes referee strictness z-score index based on standard-scaled cards and fouls.
    Returns a dict mapping referee name to z-score.
    """
    # Calculate total cards and fouls per match
    df['total_cards'] = df['hy'].fillna(0) + df['ay'].fillna(0) + df['hr'].fillna(0) + df['ar'].fillna(0)
    df['total_fouls'] = df['hf'].fillna(0) + df['af'].fillna(0)
    
    # League-wide stats
    mean_cards = df['total_cards'].mean()
    std_cards = df['total_cards'].std()
    
    mean_fouls = df['total_fouls'].mean()
    std_fouls = df['total_fouls'].std()
    
    ref_stats = []
    for ref, group in df.groupby('referee'):
        if pd.isna(ref) or len(group) <= 10:
            continue
        
        avg_cards = group['total_cards'].mean()
        avg_fouls = group['total_fouls'].mean()
        
        z_cards = (avg_cards - mean_cards) / std_cards if std_cards else 0
        z_fouls = (avg_fouls - mean_fouls) / std_fouls if std_fouls else 0
        
        z_index = (z_cards + z_fouls) / 2
        ref_stats.append({'referee': ref, 'z_index': z_index})
        
    ref_df = pd.DataFrame(ref_stats)
    if ref_df.empty:
        return {}, 0, 0
    
    p33 = ref_df['z_index'].quantile(0.33)
    p67 = ref_df['z_index'].quantile(0.67)
    
    return dict(zip(ref_df['referee'], ref_df['z_index'])), p33, p67

def sync_team_elo_table():
    """
    Synchronizes ELO ratings for all teams chronologically.
    Updates the matches table with pre/post ELOs and upserts to TeamElo snapshot.
    Also calculates and sets the referee_regime for each match.
    """
    df = pd.read_sql('SELECT * FROM matches ORDER BY date ASC', engine)
    if df.empty:
        return
    
    # Only use played matches (ftr is not null) for ELO computation.
    # Future/unplayed fixtures have ftr=NULL and must not pollute the snapshot.
    df_played = df[df['ftr'].notna()].copy()
    if df_played.empty:
        return
        
    # Get referee z-scores from played matches only
    ref_z_dict, p33, p67 = get_referee_zscores(df_played.copy())
    
    # Derive each team's canonical league from its MOST FREQUENT league in played matches.
    # Using last-seen would let a single anomalous fixture override a team's real league.
    home_leagues = df_played.groupby('home_team')['league'].agg(lambda x: x.value_counts().index[0])
    away_leagues = df_played.groupby('away_team')['league'].agg(lambda x: x.value_counts().index[0])
    team_canonical_league = {**away_leagues.to_dict(), **home_leagues.to_dict()}  # home wins tie
    
    # Figure out promoted teams per season/league
    seasons = sorted(df_played['season'].unique())
    teams_by_season_league = {}
    for (league, season), group in df_played.groupby(['league', 'season']):
        teams_by_season_league[(league, season)] = set(group['home_team']).union(set(group['away_team']))
        
    # Track ELO state
    current_elos = {}  # only populated after a team plays a real match
    teams_with_played_matches = set()  # guard for TeamElo upsert
    match_updates = []
    
    for idx, row in df_played.iterrows():
        league = row['league']
        season = row['season']
        home = row['home_team']
        away = row['away_team']
        
        # Check if promoted
        def get_prior(team):
            if team in current_elos:
                return current_elos[team]
            # Not in dict. Were they in the previous season?
            s_idx = seasons.index(season)
            if s_idx > 0:
                prev_s = seasons[s_idx - 1]
                prev_teams = teams_by_season_league.get((league, prev_s), set())
                if team not in prev_teams:
                    return PROMOTED_PRIOR_ELO
            return 1500.0
            
        home_elo = get_prior(home)
        away_elo = get_prior(away)
        
        # Determine referee regime
        ref = row['referee']
        regime = "AVERAGE"
        if ref in ref_z_dict:
            z = ref_z_dict[ref]
            if z > p67:
                regime = "STRICT"
            elif z < p33:
                regime = "LENIENT"
                
        # ELO calculation
        home_adv = 100.0
        k = 20.0
        h_prob = 1.0 / (1.0 + 10.0 ** ((away_elo - (home_elo + home_adv)) / 400.0))
        
        ftr = row.get('ftr')
        if ftr == 'H': h_actual = 1.0
        elif ftr == 'D': h_actual = 0.5
        elif ftr == 'A': h_actual = 0.0
        else: h_actual = h_prob
            
        delta = k * (h_actual - h_prob)
        home_elo_post = home_elo + delta
        away_elo_post = away_elo - delta
        
        # 38-game decay towards 1500
        home_elo_post += (1500.0 - home_elo_post) / 38.0
        away_elo_post += (1500.0 - away_elo_post) / 38.0
        
        current_elos[home] = home_elo_post
        current_elos[away] = away_elo_post
        teams_with_played_matches.add(home)
        teams_with_played_matches.add(away)
        
        match_updates.append({
            'id': row['id'],
            'home_elo_pre': home_elo,
            'away_elo_pre': away_elo,
            'home_elo_post': home_elo_post,
            'away_elo_post': away_elo_post,
            'referee_regime': regime
        })

    # Update database inside a single transaction
    db = next(get_db())
    try:
        for batch in [match_updates[i:i+1000] for i in range(0, len(match_updates), 1000)]:
            db.bulk_update_mappings(Match, batch)
            
        # Upsert TeamElo only for teams with real played match history.
        # Teams that only appear in future/unplayed fixtures are excluded.
        for team, elo in current_elos.items():
            if team not in teams_with_played_matches:
                continue
            league = team_canonical_league.get(team, "Unknown")
            obj = db.query(TeamElo).filter_by(league=league, team=team).first()
            if obj:
                obj.elo = elo
            else:
                db.add(TeamElo(league=league, team=team, elo=elo))
                
        db.commit()
        print(f"Successfully synced ELO and referee regime for {len(match_updates)} matches.")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    sync_team_elo_table()
