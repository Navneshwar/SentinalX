# server/risk_aggregator.py
"""
Risk Aggregator Module

Collects risk scores from multiple validation events and can compute
aggregate statistics per session. For this simplified version, it acts
as a lightweight passthrough and logging utility. In a production system,
this would feed into a time‑series database or analytics pipeline.

Privacy: Only aggregated numerical data is handled – no raw events.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional
from datetime import datetime
from shared.models import RiskData

logger = logging.getLogger(__name__)


class RiskAggregator:
    """
    In‑memory aggregator of risk scores per session.
    Note: Data is not persisted across server restarts.
    For production, use Redis or a time‑series DB.
    """

    def __init__(self):
        self._session_risk_history: Dict[str, List[float]] = defaultdict(list)
        self._session_anomaly_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"idle_burst": 0, "focus_instability": 0, "behavioral_drift": 0}
        )

    def add_risk_data(self, risk_data: RiskData) -> None:
        """
        Incorporate a new risk score into the aggregator.
        """
        session_id = risk_data.session_id
        self._session_risk_history[session_id].append(risk_data.risk_score)

        # Count anomalies (score > threshold, e.g., > 50)
        anomaly = risk_data.anomaly_scores
        if anomaly.idle_burst > 50:
            self._session_anomaly_counts[session_id]["idle_burst"] += 1
        if anomaly.focus_instability > 50:
            self._session_anomaly_counts[session_id]["focus_instability"] += 1
        if anomaly.behavioral_drift > 50:
            self._session_anomaly_counts[session_id]["behavioral_drift"] += 1

        logger.debug(f"Aggregated risk for session {session_id}: {risk_data.risk_score}")

    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Return aggregated metrics for a given session.
        """
        if session_id not in self._session_risk_history:
            return None

        history = self._session_risk_history[session_id]
        if not history:
            return None

        return {
            "session_id": session_id,
            "risk_count": len(history),
            "average_risk": sum(history) / len(history),
            "max_risk": max(history),
            "min_risk": min(history),
            "anomaly_counts": self._session_anomaly_counts[session_id],
        }

    def reset_session(self, session_id: str) -> None:
        """Clear all data for a given session."""
        if session_id in self._session_risk_history:
            del self._session_risk_history[session_id]
        if session_id in self._session_anomaly_counts:
            del self._session_anomaly_counts[session_id]
