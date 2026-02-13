"""
Interaction Listener Module

Captures REAL low-level interaction metadata (timing only) without storing any
actual content (keystroke characters, window titles, etc.). Uses pynput for
cross-platform system hooks.

Privacy by design: 
- NO key characters stored
- NO window titles captured
- NO screenshots or video
- ONLY timestamps and basic metadata
"""

import threading
import time
import platform
import subprocess
import sys
from queue import Queue, Empty
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

# Import pynput for real system hooks
try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("⚠️ pynput not installed. Run: pip install pynput")

# Platform-specific imports for focus tracking
SYSTEM = platform.system()
if SYSTEM == "Darwin":
    try:
        from AppKit import NSWorkspace
        FOCUS_TRACKING_AVAILABLE = True
    except ImportError:
        FOCUS_TRACKING_AVAILABLE = False
        print("⚠️ Mac focus tracking unavailable. Run: pip install pyobjc-framework-Cocoa")
elif SYSTEM == "Windows":
    try:
        import win32gui
        import win32process
        FOCUS_TRACKING_AVAILABLE = True
    except ImportError:
        FOCUS_TRACKING_AVAILABLE = False
        print("⚠️ Windows focus tracking unavailable. Run: pip install pywin32")
elif SYSTEM == "Linux":
    try:
        import Xlib
        from Xlib import X, display
        FOCUS_TRACKING_AVAILABLE = True
    except ImportError:
        FOCUS_TRACKING_AVAILABLE = False
        print("⚠️ Linux focus tracking unavailable. Run: pip install python-xlib")
else:
    FOCUS_TRACKING_AVAILABLE = False


# ============================================================================
# Shared Models (moved here to avoid circular imports)
# ============================================================================

class EventType(str, Enum):
    """Types of interaction events – timing only."""
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_SCROLL = "mouse_scroll"
    FOCUS_LOST = "focus_lost"
    FOCUS_GAINED = "focus_gained"
    IDLE_PERIOD = "idle_period"
    IDLE_END = "idle_end"


@dataclass
class BaseEvent:
    """Base class for all interaction events."""
    timestamp: float
    type: EventType


@dataclass
class KeystrokeEvent(BaseEvent):
    """Keystroke event – press or release. NO key character stored!"""
    pass


@dataclass
class MouseEvent(BaseEvent):
    """Mouse movement/click event."""
    x: int
    y: int
    button: Optional[str] = None  # Only for clicks, NULL for moves


@dataclass
class FocusEvent(BaseEvent):
    """Window focus change – no window title stored!"""
    lost_focus: bool  # True if focus lost, False if gained
    app_name: Optional[str] = None  # Optional: app name without details


@dataclass
class IdleEvent(BaseEvent):
    """Idle period – duration only."""
    duration: float  # seconds


# ============================================================================
# Abstract Base Class
# ============================================================================

class InteractionListener:
    """Abstract base class for all interaction listeners."""

    def start(self) -> None:
        """Start capturing interaction events."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop capturing and release any system hooks."""
        raise NotImplementedError

    def get_events(self, timeout: float = 0.1) -> List[BaseEvent]:
        """
        Retrieve all events that have been buffered since the last call.

        Args:
            timeout: Maximum time (seconds) to wait for events.

        Returns:
            List of captured events (may be empty).
        """
        raise NotImplementedError


# ============================================================================
# REAL Implementation (Production)
# ============================================================================

