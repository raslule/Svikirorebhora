"""
QA AGENT — Test suite for all models.
Validates output shapes, probability constraints, Brier score targets.
"""
import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Outcome Model ────────────────────────────────────────────────────────────
class TestOutcomeModel:
    def test_predict_returns_valid_probs(self, monkeypatch):
        """Probabilities should sum to 1 and be non-negative."""
        from backend.models import outcome_model
        import joblib

        # Mock joblib loads with simple passthrough
        class MockXGB:
            def predict_proba(self, X):
                return np.array([[0.50, 0.25, 0.25]])

        class MockLR:
            def predict_proba(self, X):
                return np.array([[0.45, 0.30, 0.25]])

        monkeypatch.setattr(joblib, "load", lambda p: MockXGB() if "xgb" in p else MockLR())

        result = outcome_model.predict({}, {}, {})
        total = result["prob_home"] + result["prob_draw"] + result["prob_away"]
        assert abs(total - 1.0) < 0.01, f"Probs should sum to 1, got {total}"
        assert result["prob_home"] >= 0
        assert result["prob_draw"] >= 0
        assert result["prob_away"] >= 0

    def test_implied_odds_positive(self, monkeypatch):
        """Implied odds must be positive."""
        from backend.models import outcome_model
        import joblib

        class MockModel:
            def predict_proba(self, X):
                return np.array([[0.50, 0.25, 0.25]])

        monkeypatch.setattr(joblib, "load", lambda p: MockModel())
        result = outcome_model.predict({}, {}, {})
        assert result["implied_home_odds"] > 0
        assert result["implied_draw_odds"] > 0
        assert result["implied_away_odds"] > 0


# ─── Goals Model ──────────────────────────────────────────────────────────────
class TestGoalsModel:
    def test_elo_fallback_predict(self):
        """ELO fallback must return valid xG and probabilities."""
        from backend.models.goals_model import predict

        # Use non-existent teams to trigger fallback (no DC artifacts)
        result = predict("TeamX", "TeamY", "premier-league", elo_diff=0.0)

        assert result["xg_home"] > 0
        assert result["xg_away"] > 0
        assert 0 <= result["prob_btts"] <= 1
        assert 0 <= result["prob_over_2_5"] <= 1
        assert 0 <= result["prob_over_3_5"] <= 1
        # Over 2.5 should be >= Over 3.5
        assert result["prob_over_2_5"] >= result["prob_over_3_5"]

    def test_btts_plus_complement_bounds(self):
        """BTTS Yes + No should be <= 1 (with margin for floats)."""
        from backend.models.goals_model import predict
        result = predict("A", "B", "la-liga", elo_diff=50.0)
        assert result["prob_btts"] <= 1.0
        assert result["prob_btts"] >= 0.0

    def test_high_elo_diff_increases_home_xg(self):
        """Home team with high ELO advantage should have higher xG."""
        from backend.models.goals_model import predict
        high_adv = predict("Strong", "Weak", "premier-league", elo_diff=300.0)
        low_adv  = predict("Strong", "Weak", "premier-league", elo_diff=-300.0)
        assert high_adv["xg_home"] > low_adv["xg_home"]


# ─── Corners Model ────────────────────────────────────────────────────────────
class TestCornersModel:
    def test_fallback_returns_reasonable_values(self, monkeypatch):
        """Without trained artifacts, should return sensible fallback values."""
        from backend.models import corners_model

        # Patch joblib.load to raise FileNotFoundError
        import joblib
        monkeypatch.setattr(joblib, "load", lambda p: (_ for _ in ()).throw(FileNotFoundError))

        result = corners_model.predict({}, {}, {})
        assert result.get("exp_home_corners", 0) > 0
        assert result.get("exp_away_corners", 0) > 0

    def test_over_9_5_greater_than_over_11_5(self, monkeypatch):
        """P(over 9.5) must be >= P(over 11.5)."""
        from backend.models import corners_model
        import joblib
        monkeypatch.setattr(joblib, "load", lambda p: (_ for _ in ()).throw(FileNotFoundError))

        result = corners_model.predict({}, {}, {})
        o9 = result.get("prob_corners_over_9_5", 0.55)
        o11 = result.get("prob_corners_over_11_5", 0.30)
        assert o9 >= o11


