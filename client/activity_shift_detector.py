"""
Activity Shift Detector Module

Implements three anomaly detection rules based purely on deviation from the
behavioral baseline. All rules use only numerical aggregates; no raw data
is accessed.

Each rule produces a normalized anomaly score (0–100). The overall anomaly
score is the maximum of the three individual scores (worst-case detection).

Real-world detection logic:
- Idle Burst: Long idle followed by intense typing (copy-paste behavior)
- Focus Instability: Excessive window switching (looking for answers)
- Behavioral Drift: Typing speed significantly changes (different person typing)
"""

from typing import Optional
from dataclasses import dataclass
import time
import logging

from client.baseline_builder import BaselineProfile
from client.feature_extractor import FeatureVector

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyScores:
    """
    Container for individual anomaly rule scores and the overall score.
    All scores are 0–100 where:
    0-30: Normal behavior
    30-60: Suspicious behavior
    60-100: High-risk anomaly
    """
    idle_burst: float = 0.0      # Copy-paste / external help indicator
    focus_instability: float = 0.0  # Tab switching / alt-tabbing
    behavioral_drift: float = 0.0   # Different person typing
    overall: float = 0.0         # Max of three


class ActivityShiftDetector:
    """
    Compares current feature vector against the baseline and computes
    anomaly scores using three hard‑coded rules.
    
    Features:
    - Idle-to-Burst: Detects possible copy-paste (idle then sudden typing)
    - Focus Instability: Detects window/tab switching
    - Behavioral Drift: Detects change in typing pattern
    """
    
    def __init__(self, baseline: Optional[BaselineProfile] = None):
        """
        Args:
            baseline: Pre‑computed behavioral baseline. Can be set later via
                      the `baseline` property.
        """
        self._baseline = baseline
        
        # Tracking for anomaly history (to avoid alert fatigue)
        self._recent_scores = []
        self._max_history = 10
        
        # Dynamic thresholds (can be adjusted)
        self.idle_multiplier = 1.2      # Idle threshold multiplier
        self.typing_speed_multiplier = 1.3  # Typing burst threshold
        self.focus_rate_multiplier = 1.5    # Focus instability threshold
        self.drift_threshold = 0.3           # 30% deviation threshold
        
        # Score normalization factors
        self.idle_burst_scale = 70.0    # Max score for idle burst
        self.focus_scale = 70.0          # Max score for focus instability
        self.drift_scale = 70.0          # Max score for behavioral drift
        
        logger.info("ActivityShiftDetector initialized with real detection logic")

    @property
    def baseline(self) -> Optional[BaselineProfile]:
        return self._baseline

    @baseline.setter
    def baseline(self, value: BaselineProfile) -> None:
        self._baseline = value
        logger.info(f"Baseline set: typing={value.avg_typing_speed:.1f}, "
                   f"idle={value.avg_idle_duration:.2f}s, "
                   f"focus={value.avg_focus_rate:.2f}/min")

    def compute_scores(self, features: FeatureVector) -> AnomalyScores:
        """
        Evaluate all three anomaly rules against the current features.
        
        Args:
            features: FeatureVector from the feature extractor.
            
        Returns:
            AnomalyScores object with individual rule scores and overall score.
        """
        if self._baseline is None:
            # No baseline available – cannot detect shifts
            logger.debug("No baseline available, returning zeros")
            return AnomalyScores()

        scores = AnomalyScores()
        
        # Apply all three detection rules
        scores.idle_burst = self._detect_idle_burst(features)
        scores.focus_instability = self._detect_focus_instability(features)
        scores.behavioral_drift = self._detect_behavioral_drift(features)
        
        # Overall score is maximum of the three (worst-case)
        scores.overall = max(
            scores.idle_burst, 
            scores.focus_instability, 
            scores.behavioral_drift
        )
        
        # Update history
        self._recent_scores.append(scores.overall)
        if len(self._recent_scores) > self._max_history:
            self._recent_scores.pop(0)
        
        # Log if significant anomaly detected
        if scores.overall > 60:
            logger.warning(f"HIGH RISK DETECTED: overall={scores.overall:.1f}, "
                          f"idle_burst={scores.idle_burst:.1f}, "
                          f"focus={scores.focus_instability:.1f}, "
                          f"drift={scores.behavioral_drift:.1f}")
        elif scores.overall > 30:
            logger.info(f"MEDIUM RISK: overall={scores.overall:.1f}")
        
        return scores

    def _detect_idle_burst(self, features: FeatureVector) -> float:
        """
        Rule A: Idle-to-Burst Anomaly
        Detects when user is idle for long period then suddenly types rapidly.
        This often indicates copy-pasting or external help.
        
        Logic:
        1. Check if idle duration exceeds baseline by threshold
        2. Check if typing speed exceeds baseline by threshold
        3. Score scales with how extreme the deviation is
        
        Returns:
            Score 0-100 where higher = more anomalous
        """
        # Calculate idle threshold (how long is "too long" idle)
        idle_threshold = self._baseline.avg_idle_duration * self.idle_multiplier
        
        # Check if current idle duration exceeds threshold
        if features.avg_idle_duration > idle_threshold:
            # Now check if typing speed is significantly higher than baseline
            typing_threshold = self._baseline.avg_typing_speed * self.typing_speed_multiplier
            
            if features.avg_typing_speed > typing_threshold:
                # Calculate how extreme the typing burst is
                ratio = features.avg_typing_speed / self._baseline.avg_typing_speed
                
                # Score formula: (ratio - threshold) * scale factor
                # Example: threshold=1.3, ratio=2.0 → (0.7) * 100 = 70
                raw_score = (ratio - self.typing_speed_multiplier) * 100.0
                
                # Cap at max score and ensure non-negative
                score = min(self.idle_burst_scale, max(0.0, raw_score))
                
                if score > 30:
                    logger.debug(f"Idle burst detected: idle={features.avg_idle_duration:.2f}s, "
                                f"typing_ratio={ratio:.2f}, score={score:.1f}")
                
                return score
        
        return 0.0

    def _detect_focus_instability(self, features: FeatureVector) -> float:
        """
        Rule B: Focus Instability Anomaly
        Detects excessive window/tab switching which may indicate searching
        for answers or consulting external resources.
        
        Logic:
        1. Convert focus loss count to rate per minute
        2. Compare to baseline focus rate
        3. Score scales with excess over threshold
        
        Returns:
            Score 0-100 where higher = more anomalous
        """
        # Calculate focus rate (focus losses per minute)
        window_duration = features.window_end - features.window_start
        if window_duration > 0:
            focus_rate = features.focus_loss_count * (60.0 / window_duration)
        else:
            focus_rate = 0.0

        # Check if focus rate exceeds baseline by threshold
        focus_threshold = self._baseline.avg_focus_rate * self.focus_rate_multiplier
        
        if focus_rate > focus_threshold and self._baseline.avg_focus_rate > 0:
            # Calculate how excessive the focus switching is
            ratio = focus_rate / self._baseline.avg_focus_rate
            
            # Score formula: (ratio - multiplier) * scale factor
            # Example: multiplier=1.5, ratio=2.5 → (1.0) * 70 = 70
            raw_score = (ratio - self.focus_rate_multiplier) * 70.0
            
            score = min(self.focus_scale, max(0.0, raw_score))
            
            if score > 30:
                logger.debug(f"Focus instability: rate={focus_rate:.2f}/min, "
                            f"baseline={self._baseline.avg_focus_rate:.2f}/min, "
                            f"score={score:.1f}")
            
            return score
        
        return 0.0

    def _detect_behavioral_drift(self, features: FeatureVector) -> float:
        """
        Rule C: Behavioral Drift Anomaly
        Detects when typing speed significantly deviates from baseline.
        This could indicate a different person typing or significant
        change in user state (fatigue, stress, etc.).
        
        Logic:
        1. Calculate percentage deviation from baseline typing speed
        2. Compare to drift threshold
        3. Score scales with excess over threshold
        
        Returns:
            Score 0-100 where higher = more anomalous
        """
        if self._baseline.avg_typing_speed <= 0:
            return 0.0

        # Calculate absolute percentage deviation
        deviation = abs(features.avg_typing_speed - self._baseline.avg_typing_speed)
        deviation_pct = deviation / self._baseline.avg_typing_speed

        # Check if deviation exceeds threshold
        if deviation_pct > self.drift_threshold:
            # Score formula: (excess over threshold) * scale factor
            # Example: threshold=0.3, deviation=0.8 → (0.5) * 200 = 100
            raw_score = (deviation_pct - self.drift_threshold) * 200.0
            
            score = min(self.drift_scale, max(0.0, raw_score))
            
            if score > 30:
                logger.debug(f"Behavioral drift: baseline={self._baseline.avg_typing_speed:.1f}, "
                            f"current={features.avg_typing_speed:.1f}, "
                            f"deviation={deviation_pct:.2f}, score={score:.1f}")
            
            return score
        
        return 0.0

    def get_anomaly_explanation(self, scores: AnomalyScores) -> str:
        """
        Generate human-readable explanation of detected anomalies.
        Useful for dashboard and alerts.
        
        Args:
            scores: AnomalyScores object
            
        Returns:
            String explaining what triggered the anomaly
        """
        explanations = []
        
        if scores.idle_burst > 60:
            explanations.append("🔴 CRITICAL: Extreme typing burst after idle - possible copy-paste")
        elif scores.idle_burst > 30:
            explanations.append("🟠 WARNING: Unusual typing pattern after idle")
            
        if scores.focus_instability > 60:
            explanations.append("🔴 CRITICAL: Excessive window/tab switching")
        elif scores.focus_instability > 30:
            explanations.append("🟠 WARNING: Frequent focus changes")
            
        if scores.behavioral_drift > 60:
            explanations.append("🔴 CRITICAL: Typing speed drastically changed")
        elif scores.behavioral_drift > 30:
            explanations.append("🟠 WARNING: Typing pattern shifted")
            
        if not explanations:
            return "Normal behavior detected"
            
        return " | ".join(explanations)

    def reset(self) -> None:
        """Reset detector state (keep baseline but clear history)."""
        self._recent_scores.clear()
        logger.info("Detector history reset")


