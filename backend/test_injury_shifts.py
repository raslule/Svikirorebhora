# -*- coding: utf-8 -*-
from backend.models.goals_model import predict

target_probs = [0.60, 0.25, 0.15]  # Outcome model probabilities
print("--- Test 1: Base Prediction (No injuries) ---")
res_base = predict(home_team="Arsenal", away_team="Everton", league="ENG-Premier League", target_probs=target_probs)
lam_base = res_base['xg_home']
mu_base = res_base['xg_away']
print(f"Base xG -> Home: {lam_base}, Away: {mu_base}")
ro_base = res_base['reconciled_outcome']
print(f"Prob Sum (IPF check): {ro_base.get('prob_home', 0) + ro_base.get('prob_draw', 0) + ro_base.get('prob_away', 0):.4f}")

print("\n--- Test 2: Arsenal missing Key FW ---")
res_fw = predict(home_team="Arsenal", away_team="Everton", league="ENG-Premier League", target_probs=target_probs, home_miss_fw=True)
lam_fw = res_fw['xg_home']
mu_fw = res_fw['xg_away']
shift_fw = (lam_fw - lam_base) / lam_base
print(f"Missing FW xG -> Home: {lam_fw}, Away: {mu_fw}")
print(f"Shift on Home xG: {shift_fw:.4%} (Expected: -11.45%)")
ro_fw = res_fw['reconciled_outcome']
print(f"Prob Sum (IPF check): {ro_fw.get('prob_home', 0) + ro_fw.get('prob_draw', 0) + ro_fw.get('prob_away', 0):.4f}")

print("\n--- Test 3: Arsenal missing Key DF ---")
res_df = predict(home_team="Arsenal", away_team="Everton", league="ENG-Premier League", target_probs=target_probs, home_miss_df=True)
lam_df = res_df['xg_home']
mu_df = res_df['xg_away']
shift_df = (mu_df - mu_base) / mu_base
print(f"Missing DF xG -> Home: {lam_df}, Away: {mu_df}")
print(f"Shift on Away xG: {shift_df:.4%} (Expected: +8.20%)")
ro_df = res_df['reconciled_outcome']
print(f"Prob Sum (IPF check): {ro_df.get('prob_home', 0) + ro_df.get('prob_draw', 0) + ro_df.get('prob_away', 0):.4f}")

print("\n--- Test 4: Arsenal missing both FW and DF ---")
res_both = predict(home_team="Arsenal", away_team="Everton", league="ENG-Premier League", target_probs=target_probs, home_miss_fw=True, home_miss_df=True)
print(f"Missing Both xG -> Home: {res_both['xg_home']}, Away: {res_both['xg_away']}")
ro_both = res_both['reconciled_outcome']
print(f"Prob Sum (IPF check): {ro_both.get('prob_home', 0) + ro_both.get('prob_draw', 0) + ro_both.get('prob_away', 0):.4f}")


from backend.data.injury_scraper import _has_recent_starts, get_team_injury_flags
print("\n--- Test 5: Scraper positional mapping ---")
flags = get_team_injury_flags("Arsenal", "ENG-Premier League")
print("Arsenal Scraped Flags:", flags)
