"""
Baseline Builder Module

Establishes a behavioral baseline for a user session by observing the first
N minutes of interaction. Only numerical aggregates are stored – no raw events
or identifying information are retained.
"""

from typing import List, Optional
from dataclasses import dataclass
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BaselineProfile:
    """
    Immutable snapshot of a user's "normal" behavior.
    All fields are aggregated numerical values.
    """
    avg_typing_speed: float      # Keystrokes per minute
    avg_idle_duration: float     # Seconds
    avg_focus_rate: float        # Focus losses per minute


class BaselineBuilder:
    """
    Accumulates feature vectors during the initial calibration phase.
    After enough data is collected, it computes and freezes the baseline.
    """

    def __init__(self, calibration_duration: float = 180.0):
        """
        Args:
            calibration_duration: Length of baseline observation period (seconds).
                                  Default 3 minutes (180 seconds).
        """
        self.calibration_duration = calibration_duration
        self._feature_history: List['FeatureVector'] = []
        self._baseline: Optional[BaselineProfile] = None
        self._calibration_start: Optional[float] = None
        self._min_samples_required = 5  # Need at least 5 samples before calibrating

    def start_calibration(self, start_time: float) -> None:
        """
        Begin a new calibration period. Any previous baseline and history are cleared.
        """
        self._feature_history.clear()
        self._baseline = None
        self._calibration_start = start_time
        logger.info(f"Calibration started at {start_time}")

    def update(self, features: 'FeatureVector', current_time: float) -> None:
        """
        Feed a new feature vector into the builder.

        Args:
            features: FeatureVector computed from the current sliding window.
            current_time: Timestamp of the vector (window end time).
        """
        if self._baseline is not None:
            # Baseline already built – ignore further updates.
            return

        if self._calibration_start is None:
            # Implicitly start calibration on first update.
            self.start_calibration(current_time)
            return

        # Store the feature vector if we are still within calibration period
        time_in_calibration = current_time - self._calibration_start
        
        if time_in_calibration <= self.calibration_duration:
            self._feature_history.append(features)
            logger.debug(f"Calibration: {time_in_calibration:.1f}s, samples: {len(self._feature_history)}")
            
            # Check if we have enough samples AND enough time has passed
            if (len(self._feature_history) >= self._min_samples_required and 
                time_in_calibration >= self.calibration_duration * 0.5):  # At least 50% of calibration time
                # Only calibrate if we have some typing data
                if self._has_typing_data():
                    self._build_baseline()
        else:
            # Time is up – build the baseline
            self._build_baseline()

    def _has_typing_data(self) -> bool:
        """Check if we have any typing data in the history."""
        for fv in self._feature_history:
            # Check both avg_typing_speed and key_press_count if available
            if hasattr(fv, 'avg_typing_speed') and fv.avg_typing_speed > 5.0:
                return True
            if hasattr(fv, 'key_press_count') and fv.key_press_count > 2:
                return True
        return False

    def _build_baseline(self) -> None:
        """
        Compute baseline profile from all collected feature vectors.
        After this method is called, the internal history is cleared
        and the baseline is frozen.
        """
        if not self._feature_history:
            # No data – set fallback values
            logger.warning("No feature history, using fallback baseline")
            self._baseline = BaselineProfile(
                avg_typing_speed=150.0,
                avg_idle_duration=2.0,
                avg_focus_rate=0.5
            )
            return

        # DEBUG: Print sample of feature vectors
        for i, fv in enumerate(self._feature_history[:5]):
            key_count = getattr(fv, 'key_press_count', 0)
            logger.info(f"Sample {i}: typing={fv.avg_typing_speed:.1f}, key_press_count={key_count}")

        # Filter out windows with zero typing for baseline calculation
        valid_features = []
        for fv in self._feature_history:
            if fv.avg_typing_speed > 0:
                valid_features.append(fv)
            elif hasattr(fv, 'key_press_count') and fv.key_press_count > 0:
                valid_features.append(fv)
        
        if not valid_features:
            logger.warning(f"No typing detected during calibration. Total samples: {len(self._feature_history)}")
            # If we have enough samples but no typing, still calibrate with what we have
            if len(self._feature_history) >= 10:
                logger.warning("Using all samples even with no typing")
                valid_features = self._feature_history
            else:
                logger.info("Not enough samples yet, continuing calibration...")
                return

        # Aggregate all features
        total_typing_speed = 0.0
        total_idle_duration = 0.0
        total_focus_loss = 0.0
        valid_count = len(valid_features)  # FIXED: Use valid_count instead of window_count

        for fv in valid_features:
            total_typing_speed += fv.avg_typing_speed
            total_idle_duration += fv.avg_idle_duration
            total_focus_loss += fv.focus_loss_count

        # Compute averages - FIXED: Use valid_count
        avg_typing_speed = total_typing_speed / valid_count if valid_count > 0 else 150.0
        avg_idle_duration = total_idle_duration / valid_count if valid_count > 0 else 2.0

        # Focus rate = focus losses per minute
        if valid_count > 0:
            avg_focus_per_window = total_focus_loss / valid_count
            # Estimate window duration from the first feature
            window_duration = 30.0  # fallback
            if hasattr(valid_features[0], 'window_end') and hasattr(valid_features[0], 'window_start'):
                window_duration = valid_features[0].window_end - valid_features[0].window_start
                if window_duration <= 0:
                    window_duration = 30.0
            avg_focus_rate = avg_focus_per_window * (60.0 / window_duration)
        else:
            avg_focus_rate = 0.5

        self._baseline = BaselineProfile(
            avg_typing_speed=avg_typing_speed,
            avg_idle_duration=avg_idle_duration,
            avg_focus_rate=avg_focus_rate
        )

        # Log the baseline
        logger.info(f"✅ Baseline built after {len(self._feature_history)} samples")
        logger.info(f"   - Avg typing speed: {avg_typing_speed:.1f} keys/min")
        logger.info(f"   - Avg idle duration: {avg_idle_duration:.2f}s")
        logger.info(f"   - Avg focus rate: {avg_focus_rate:.2f}/min")

        # Free memory
        self._feature_history.clear()

    @property
    def baseline(self) -> Optional[BaselineProfile]:
        """Return the frozen baseline profile, or None if calibration is not finished."""
        return self._baseline

    @property
    def is_calibrated(self) -> bool:
        """Check if baseline has been built."""
        return self._baseline is not None

    @property
    def calibration_progress(self) -> float:
        """Return calibration progress as percentage."""
        if self._calibration_start is None:
            return 0.0
        if self._baseline is not None:
            return 100.0
        elapsed = time.time() - self._calibration_start
        return min(100.0, (elapsed / self.calibration_duration) * 100.0)

    def reset(self) -> None:
        """Force reset – discard baseline and history."""
        self._feature_history.clear()
        self._baseline = None
        self._calibration_start = None
        logger.info("Baseline builder reset")