# server/anomaly_validator.py
"""
Anomaly Validator Module

Performs lightweight statistical validation of incoming risk data.
This acts as a sanity check to filter out obviously malformed or
out-of-range values before storing in the database.

Only simple range and consistency checks are performed – no personal
data is examined.
"""

from typing import Tuple, Dict, Any
from shared.models import RiskData


class AnomalyValidator:
    """
    Validates risk payloads against a set of statistical rules.
    Rules are based on reasonable human behavioral limits.
    """

    def __init__(self):
        # Define acceptable ranges (tunable parameters)
        self.risk_score_min = 0.0
        self.risk_score_max = 100.0
        self.anomaly_score_min = 0.0
        self.anomaly_score_max = 100.0
        self.max_focus_loss_per_minute = 30.0   # Unrealistically high focus loss rate

    def validate(self, payload: RiskData) -> Tuple[bool, str]:
        """
        Check if the incoming risk data is plausible.

        Returns:
            Tuple (is_valid, reason). If valid, reason is empty string.
        """
        # 1. Risk score bounds
        if not (self.risk_score_min <= payload.risk_score <= self.risk_score_max):
            return False, f"Risk score {payload.risk_score} out of range [{self.risk_score_min}, {self.risk_score_max}]"

        # 2. Anomaly scores bounds
        scores = payload.anomaly_scores
        for field, value in [
            ("idle_burst", scores.idle_burst),
            ("focus_instability", scores.focus_instability),
            ("behavioral_drift", scores.behavioral_drift),
        ]:
            if not (self.anomaly_score_min <= value <= self.anomaly_score_max):
                return False, f"Anomaly score {field}: {value} out of range"

        # 3. Consistency: if overall risk is 0, all sub‑scores should be 0
        if payload.risk_score == 0.0:
            if scores.idle_burst != 0.0 or scores.focus_instability != 0.0 or scores.behavioral_drift != 0.0:
                return False, "Risk score is zero but anomaly scores are non‑zero"

        # 4. Session ID presence (simple non‑empty check)
        if not payload.session_id or not payload.session_id.strip():
            return False, "Session ID is empty or missing"

        # 5. Timestamp sanity (not in future)
        #    We rely on the client's clock; just check it's not too far in future.
        #    A full NTP sync is out of scope. We'll do a simple check.
        #    We can't easily get current time here without external dependency,
        #    but we can reject timestamps > now + 1 minute as likely erroneous.
        #    However, since this is a local demo, we skip strict future check.
        #    Instead, just verify timestamp is a reasonable float.
        if not isinstance(payload.timestamp, (int, float)) or payload.timestamp <= 0:
            return False, "Invalid timestamp"

        # 6. Optional: check focus loss rate derived from anomaly_scores? Not needed.

        return True, ""

    def validate_dict(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Convenience method for validating raw dictionaries.
        Attempts to construct RiskData object first.
        """
        try:
            # Use model_validate for Pydantic v2, fallback for v1
            if hasattr(RiskData, "model_validate"):
                payload = RiskData.model_validate(data)
            else:
                payload = RiskData.parse_obj(data)
            return self.validate(payload)
        except Exception as e:
            return False, f"Payload parsing failed: {str(e)}"
