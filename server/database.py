# server/database.py
"""
Database Module

Sets up SQLite database connection using SQLAlchemy ORM.
Defines the RiskRecord table for storing validated risk scores.
Uses a simple file‑based SQLite database (sentinelx.db) for local development.

Privacy: Only aggregated risk scores and metadata are stored – no raw keystrokes,
no PII, no event streams. The session_id is a UUID generated client‑side and
does not identify the user.
"""

import os
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

# Determine database path – store in project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "sentinelx.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite engine with necessary settings for concurrency and foreign keys
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Allow FastAPI to use same thread
    echo=False  # Set to True for SQL logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class RiskRecord(Base):
    """
    Database model representing a single risk score submission.
    """
    __tablename__ = "risk_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # Unix timestamp
    risk_score = Column(Float, nullable=False)
    anomaly_scores = Column(Text, nullable=False)  # JSON string of AnomalyScores
    session_id = Column(String, nullable=False, index=True)
    validated = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RiskRecord id={self.id} session={self.session_id} risk={self.risk_score:.1f}>"


def init_db():
    """Create database tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_session_summary(db: Session, session_id: str):
    """
    Utility function to retrieve all risk records for a given session.
    Used by dashboard to display historical risk.
    """
    return db.query(RiskRecord).filter(RiskRecord.session_id == session_id).order_by(RiskRecord.timestamp).all()