class RealInteractionListener(InteractionListener):
    """
    REAL system interaction listener using pynput hooks.
    Captures actual keyboard, mouse, and focus events from the system.
    
    Features:
    - Real keyboard press/release timings (NO content!)
    - Real mouse movement and clicks
    - Idle period detection
    - Window focus tracking (optional, no window titles)
    - Cross-platform support
    
    Privacy:
    - No key characters, codes, or identifiers
    - No window titles or application names (optional)
    - No screenshots or video
    """
    
    def __init__(self, track_focus: bool = True, idle_threshold: float = 3.0):
        """
        Initialize the real interaction listener.
        
        Args:
            track_focus: Whether to track window focus changes
            idle_threshold: Seconds of inactivity before considering idle
        """
        self._event_queue: Queue[BaseEvent] = Queue()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._idle_thread: Optional[threading.Thread] = None
        self._focus_thread: Optional[threading.Thread] = None
        
        # Activity tracking
        self._last_activity_time = time.time()
        self._idle_threshold = idle_threshold
        self._idle_check_interval = 0.5  # Check idle every 0.5 seconds
        self._is_idle = False
        self._idle_start_time = None
        
        # Keyboard tracking
        self._keys_pressed = 0  # Count of currently pressed keys
        self._last_key_time = 0
        
        # Mouse tracking
        self._mouse_position = (0, 0)
        self._move_counter = 0
        self._mouse_sampling_rate = 10  # Record every 10th move to avoid flooding
        
        # Focus tracking
        self._track_focus = track_focus and FOCUS_TRACKING_AVAILABLE
        self._current_focus_state = True
        self._last_focus_check = 0
        self._focus_check_interval = 1.0  # Check focus every second
        
        # Platform info
        self._os_name = SYSTEM
        self._setup_platform_specific()
        
        print(f"🖥️ [RealListener] Initialized for {self._os_name}")
        if self._track_focus:
            print(f"✅ [RealListener] Focus tracking enabled")
        else:
            print(f"⚠️ [RealListener] Focus tracking disabled/unavailable")

    def _setup_platform_specific(self) -> None:
        """Setup platform-specific components."""
        if self._os_name == "Windows":
            self._setup_windows()
        elif self._os_name == "Darwin":
            self._setup_mac()
        elif self._os_name == "Linux":
            self._setup_linux()

    def _setup_windows(self) -> None:
        """Windows-specific setup."""
        try:
            import win32gui
            import win32process
            self._windows_utils = True
        except:
            self._windows_utils = False

    def _setup_mac(self) -> None:
        """Mac-specific setup."""
        try:
            from AppKit import NSWorkspace
            self._workspace = NSWorkspace.sharedWorkspace()
        except:
            pass

    def _setup_linux(self) -> None:
        """Linux-specific setup."""
        try:
            from Xlib import display
            self._x_display = display.Display()
        except:
            pass

    def start(self) -> None:
        """Start capturing real system events."""
        if not PYNPUT_AVAILABLE:
            print("❌ [RealListener] Cannot start: pynput not installed")
            print("   Run: pip install pynput")
            return
            
        if self._running:
            return
            
        self._running = True
        print("\n" + "="*50)
        print("🎯 STARTING REAL INTERACTION CAPTURE")
        print("="*50)
        
        # Start the main pynput listeners in a separate thread
        self._listener_thread = threading.Thread(target=self._run_listeners, daemon=True)
        self._listener_thread.start()
        
        # Start idle detection thread
        self._idle_thread = threading.Thread(target=self._check_idle, daemon=True)
        self._idle_thread.start()
        
        # Start focus tracking thread if enabled
        if self._track_focus:
            self._focus_thread = threading.Thread(target=self._track_focus_changes, daemon=True)
            self._focus_thread.start()
        
        print("✅ [RealListener] Real interaction capture started")
        print("   - Monitoring keyboard (timing only, NO content)")
        print("   - Monitoring mouse (movement + clicks)")
        print("   - Tracking idle periods")
        if self._track_focus:
            print("   - Tracking window focus changes")
        print("="*50 + "\n")

    def _run_listeners(self) -> None:
        """Run the pynput listeners in a separate thread."""
        try:
            # Keyboard listener
            def on_press(key):
                try:
                    now = time.time()
                    self._last_activity_time = now
                    self._keys_pressed += 1
                    self._last_key_time = now
                    
                    # Queue key press event (NO key content stored!)
                    self._event_queue.put(
                        KeystrokeEvent(
                            timestamp=now,
                            type=EventType.KEY_PRESS
                        )
                    )
                except Exception as e:
                    print(f"❌ [RealListener] Error in key press handler: {e}")

            def on_release(key):
                try:
                    now = time.time()
                    self._last_activity_time = now
                    self._keys_pressed = max(0, self._keys_pressed - 1)
                    
                    # Queue key release event
                    self._event_queue.put(
                        KeystrokeEvent(
                            timestamp=now,
                            type=EventType.KEY_RELEASE
                        )
                    )
                except Exception as e:
                    print(f"❌ [RealListener] Error in key release handler: {e}")

            # Mouse listener
            def on_move(x, y):
                try:
                    now = time.time()
                    self._last_activity_time = now
                    self._mouse_position = (x, y)
                    
                    # Sample mouse movements to avoid flooding
                    self._move_counter += 1
                    if self._move_counter % self._mouse_sampling_rate == 0:
                        self._event_queue.put(
                            MouseEvent(
                                timestamp=now,
                                type=EventType.MOUSE_MOVE,
                                x=x,
                                y=y,
                                button=None
                            )
                        )
                except Exception as e:
                    print(f"❌ [RealListener] Error in mouse move handler: {e}")

            def on_click(x, y, button, pressed):
                try:
                    now = time.time()
                    self._last_activity_time = now
                    
                    # Store mouse click events
                    self._event_queue.put(
                        MouseEvent(
                            timestamp=now,
                            type=EventType.MOUSE_CLICK,
                            x=x,
                            y=y,
                            button=str(button) if pressed else None
                        )
                    )
                except Exception as e:
                    print(f"❌ [RealListener] Error in mouse click handler: {e}")

            def on_scroll(x, y, dx, dy):
                try:
                    now = time.time()
                    self._last_activity_time = now
                    
                    self._event_queue.put(
                        MouseEvent(
                            timestamp=now,
                            type=EventType.MOUSE_SCROLL,
                            x=x,
                            y=y,
                            button=None
                        )
                    )
                except Exception as e:
                    print(f"❌ [RealListener] Error in mouse scroll handler: {e}")

            # Start listeners
            with keyboard.Listener(on_press=on_press, on_release=on_release) as kb_listener:
                with mouse.Listener(
                    on_move=on_move, 
                    on_click=on_click, 
                    on_scroll=on_scroll
                ) as mouse_listener:
                    kb_listener.join()
                    mouse_listener.join()
                    
        except Exception as e:
            print(f"❌ [RealListener] Fatal error in listener thread: {e}")
            self._running = False

    def _check_idle(self) -> None:
        """
        Background thread to detect idle periods.
        Emits IdleEvent when no activity detected for threshold duration.
        """
        while self._running:
            try:
                now = time.time()
                time_since_activity = now - self._last_activity_time
                
                if time_since_activity > self._idle_threshold and not self._is_idle:
                    # Just became idle
                    self._is_idle = True
                    self._idle_start_time = self._last_activity_time
                    
                    self._event_queue.put(
                        IdleEvent(
                            timestamp=now,
                            type=EventType.IDLE_PERIOD,
                            duration=time_since_activity
                        )
                    )
                    print(f"⏸️ [RealListener] User idle ({time_since_activity:.1f}s)")
                    
                elif time_since_activity <= self._idle_threshold and self._is_idle:
                    # Just became active again
                    self._is_idle = False
                    idle_duration = now - self._idle_start_time
                    
                    self._event_queue.put(
                        IdleEvent(
                            timestamp=now,
                            type=EventType.IDLE_END,
                            duration=idle_duration
                        )
                    )
                    print(f"▶️ [RealListener] User active again (was idle for {idle_duration:.1f}s)")
                    
                elif self._is_idle:
                    # Still idle, emit periodic updates
                    if time_since_activity - self._idle_threshold > 1.0:
                        self._event_queue.put(
                            IdleEvent(
                                timestamp=now,
                                type=EventType.IDLE_PERIOD,
                                duration=time_since_activity
                            )
                        )
                        
            except Exception as e:
                print(f"❌ [RealListener] Error in idle check: {e}")
                
            time.sleep(self._idle_check_interval)

    def _track_focus_changes(self) -> None:
        """
        Background thread to track window focus changes.
        Simplified version for Windows.
        """
        if not self._track_focus:
            return
        
        print(f"🔍 [RealListener] Starting focus tracking for {self._os_name}")
        
        # For Windows, use a simpler approach
        if self._os_name == "Windows":
            try:
                import win32gui
                import win32process
                
                last_window = None
                switch_count = 0
                
                while self._running:
                    try:
                        # Get foreground window
                        hwnd = win32gui.GetForegroundWindow()
                        window_title = win32gui.GetWindowText(hwnd)
                        
                        # Only track if window changed
                        if hwnd != last_window:
                            switch_count += 1
                            now = time.time()
                            
                            # Emit focus lost for previous window
                            if last_window is not None:
                                self._event_queue.put(
                                    FocusEvent(
                                        timestamp=now - 0.1,
                                        type=EventType.FOCUS_LOST,
                                        lost_focus=True,
                                        app_name="previous_app"
                                    )
                                )
                            
                            # Emit focus gained for new window
                            self._event_queue.put(
                                FocusEvent(
                                    timestamp=now,
                                    type=EventType.FOCUS_GAINED,
                                    lost_focus=False,
                                    app_name="browser"  # Generic for privacy
                                )
                            )
                            
                            print(f"👁️ Window switch #{switch_count}")
                            last_window = hwnd
                        
                    except Exception as e:
                        pass  # Silently ignore focus errors
                    
                    time.sleep(0.5)  # Check every 500ms
                    
            except ImportError:
                print("⚠️ win32gui not available for focus tracking")
        
        elif self._os_name == "Darwin":  # Mac
            # Simplified Mac version
            while self._running:
                time.sleep(1)
        
        else:  # Linux
            while self._running:
                time.sleep(1)
    def _get_current_focus_state(self) -> bool:
        """Check if our window currently has focus."""
        # This is simplified - in production, you'd track your own window
        # For now, assume we always have focus when app is running
        return True

    def _get_focused_app_name(self) -> Optional[str]:
        """
        Get name of currently focused application.
        Returns generic category instead of specific app name for privacy.
        """
        try:
            if self._os_name == "Windows":
                # Return generic category
                return "browser"  # Simplified
            elif self._os_name == "Darwin":
                # Return generic category
                return "browser"  # Simplified
            elif self._os_name == "Linux":
                return "browser"  # Simplified
            else:
                return None
        except:
            return None

    def stop(self) -> None:
        """Stop capturing events."""
        self._running = False
        print("\n" + "="*50)
        print("🛑 STOPPING REAL INTERACTION CAPTURE")
        print("="*50)
        
        # Wait for threads to finish
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=2.0)
        if self._idle_thread and self._idle_thread.is_alive():
            self._idle_thread.join(timeout=1.0)
        if self._focus_thread and self._focus_thread.is_alive():
            self._focus_thread.join(timeout=1.0)
            
        print("✅ [RealListener] Real interaction capture stopped")

    def get_events(self, timeout: float = 0.1) -> List[BaseEvent]:
        """
        Retrieve all events that have been buffered since the last call.
        
        Args:
            timeout: Maximum time to wait for events.
            
        Returns:
            List of captured events (may be empty).
        """
        events: List[BaseEvent] = []
        start = time.time()
        
        while (time.time() - start) < timeout:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except Empty:
                time.sleep(0.001)  # Small sleep to prevent CPU spinning
                
        return events

    def get_stats(self) -> Dict[str, Any]:
        """Get current listener statistics."""
        return {
            "running": self._running,
            "os": self._os_name,
            "idle": self._is_idle,
            "idle_duration": time.time() - self._last_activity_time if self._is_idle else 0,
            "keys_pressed": self._keys_pressed,
            "mouse_position": self._mouse_position,
            "queue_size": self._event_queue.qsize(),
            "track_focus": self._track_focus
        }


