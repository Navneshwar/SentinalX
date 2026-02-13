"""
Feature Extractor Module

Transforms raw interaction events (timestamps only) into numerical features.
No content (characters, window titles) is ever accessed or stored.
All features are derived purely from timing and motion metadata.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple, Optional
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from shared.models import (
    BaseEvent,
    KeystrokeEvent,
    MouseEvent,
    FocusEvent,
    IdleEvent,
    EventType,
)


@dataclass
class FeatureVector:
    """
    Container for all behavioral features extracted from a window of events.
    Used as input to baseline builder and anomaly detectors.
    """
    avg_typing_speed: float = 0.0      # Keystrokes per minute
    avg_idle_duration: float = 0.0     # Seconds per idle event
    focus_loss_count: int = 0          # Number of focus lost events
    avg_mouse_speed: float = 0.0       # Pixels per second
    inter_key_interval: float = 0.0    # Average time between keystrokes (seconds)
    window_start: float = 0.0
    window_end: float = 0.0
    key_press_count: int = 0           # ADD THIS - count of key presses in window


class FeatureExtractor:
    """
    Maintains a sliding window of interaction events and computes
    aggregate features on request.
    """

    def __init__(self, window_duration: float = 30.0):
        """
        Args:
            window_duration: Length of the sliding time window (seconds).
                             Features are computed over this lookback period.
        """
        self.window_duration = window_duration
        self._event_buffer: deque[BaseEvent] = deque()
        logger.info(f"FeatureExtractor initialized with {window_duration}s window")

    def add_event(self, event: BaseEvent) -> None:
        """
        Insert a new event into the buffer.
        """
        if not self._event_buffer or event.timestamp >= self._event_buffer[-1].timestamp:
            self._event_buffer.append(event)
        else:
            # Rare out-of-order – insert in correct position
            for i, e in enumerate(self._event_buffer):
                if event.timestamp < e.timestamp:
                    self._event_buffer.insert(i, event)
                    break

    def _prune_buffer(self, current_time: float) -> None:
        """
        Remove events older than window_duration from the buffer.
        """
        cutoff = current_time - self.window_duration
        while self._event_buffer and self._event_buffer[0].timestamp < cutoff:
            self._event_buffer.popleft()

    def compute_features(self, current_time: Optional[float] = None) -> FeatureVector:
        """
        Compute feature vector from events in the current sliding window.
        """
        if current_time is None:
            current_time = time.time()

        self._prune_buffer(current_time)
        window_events = list(self._event_buffer)
        
        # Debug: print event types in window
        event_types = {}
        for ev in window_events:
            event_types[ev.type] = event_types.get(ev.type, 0) + 1
        
        if window_events:
            logger.debug(f"Window events: {event_types}")

        fv = FeatureVector()
        fv.window_start = current_time - self.window_duration
        fv.window_end = current_time

        # --- KEYSTROKE FEATURES - FIXED ---
        press_timestamps = []
        for ev in window_events:
            # Check for KEY_PRESS events
            if hasattr(ev, 'type') and ev.type == EventType.KEY_PRESS:
                press_timestamps.append(ev.timestamp)
                logger.debug(f"Found KEY_PRESS at {ev.timestamp}")

        fv.key_press_count = len(press_timestamps)
        
        if len(press_timestamps) >= 2:
            # Inter‑key interval: time between consecutive key presses
            intervals = [press_timestamps[i+1] - press_timestamps[i] for i in range(len(press_timestamps)-1)]
            fv.inter_key_interval = sum(intervals) / len(intervals)
            
            # Typing speed: keystrokes per minute
            window_len = current_time - fv.window_start
            if window_len > 0:
                fv.avg_typing_speed = (len(press_timestamps) / window_len) * 60
                logger.debug(f"Typing speed: {fv.avg_typing_speed:.1f} keys/min from {len(press_timestamps)} presses")
        else:
            fv.inter_key_interval = 0.0
            fv.avg_typing_speed = 0.0
            if press_timestamps:
                logger.debug(f"Only {len(press_timestamps)} key press, need 2+ for speed")

        # --- Idle duration ---
        idle_durations = []
        for ev in window_events:
            if isinstance(ev, IdleEvent) or (hasattr(ev, 'type') and ev.type == EventType.IDLE_PERIOD):
                if hasattr(ev, 'duration'):
                    idle_durations.append(ev.duration)
        fv.avg_idle_duration = sum(idle_durations) / len(idle_durations) if idle_durations else 0.0

        # --- Focus loss count ---
        focus_loss_count = 0
        for ev in window_events:
            if hasattr(ev, 'type') and ev.type == EventType.FOCUS_LOST:
                focus_loss_count += 1
        fv.focus_loss_count = focus_loss_count

        # --- Mouse speed ---
        mouse_positions = []
        for ev in window_events:
            if hasattr(ev, 'type') and ev.type == EventType.MOUSE_MOVE:
                if hasattr(ev, 'x') and hasattr(ev, 'y'):
                    mouse_positions.append((ev.timestamp, ev.x, ev.y))

        if len(mouse_positions) >= 2:
            total_distance = 0.0
            for i in range(len(mouse_positions)-1):
                _, x1, y1 = mouse_positions[i]
                _, x2, y2 = mouse_positions[i+1]
                dx = x2 - x1
                dy = y2 - y1
                total_distance += math.sqrt(dx*dx + dy*dy)

            time_span = mouse_positions[-1][0] - mouse_positions[0][0]
            if time_span > 0:
                fv.avg_mouse_speed = total_distance / time_span
        else:
            fv.avg_mouse_speed = 0.0

        return fv

    def clear(self) -> None:
        """Reset the event buffer."""
        self._event_buffer.clear()
        logger.info("FeatureExtractor cleared")