"""
QA AGENT — API integration tests.
Tests all endpoints return correct status codes and schemas.
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client):
    """Register + login a test user and return auth headers."""
    import uuid
    uname = f"testuser_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/auth/register", json={"username": uname, "password": "testpass123"})
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestAuthRoutes:
    def test_register_returns_token(self, client):
        import uuid
        uname = f"qa_user_{uuid.uuid4().hex[:6]}"
        resp = client.post("/api/auth/register", json={"username": uname, "password": "securepass"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_valid_credentials(self, client):
        client.post("/api/auth/register", json={"username": "qa_user_02", "password": "mypass"})
        resp = client.post("/api/auth/token", data={"username": "qa_user_02", "password": "mypass"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_invalid_credentials(self, client):
        resp = client.post("/api/auth/token", data={"username": "nobody", "password": "wrong"})
        assert resp.status_code == 401

    def test_me_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert "username" in resp.json()


class TestPredictionRoutes:
    def test_predict_requires_auth(self, client):
        resp = client.post("/api/predict", json={
            "home_team": "Arsenal", "away_team": "Chelsea", "league": "premier-league"
        })
        assert resp.status_code == 401

    def test_predict_valid_request(self, client, auth_headers):
        resp = client.post("/api/predict", headers=auth_headers, json={
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "league": "premier-league",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "outcome" in data
        assert "goals" in data
        assert "corners" in data
        assert "fouls" in data
        assert "meta" in data

    def test_predict_outcome_probs_sum_to_one(self, client, auth_headers):
        resp = client.post("/api/predict", headers=auth_headers, json={
            "home_team": "Real Madrid", "away_team": "Barcelona", "league": "la-liga"
        })
        assert resp.status_code == 200
        outcome = resp.json()["outcome"]
        total = outcome["prob_home"] + outcome["prob_draw"] + outcome["prob_away"]
        assert abs(total - 1.0) < 0.02

    def test_predict_invalid_league(self, client, auth_headers):
        resp = client.post("/api/predict", headers=auth_headers, json={
            "home_team": "A", "away_team": "B", "league": "fake-league"
        })
        assert resp.status_code == 400


class TestBetRoutes:
    def test_create_bet(self, client, auth_headers):
        resp = client.post("/api/bets", headers=auth_headers, json={
            "match_date": "2026-08-20",
            "league": "premier-league",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "market": "1X2",
            "selection": "Home",
            "odds": 2.10,
            "stake": 10.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["market"] == "1X2"
        assert data["result"] is None  # pending
        return data["id"]

    def test_list_bets(self, client, auth_headers):
        resp = client.get("/api/bets", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_bet_result(self, client, auth_headers):
        # Create a bet first
        create = client.post("/api/bets", headers=auth_headers, json={
            "match_date": "2026-08-21",
            "league": "la-liga",
            "home_team": "Real Madrid",
            "away_team": "Atletico",
            "market": "BTTS",
            "selection": "Yes",
            "odds": 1.80,
            "stake": 20.0,
        })
        bet_id = create.json()["id"]

        # Mark as won
        resp = client.put(f"/api/bets/{bet_id}", headers=auth_headers, json={"result": "WON"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "WON"
        assert data["profit_loss"] == pytest.approx(16.0, 0.01)  # (1.80-1) * 20

    def test_analytics_returns_summary(self, client, auth_headers):
        resp = client.get("/api/bets/analytics/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data or "message" in data


class TestMatchRoutes:
    def test_results_endpoint(self, client, auth_headers):
        resp = client.get("/api/matches/results?league=premier-league&limit=10", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_standings_endpoint(self, client, auth_headers):
        resp = client.get("/api/matches/standings?league=premier-league", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_root_health_check(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "SoccerOracle API running"