# ============================================================================
# MOCK Implementation (Testing/Development)
# ============================================================================
# ============================================================================
# MOCK Implementation (Testing/Development) - UPDATED
# ============================================================================

class MockInteractionListener(InteractionListener):
    """
    SYNTHETIC event generator for testing and development only.
    
    Generates plausible interaction patterns without real system hooks.
    Useful for:
    - Development without permissions
    - Testing UI/UX
    - Generating predictable patterns
    
    NOT for production use!
    """
    
    def __init__(
        self,
        mean_event_interval: float = 0.2,
        idle_probability: float = 0.15,
        focus_loss_probability: float = 0.02,
        typing_burst_probability: float = 0.3,
        mouse_active_probability: float = 0.5,
        # Add these new parameters to match RealInteractionListener
        track_focus: bool = False,  # Added but ignored in mock
        idle_threshold: float = 3.0,  # Added but ignored in mock
        **kwargs  # Catch any other parameters
    ):
        """
        Args:
            mean_event_interval: Average time between generated events (seconds)
            idle_probability: Probability of idle events
            focus_loss_probability: Probability of focus loss events
            typing_burst_probability: Probability of typing bursts
            mouse_active_probability: Probability of mouse movement
            track_focus: Ignored in mock (for compatibility)
            idle_threshold: Ignored in mock (for compatibility)
            **kwargs: Catch any other parameters for compatibility
        """
        self.mean_event_interval = mean_event_interval
        self.idle_probability = idle_probability
        self.focus_loss_probability = focus_loss_probability
        self.typing_burst_probability = typing_burst_probability
        self.mouse_active_probability = mouse_active_probability
        
        self._queue: Queue[BaseEvent] = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # State tracking
        self._last_event_time = time.time()
        self._in_idle = False
        self._idle_start = None
        self._keys_pressed = 0
        
        print("🤖 [MockListener] Initialized (SYNTHETIC DATA - FOR TESTING ONLY)")

    def start(self) -> None:
        """Start the mock event generator."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._generate_events, daemon=True)
        self._thread.start()
        
        print("🤖 [MockListener] Started generating synthetic events")

    def _generate_events(self) -> None:
        """Generate synthetic events in a loop."""
        import random
        
        while self._running:
            # Decide what kind of event to generate
            now = time.time()
            event_type = random.random()
            
            # Check for idle period end
            if self._in_idle:
                if random.random() < 0.3:  # 30% chance to exit idle
                    self._in_idle = False
                    idle_duration = now - self._idle_start
                    self._queue.put(
                        IdleEvent(
                            timestamp=now,
                            type=EventType.IDLE_END,
                            duration=idle_duration
                        )
                    )
                    print(f"🤖 [MockListener] Idle ended (was {idle_duration:.1f}s)")
                # If still idle, generate no other events
                else:
                    time.sleep(0.1)
                    continue
            
            # Start idle period
            if not self._in_idle and random.random() < self.idle_probability * 0.1:
                self._in_idle = True
                self._idle_start = now
                self._queue.put(
                    IdleEvent(
                        timestamp=now,
                        type=EventType.IDLE_PERIOD,
                        duration=0.0
                    )
                )
                print(f"🤖 [MockListener] Idle started")
                time.sleep(0.1)
                continue
            
            # Generate normal events
            if event_type < self.typing_burst_probability:
                # Typing burst
                num_keys = random.randint(1, 5)
                for i in range(num_keys):
                    press_time = now + (i * random.uniform(0.05, 0.15))
                    release_time = press_time + random.uniform(0.05, 0.10)
                    
                    self._queue.put(
                        KeystrokeEvent(
                            timestamp=press_time,
                            type=EventType.KEY_PRESS
                        )
                    )
                    self._queue.put(
                        KeystrokeEvent(
                            timestamp=release_time,
                            type=EventType.KEY_RELEASE
                        )
                    )
                    
            elif event_type < self.typing_burst_probability + 0.3:
                # Mouse movement
                x = random.randint(0, 1920)
                y = random.randint(0, 1080)
                self._queue.put(
                    MouseEvent(
                        timestamp=now,
                        type=EventType.MOUSE_MOVE,
                        x=x,
                        y=y,
                        button=None
                    )
                )
                
            elif event_type < self.typing_burst_probability + 0.5:
                # Mouse click
                x = random.randint(0, 1920)
                y = random.randint(0, 1080)
                self._queue.put(
                    MouseEvent(
                        timestamp=now,
                        type=EventType.MOUSE_CLICK,
                        x=x,
                        y=y,
                        button="left"
                    )
                )
                
            else:
                # Focus change
                if random.random() < 0.5:
                    self._queue.put(
                        FocusEvent(
                            timestamp=now,
                            type=EventType.FOCUS_LOST,
                            lost_focus=True,
                            app_name="other_app"
                        )
                    )
                else:
                    self._queue.put(
                        FocusEvent(
                            timestamp=now,
                            type=EventType.FOCUS_GAINED,
                            lost_focus=False,
                            app_name="exam_window"
                        )
                    )
            
            # Sleep based on mean interval
            sleep_time = random.expovariate(1.0 / self.mean_event_interval)
            time.sleep(sleep_time)

    def stop(self) -> None:
        """Stop the mock generator."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("🤖 [MockListener] Stopped")

    def get_events(self, timeout: float = 0.1) -> List[BaseEvent]:
        """Get events from the mock queue."""
        events: List[BaseEvent] = []
        start = time.time()
        
        while (time.time() - start) < timeout:
            try:
                event = self._queue.get_nowait()
                events.append(event)
            except Empty:
                time.sleep(0.01)
                
        return events

