import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
import logging

# We will import run_empirical_analysis from backend/data/fbref_empirical.py
# First, we need to modify fbref_empirical.py temporarily to return the df_model instead of just running
with open("backend/data/fbref_empirical.py", "r", encoding="utf-8") as f:
    code = f.read()

# Make it return df_model
code = code.replace("df_reg = pd.DataFrame(records)", "df_reg = pd.DataFrame(records)\n    return df_model")
code += "\n\nif __name__ == '__main__':\n    df_model = run_empirical_analysis(sample_mode=False)\n    df_model.to_csv('real_fbref_cache.csv', index=False)\n"

with open("temp_fbref.py", "w", encoding="utf-8") as f:
    f.write(code)

import temp_fbref
print("Running actual FBref scrape from local soccerdata cache...")
df_fbref = temp_fbref.run_empirical_analysis(sample_mode=False)

print(f"FBref data loaded: {len(df_fbref)} matches.")

# Load corners from soccer_oracle.db
print("Loading corners data from soccer_oracle.db...")
conn = sqlite3.connect("data/soccer_oracle.db")
df_db = pd.read_sql("SELECT season, home_team, away_team, hc, ac FROM matches", conn)
conn.close()

# Normalize team names for merging or just merge on date/teams if possible.
# Wait, soccerdata team names and football-data.co.uk team names might differ!
# We can use fuzzy matching or just a known map.
# Let's see how many match exactly first.
df_fbref["season_str"] = df_fbref["season"].astype(str)
df_db["season_str"] = df_db["season"].astype(str).str.replace("20", "").str.replace("/", "")
# e.g. "2021/2022" -> "2122", let's fix that
def fix_season(x):
    if "/" in str(x):
        parts = str(x).split("/")
        return parts[0][-2:] + parts[1][-2:]
    return str(x)
df_db["season_str"] = df_db["season"].apply(fix_season)

# Simple merge
merged = pd.merge(df_fbref, df_db, left_on=["season", "home_team", "away_team"], right_on=["season_str", "home_team", "away_team"], how="inner")
print(f"Direct team name merge matched: {len(merged)} matches.")

if len(merged) < len(df_fbref) * 0.5:
    print("Direct match failed for many teams. We will use difflib to map teams.")
    import difflib
    db_teams = df_db['home_team'].unique()
    fb_teams = df_fbref['home_team'].unique()
    team_map = {}
    for ft in fb_teams:
        matches = difflib.get_close_matches(ft, db_teams, n=1, cutoff=0.6)
        if matches:
            team_map[ft] = matches[0]
        else:
            team_map[ft] = ft
    
    df_fbref['home_team_db'] = df_fbref['home_team'].map(team_map)
    df_fbref['away_team_db'] = df_fbref['away_team'].map(team_map)
    
    merged = pd.merge(df_fbref, df_db, left_on=["season", "home_team_db", "away_team_db"], right_on=["season_str", "home_team", "away_team"], how="inner")
    print(f"Fuzzy team name merge matched: {len(merged)} matches.")

# Now we have df_model with hc and ac!
# We need to compute score-state confound. Since we don't have trailing time, we'll just use a basic proxy or omit it and state we omitted it due to data limitations.
# Actually, the user said: "At minimum, flag this as a known limitation if you're not controlling for it"

print("\n--- ACTUAL REAL DATA CORNERS EMPIRICAL RESULTS ---")
print(f"N={len(merged)}")
merged['hc'] = pd.to_numeric(merged['hc'], errors='coerce')
merged['ac'] = pd.to_numeric(merged['ac'], errors='coerce')
merged = merged.dropna(subset=['hc', 'ac'])

alpha = 0.05 / 8

# HC Regression
# In statsmodels, space in team names causes issues if not wrapped in Q() or if we just use them directly in C()
# Let's replace spaces in column names
merged.columns = [c.replace(' ', '_').replace('-', '_') for c in merged.columns]
formula_hc = "hc ~ C(home_team) + C(away_team) + home_miss_fw + home_miss_mf + away_miss_df + away_miss_gk"
formula_ac = "ac ~ C(home_team) + C(away_team) + away_miss_fw + away_miss_mf + home_miss_df + home_miss_gk"

try:
    model_hc = smf.glm(formula=formula_hc, data=merged, family=sm.families.NegativeBinomial(alpha=0.2)).fit()
    model_ac = smf.glm(formula=formula_ac, data=merged, family=sm.families.NegativeBinomial(alpha=0.2)).fit()

    results = [
        ("home_miss_fw (Impact on own corners)", model_hc, "home_miss_fw"),
        ("home_miss_mf (Impact on own corners)", model_hc, "home_miss_mf"),
        ("away_miss_df (Impact on opp corners)", model_hc, "away_miss_df"),
        ("away_miss_gk (Impact on opp corners)", model_hc, "away_miss_gk"),
        ("away_miss_fw (Impact on own corners)", model_ac, "away_miss_fw"),
        ("away_miss_mf (Impact on own corners)", model_ac, "away_miss_mf"),
        ("home_miss_df (Impact on opp corners)", model_ac, "home_miss_df"),
        ("home_miss_gk (Impact on opp corners)", model_ac, "home_miss_gk"),
    ]

    for name, model, term in results:
        coef = model.params.get(term, 0)
        p_val = model.pvalues.get(term, 1)
        pct_change = (np.exp(coef) - 1) * 100
        n_obs = merged[term].sum()
        
        ci_lower = (np.exp(model.conf_int().loc[term, 0]) - 1) * 100
        ci_upper = (np.exp(model.conf_int().loc[term, 1]) - 1) * 100
        
        sig_marker = "*" if p_val < alpha else ""
        print(f"{name:<40}: {pct_change:>6.2f}% (95% CI: {ci_lower:>6.2f}% to {ci_upper:>6.2f}%), p-value: {p_val:.4f} (N={n_obs}){sig_marker}")

except Exception as e:
    print(f"Regression failed: {e}")

