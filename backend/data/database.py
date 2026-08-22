"""
DATABASE AGENT — SQLAlchemy SQLite schema for SoccerOracle.
Tables: matches, team_elo, predictions, bets, users
"""
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    DateTime, Boolean, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "soccer_oracle.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    league = Column(String, index=True, nullable=False)
    season = Column(String, index=True)
    date = Column(DateTime, index=True)
    home_team = Column(String, index=True)
    away_team = Column(String, index=True)
    # Full-time
    fthg = Column(Float)
    ftag = Column(Float)
    ftr = Column(String)           # H / D / A
    # Half-time
    hthg = Column(Float)
    htag = Column(Float)
    htr = Column(String)
    # Shots
    hs = Column(Float)
    as_ = Column(Float)
    hst = Column(Float)
    ast = Column(Float)
    # Corners
    hc = Column(Float)
    ac = Column(Float)
    # Fouls / Cards
    hf = Column(Float)
    af = Column(Float)
    hy = Column(Float)
    ay = Column(Float)
    hr = Column(Float)
    ar = Column(Float)
    # Referee
    referee = Column(String)
    
    # Pre-match and post-match ELO tracking
    home_elo_pre = Column(Float)
    away_elo_pre = Column(Float)
    home_elo_post = Column(Float)
    away_elo_post = Column(Float)
    
    # Engineered features
    home_days_rest = Column(Float)
    away_days_rest = Column(Float)
    home_travel_fatigue = Column(Integer)
    away_travel_fatigue = Column(Integer)
    is_ghost_game = Column(Boolean, default=False)
    referee_regime = Column(String)

    __table_args__ = (
        UniqueConstraint("league", "date", "home_team", "away_team", name="uq_match"),
    )


class TeamElo(Base):
    __tablename__ = "team_elo"
    id = Column(Integer, primary_key=True)
    league = Column(String, index=True)
    team = Column(String, index=True)
    elo = Column(Float, default=1500.0)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("league", "team", name="uq_team_elo"),)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    league = Column(String)
    season = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    match_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    # 1X2
    prob_home = Column(Float)
    prob_draw = Column(Float)
    prob_away = Column(Float)
    # Goals / xG
    xg_home = Column(Float)
    xg_away = Column(Float)
    prob_btts = Column(Float)
    prob_over_2_5 = Column(Float)
    prob_over_3_5 = Column(Float)
    # Corners
    exp_home_corners = Column(Float)
    exp_away_corners = Column(Float)
    prob_corners_over_9_5 = Column(Float)
    prob_corners_over_10_5 = Column(Float)
    prob_corners_over_11_5 = Column(Float)
    # Fouls
    exp_home_fouls = Column(Float)
    exp_away_fouls = Column(Float)
    prob_fouls_over_20 = Column(Float)
    prob_fouls_over_25 = Column(Float)


class Fixture(Base):
    __tablename__ = "fixtures"
    id = Column(Integer, primary_key=True)
    external_id = Column(Integer, index=True, nullable=True)
    league = Column(String, index=True)
    season = Column(String, index=True)
    matchday = Column(Integer, nullable=True)
    kickoff_utc = Column(DateTime, index=True)
    kickoff_local = Column(String, nullable=True)
    home_team = Column(String, index=True)
    away_team = Column(String, index=True)
    home_days_rest = Column(Float, nullable=True)
    away_days_rest = Column(Float, nullable=True)
    venue = Column(String, nullable=True)
    status = Column(String, default="SCHEDULED")
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("league", "home_team", "away_team", "kickoff_utc", name="uq_fixture"),
    )


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    bets = relationship("Bet", back_populates="user")


class Bet(Base):
    __tablename__ = "bets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    match_date = Column(DateTime)
    league = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    market = Column(String)      # e.g. "1X2", "BTTS", "Over 2.5", "Corners O9.5"
    selection = Column(String)   # e.g. "Home", "Yes", "Over", "Under"
    odds = Column(Float)
    stake = Column(Float)
    result = Column(String, nullable=True)  # "WON" / "LOST" / "VOID" / null (pending)
    profit_loss = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    user = relationship("User", back_populates="bets")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Database initialized at {DB_PATH}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