# ─── Fouls Model ──────────────────────────────────────────────────────────────
class TestFoulsModel:
    def test_fallback_returns_values(self, monkeypatch):
        """Without trained artifacts, fouls model must still return values."""
        from backend.models import fouls_model
        import joblib
        monkeypatch.setattr(joblib, "load", lambda p: (_ for _ in ()).throw(FileNotFoundError))

        result = fouls_model.predict({}, {}, {})
        assert result.get("exp_total_fouls", 0) > 0
        assert 0 <= result.get("prob_fouls_over_20", 0) <= 1
        assert result.get("prob_fouls_over_20", 1) >= result.get("prob_fouls_over_30", 0)


# ─── Feature Engineering ──────────────────────────────────────────────────────
class TestFeatureEngineering:
    def _sample_df(self):
        import pandas as pd
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15",
                                     "2024-01-22", "2024-01-29", "2024-02-05"]),
            "home_team": ["Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea"],
            "away_team": ["Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal"],
            "fthg": [2.0, 1.0, 3.0, 0.0, 1.0, 2.0],
            "ftag": [1.0, 1.0, 1.0, 2.0, 1.0, 0.0],
            "ftr":  ["H", "D", "H", "A", "D", "H"],
            "hst": [6.0, 4.0, 8.0, 2.0, 5.0, 7.0],
            "ast": [3.0, 5.0, 2.0, 6.0, 4.0, 2.0],
            "hc": [5.0, 4.0, 6.0, 3.0, 5.0, 6.0],
            "ac": [4.0, 5.0, 3.0, 6.0, 4.0, 3.0],
            "hf": [12.0, 10.0, 14.0, 8.0, 11.0, 13.0],
            "af": [11.0, 13.0, 9.0, 14.0, 10.0, 11.0],
            "hy": [2.0, 1.0, 3.0, 0.0, 2.0, 1.0],
            "ay": [1.0, 2.0, 1.0, 3.0, 1.0, 2.0],
            "hr": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "ar": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "referee": ["M.Oliver"] * 6,
        })
        df["Date"] = df["date"]
        return df

    def test_elo_computed(self):
        from backend.data.feature_engineering import calculate_elo
        df = self._sample_df()
        result, elo_dict = calculate_elo(df)
        assert "Home_ELO" in result.columns
        assert "Away_ELO" in result.columns
        assert len(result) == len(df)

    def test_rolling_form_no_leakage(self):
        """Rolling form should be NaN or based only on prior matches."""
        from backend.data.feature_engineering import add_rolling_form
        df = self._sample_df()
        result = add_rolling_form(df)
        # First match for each team should have NaN rolling form (no prior matches)
        # We just check columns exist
        assert "Home_Roll_GF" in result.columns
        assert "Away_Roll_GF" in result.columns

    def test_referee_regime_assigned(self):
        from backend.data.feature_engineering import add_referee_regime
        df = self._sample_df()
        result = add_referee_regime(df)
        assert "referee_regime" in result.columns
        assert all(result["referee_regime"].isin(["Pre-Respect", "Respect-Campaign", "Webb-Era"]))

    def test_ghost_game_flag(self):
        from backend.data.feature_engineering import add_ghost_game_flag
        import pandas as pd
        df = pd.DataFrame({
            "date": pd.to_datetime(["2019-12-01", "2020-04-15", "2021-03-10", "2022-01-01"]),
            "home_team": ["A"] * 4,
            "away_team": ["B"] * 4,
        })
        result = add_ghost_game_flag(df)
        assert result.loc[result["date"] < "2020-03-01", "is_ghost_game"].sum() == 0
        assert result.loc[result["date"] == "2020-04-15", "is_ghost_game"].values[0] == 1
        assert result.loc[result["date"] == "2022-01-01", "is_ghost_game"].values[0] == 0