# For testing the detector directly
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 TESTING ACTIVITY SHIFT DETECTOR")
    print("="*60)
    
    # Create a sample baseline
    from client.baseline_builder import BaselineProfile
    
    baseline = BaselineProfile(
        avg_typing_speed=200.0,    # 200 keys/min
        avg_idle_duration=2.0,      # 2 seconds average idle
        avg_focus_rate=0.5          # 0.5 focus losses per minute
    )
    
    detector = ActivityShiftDetector(baseline)
    
    # Test normal behavior
    print("\n📊 Testing NORMAL behavior:")
    normal_features = FeatureVector(
        avg_typing_speed=210.0,     # Slightly above baseline
        avg_idle_duration=2.2,       # Slightly above baseline
        focus_loss_count=1,          # 1 focus loss in window
        window_start=time.time() - 30,
        window_end=time.time()
    )
    
    scores = detector.compute_scores(normal_features)
    print(f"   Idle Burst: {scores.idle_burst:.1f}")
    print(f"   Focus Instability: {scores.focus_instability:.1f}")
    print(f"   Behavioral Drift: {scores.behavioral_drift:.1f}")
    print(f"   Overall: {scores.overall:.1f}")
    print(f"   Explanation: {detector.get_anomaly_explanation(scores)}")
    
    # Test IDLE BURST anomaly
    print("\n⚠️ Testing IDLE BURST anomaly:")
    idle_burst_features = FeatureVector(
        avg_typing_speed=400.0,     # 2x baseline (typing burst)
        avg_idle_duration=5.0,       # 2.5x baseline (long idle)
        focus_loss_count=0,
        window_start=time.time() - 30,
        window_end=time.time()
    )
    
    scores = detector.compute_scores(idle_burst_features)
    print(f"   Idle Burst: {scores.idle_burst:.1f}")
    print(f"   Explanation: {detector.get_anomaly_explanation(scores)}")
    
    # Test FOCUS INSTABILITY anomaly
    print("\n⚠️ Testing FOCUS INSTABILITY anomaly:")
    focus_features = FeatureVector(
        avg_typing_speed=200.0,      # Normal typing
        avg_idle_duration=1.5,        # Normal idle
        focus_loss_count=15,          # 15 focus losses in 30s = 30/min (60x baseline!)
        window_start=time.time() - 30,
        window_end=time.time()
    )
    
    scores = detector.compute_scores(focus_features)
    print(f"   Focus Instability: {scores.focus_instability:.1f}")
    print(f"   Explanation: {detector.get_anomaly_explanation(scores)}")
    
    # Test BEHAVIORAL DRIFT anomaly
    print("\n⚠️ Testing BEHAVIORAL DRIFT anomaly:")
    drift_features = FeatureVector(
        avg_typing_speed=50.0,       # 75% below baseline
        avg_idle_duration=2.0,
        focus_loss_count=0,
        window_start=time.time() - 30,
        window_end=time.time()
    )
    
    scores = detector.compute_scores(drift_features)
    print(f"   Behavioral Drift: {scores.behavioral_drift:.1f}")
    print(f"   Explanation: {detector.get_anomaly_explanation(scores)}")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)