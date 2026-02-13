# shared/models.py
"""
Shared Data Models (Pydantic)

Defines the data structures exchanged between client, server, and dashboard.
All models use only numerical metadata and session identifiers.
NO raw keystrokes, characters, or personally identifiable information.

These models are used for:
- Serialization/deserialization in the API
- Type safety in client modules
- Validation in the anomaly validator
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    """Types of interaction events – timing only."""
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    MOUSE_MOVE = "mouse_move"
    FOCUS_LOST = "focus_lost"
    FOCUS_GAINED = "focus_gained"
    IDLE_PERIOD = "idle_period"


class BaseEvent(BaseModel):
    """
    Abstract base for all interaction events.
    Contains only timestamp and event type.
    """
    timestamp: float = Field(..., description="Unix timestamp (seconds)")
    type: EventType = Field(..., description="Event classification")


class KeystrokeEvent(BaseEvent):
    """
    Keystroke event – press or release.
    NO key character, NO scan code, NO key identifier.
    Only timestamp and type.
    """
    pass


class MouseEvent(BaseEvent):
    """Mouse movement – only coordinates, no window info."""
    x: int = Field(..., description="X coordinate (screen)")
    y: int = Field(..., description="Y coordinate (screen)")


class FocusEvent(BaseEvent):
    """
    Window focus change – no window title, no application name.
    Only whether focus was lost or gained.
    """
    lost_focus: bool = Field(..., description="True if focus lost, False if gained")


class IdleEvent(BaseEvent):
    """Idle period – duration only."""
    duration: float = Field(..., description="Idle duration in seconds")


# ----------------------------------------------------------------------
# Risk & anomaly models (client → server)
# ----------------------------------------------------------------------

class AnomalyScores(BaseModel):
    """Individual anomaly rule scores and overall score (0–100)."""
    idle_burst: float = Field(0.0, ge=0.0, le=100.0)
    focus_instability: float = Field(0.0, ge=0.0, le=100.0)
    behavioral_drift: float = Field(0.0, ge=0.0, le=100.0)
    overall: float = Field(0.0, ge=0.0, le=100.0)


class RiskData(BaseModel):
    """
    Payload sent to POST /risk.
    Contains only risk score, anomaly scores, session ID, and timestamp.
    """
    timestamp: float = Field(..., description="Unix timestamp of risk calculation")
    risk_score: float = Field(..., ge=0.0, le=100.0)
    anomaly_scores: AnomalyScores
    session_id: str = Field(..., description="Unique session identifier (UUID)")
    # Optional metadata (for debugging)
    source: Optional[str] = "sentinelx-client"


class RiskResponse(BaseModel):
    """Response from the server after storing risk data."""
    received: bool
    record_id: Optional[int] = None
    message: str
