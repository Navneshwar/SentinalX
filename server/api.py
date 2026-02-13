# server/api.py
"""
FastAPI Backend API Module

Exposes a single REST endpoint POST /risk which accepts a risk score and
metadata, performs lightweight validation, and stores the record in SQLite.
CORS is enabled to allow requests from the Streamlit dashboard.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from shared.models import RiskData, RiskResponse
from server.database import SessionLocal, engine, Base, RiskRecord
from server.anomaly_validator import AnomalyValidator

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SentinelX Risk API", version="1.0.0")

# CORS – allow dashboard origin (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

validator = AnomalyValidator()


def get_db():
    """Dependency to obtain a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/risk", response_model=RiskResponse)
async def receive_risk(payload: RiskData, db: Session = Depends(get_db)):
    """
    Accept a risk score and associated metadata.

    Steps:
    1. Validate the incoming data using statistical rules.
    2. If validation passes, store in SQLite.
    3. Return a confirmation response.

    Privacy: no raw keystrokes or personally identifiable information
    is ever transmitted or stored.
    """
    # Statistical validation
    is_valid, reason = validator.validate(payload)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    # Create database record
    record = RiskRecord(
        timestamp=payload.timestamp,
        risk_score=payload.risk_score,
        anomaly_scores=payload.anomaly_scores.model_dump_json(),  # store as JSON
        session_id=payload.session_id,
        validated=True
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return RiskResponse(
        received=True,
        record_id=record.id,
        message="Risk data stored successfully"
    )


@app.get("/health")
async def health_check():
    """Simple health endpoint."""
    return {"status": "healthy"}