# ============================================================================
# Factory function to easily switch between implementations
# ============================================================================

def create_listener(use_real: bool = True, **kwargs) -> InteractionListener:
    """
    Factory function to create the appropriate listener.
    
    Args:
        use_real: If True, create RealInteractionListener (requires pynput)
                 If False, create MockInteractionListener for testing
        **kwargs: Arguments to pass to the listener constructor
    
    Returns:
        An initialized InteractionListener instance
    """
    if use_real and PYNPUT_AVAILABLE:
        print("\n" + "="*60)
        print("🔴 CREATING REAL INTERACTION LISTENER (Production Mode)")
        print("="*60)
        # Only pass relevant kwargs to RealInteractionListener
        real_kwargs = {k: v for k, v in kwargs.items() 
                      if k in ['track_focus', 'idle_threshold']}
        return RealInteractionListener(**real_kwargs)
    else:
        print("\n" + "="*60)
        print("🟡 CREATING MOCK INTERACTION LISTENER (Test Mode)")
        if use_real and not PYNPUT_AVAILABLE:
            print("   (Real listener unavailable - pynput not installed)")
        print("="*60)
        # Mock accepts all kwargs (they'll be ignored if not needed)
        return MockInteractionListener(**kwargs)


# ============================================================================
# Self-test code (runs when file is executed directly)
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 TESTING INTERACTION LISTENER")
    print("="*60)
    
    # Test real listener if available
    if PYNPUT_AVAILABLE:
        print("\n🔴 Testing RealInteractionListener...")
        listener = RealInteractionListener(track_focus=True)
        listener.start()
        
        print("\n📊 Capturing events for 10 seconds...")
        print("   Try typing, moving mouse, or switching windows!")
        
        for i in range(10):
            time.sleep(1)
            events = listener.get_events(timeout=0.1)
            stats = listener.get_stats()
            print(f"\n   Second {i+1}: {len(events)} events, " +
                  f"Keys: {stats['keys_pressed']}, " +
                  f"Idle: {stats['idle']}")
        
        listener.stop()
    
    # Test mock listener
    print("\n🟡 Testing MockInteractionListener...")
    mock = MockInteractionListener()
    mock.start()
    
    time.sleep(3)
    events = mock.get_events(timeout=0.5)
    print(f"   Generated {len(events)} mock events")
    
    # Show first few events
    for i, event in enumerate(events[:5]):
        print(f"   Event {i+1}: {event.type} at {event.timestamp:.2f}")
    
    mock.stop()
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)