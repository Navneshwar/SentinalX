"""
Risk Engine Module

Combines anomaly scores from the activity shift detector into a single
risk score using a weighted formula. Applies a moving average to smooth
short‑term fluctuations. The final risk score is a float in the range 0–100.
"""

from collections import deque
from typing import Deque, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Aggregates anomaly scores, applies weighting, and maintains a smoothed
    moving average of the risk level.
    """

    def __init__(self, smoothing_window: int = 3):  # Reduced from 5 to 3
        """
        Args:
            smoothing_window: Number of recent risk scores to average.
                              Smaller values = more responsive but less smooth.
        """
        self.smoothing_window = smoothing_window
        self._risk_history: Deque[float] = deque(maxlen=smoothing_window)
        self._last_raw_risk: float = 0.0
        self._last_smoothed_risk: float = 0.0

        # Weight configuration - more aggressive detection
        self.weight_idle_burst = 0.4
        self.weight_focus_instability = 0.35
        self.weight_behavioral_drift = 0.25

    def compute_risk(self, anomaly_scores) -> float:
        """
        Calculate the weighted risk score from the given anomaly scores,
        update the moving average, and return the smoothed value.

        Args:
            anomaly_scores: AnomalyScores object containing individual rule scores.

        Returns:
            Smoothed risk score (0–100).
        """
        # Log incoming anomaly scores
        logger.debug(f"Anomaly scores - I:{anomaly_scores.idle_burst:.1f} "
                    f"F:{anomaly_scores.focus_instability:.1f} "
                    f"D:{anomaly_scores.behavioral_drift:.1f}")

        # Weighted combination of the three anomaly scores
        raw_risk = (
            self.weight_idle_burst * anomaly_scores.idle_burst +
            self.weight_focus_instability * anomaly_scores.focus_instability +
            self.weight_behavioral_drift * anomaly_scores.behavioral_drift
        )
        
        # Ensure score is within 0–100
        raw_risk = max(0.0, min(100.0, raw_risk))

        self._last_raw_risk = raw_risk

        # Update history and compute moving average
        self._risk_history.append(raw_risk)
        
        if len(self._risk_history) > 0:
            # Use weighted average - more weight on recent values
            if len(self._risk_history) == 1:
                smoothed = raw_risk
            else:
                # Give 60% weight to latest, 40% to history average
                history_avg = sum(list(self._risk_history)[:-1]) / (len(self._risk_history) - 1)
                smoothed = (0.6 * raw_risk) + (0.4 * history_avg)
        else:
            smoothed = raw_risk

        self._last_smoothed_risk = smoothed

        # Log if significant
        if raw_risk >= 60:
            logger.warning(f"🔴 HIGH RISK - Raw: {raw_risk:.1f}, Smoothed: {smoothed:.1f}")
        elif raw_risk >= 30:
            logger.info(f"🟠 MEDIUM RISK - Raw: {raw_risk:.1f}, Smoothed: {smoothed:.1f}")
        else:
            logger.debug(f"🟢 LOW RISK - Raw: {raw_risk:.1f}, Smoothed: {smoothed:.1f}")

        return smoothed

    @property
    def current_risk(self) -> float:
        """Return the most recent smoothed risk score."""
        return self._last_smoothed_risk

    @property
    def raw_risk(self) -> float:
        """Return the most recent raw (unsmoothed) risk score."""
        return self._last_raw_risk

    def reset(self) -> None:
        """Clear internal history and reset risk scores to zero."""
        self._risk_history.clear()
        self._last_raw_risk = 0.0
        self._last_smoothed_risk = 0.0
        logger.info("RiskEngine reset")