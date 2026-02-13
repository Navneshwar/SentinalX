# main.py
"""
SentinelX – Simplified Risk‑Based Proctoring System
Entry point for local demonstration.

Launches three concurrent processes:
1. FastAPI backend server (on port 8000)
2. Streamlit dashboard (on port 8501)
3. REAL client that captures actual interaction metadata and sends risk scores

All components run in separate processes. Use Ctrl+C to terminate.
"""

import os
import sys

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print(f"[Main] Project root: {PROJECT_ROOT}")
print(f"[Main] Python version: {sys.version}")

import multiprocessing
import time
import uuid
import requests
import argparse
from datetime import datetime
from typing import Optional

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

class Config:
    """Configuration settings for SentinelX."""
    
    # Server settings
    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 8000
    SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    # Dashboard settings
    DASHBOARD_PORT = 8501
    
    # Client settings
    CALIBRATION_DURATION = 180  # 3 minutes baseline
    RISK_SEND_INTERVAL = 5       # Send risk score every 5 seconds
    FEATURE_WINDOW = 30          # 30-second feature window
    
    # Detection thresholds
    IDLE_THRESHOLD = 3.0         # Consider idle after 3 seconds
    TRACK_FOCUS = True           # Track window focus changes
    
    # Demo mode (use mock data for testing without permissions)
    DEMO_MODE = False            # Set to True to use mock listener


# ----------------------------------------------------------------------
# 1. Database Initialization
# ----------------------------------------------------------------------

def init_database():
    """Create database tables before starting the server."""
    try:
        from server.database import init_db
        print("[Main] Initializing database...")
        init_db()
        print("[Main] Database ready at: sentinelx.db")
    except Exception as e:
        print(f"[Main] Database initialization error: {e}")
        sys.exit(1)


# ----------------------------------------------------------------------
# 2. FastAPI Server Process
# ----------------------------------------------------------------------

def run_server():
    """Start Uvicorn server for the FastAPI application."""
    import os
    import sys
    
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    
    import uvicorn
    from server.api import app
    
    print(f"[Server] Starting on http://{Config.SERVER_HOST}:{Config.SERVER_PORT}")
    uvicorn.run(
        app, 
        host=Config.SERVER_HOST, 
        port=Config.SERVER_PORT, 
        log_level="info"
    )


# ----------------------------------------------------------------------
# 3. Streamlit Dashboard Process
# ----------------------------------------------------------------------

def run_dashboard():
    """Launch Streamlit dashboard using its CLI."""
    import os
    import sys
    import subprocess
    
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    
    dashboard_path = os.path.join(PROJECT_ROOT, "dashboard", "app.py")
    
    if not os.path.exists(dashboard_path):
        print(f"[Dashboard] ERROR: File not found at {dashboard_path}")
        print(f"[Dashboard] Current directory: {os.getcwd()}")
        return
        
    print(f"[Dashboard] Starting on http://localhost:{Config.DASHBOARD_PORT}")
    print(f"[Dashboard] Path: {dashboard_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path, 
                   f"--server.port={Config.DASHBOARD_PORT}"])


# ----------------------------------------------------------------------
# 4. Real Client Process
# ----------------------------------------------------------------------

def run_simulation(demo_mode: bool = False):
    """
    Run REAL client that captures actual user interaction.
    
    Args:
        demo_mode: If True, use mock listener (no permissions needed)
                  If False, use real listener (requires system permissions)
    """
    # Add path
    import os
    import sys
    
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, sys.path.insert(0, PROJECT_ROOT))
    
    import time
    import uuid
    import requests
    from datetime import datetime
    
    # Import our new listener factory
    try:
        from client.interaction_listener import create_listener
        from client.feature_extractor import FeatureExtractor
        from client.baseline_builder import BaselineBuilder
        from client.activity_shift_detector import ActivityShiftDetector
        from client.risk_engine import RiskEngine
        from shared.models import RiskData, AnomalyScores
        
        print("[Client] ✅ All modules imported successfully")
    except ImportError as e:
        print(f"[Client] ❌ Import error: {e}")
        print(f"[Client] sys.path: {sys.path}")
        raise

    # Print mode
    mode_str = "DEMO MODE (mock data)" if demo_mode else "PRODUCTION MODE (real data)"
    print("\n" + "="*60)
    print(f"🚀 Starting SentinelX Client in {mode_str}")
    print("="*60 + "\n")

    # Generate unique session ID
    session_id = str(uuid.uuid4())
    print(f"[Client] Session ID: {session_id}")
    print(f"[Client] Start time: {datetime.now().strftime('%H:%M:%S')}")

    # Initialize components with config
    listener = create_listener(
        use_real=not demo_mode,
        track_focus=Config.TRACK_FOCUS,
        idle_threshold=Config.IDLE_THRESHOLD
    )
    
    extractor = FeatureExtractor(window_duration=Config.FEATURE_WINDOW)
    baseline_builder = BaselineBuilder(calibration_duration=Config.CALIBRATION_DURATION)
    detector = ActivityShiftDetector()
    risk_engine = RiskEngine(smoothing_window=3)

    # Start the real event listener
    try:
        listener.start()
        print("[Client] ✅ Interaction listener started")
    except Exception as e:
        print(f"[Client] ❌ Failed to start listener: {e}")
        print("   Try running in demo mode with --demo flag")
        return

    # Wait for server to be ready
    print("[Client] Waiting for server...")
    server_ready = False
    for i in range(10):
        try:
            resp = requests.get(f"{Config.SERVER_URL}/health", timeout=1)
            if resp.status_code == 200:
                server_ready = True
                print("[Client] ✅ Server connection established")
                break
        except:
            pass
        time.sleep(1)
    
    if not server_ready:
        print("[Client] ⚠️  Server not responding - will retry sending data")

    # Main loop
    last_risk_send_time = 0
    calibration_start_time = time.time()
    event_count = 0
    risk_count = 0
    
    print("\n" + "-"*60)
    print("📊 Monitoring started - interact with your computer normally")
    print("-"*60 + "\n")

    try:
        while True:
            current_time = time.time()
            
            # 1. Get real events from listener
            events = listener.get_events(timeout=0.5)
            if events:
                event_count += len(events)
                for event in events:
                    extractor.add_event(event)

            # 2. Compute features from current window
            features = extractor.compute_features()

            # 3. Update baseline builder (calibration phase)
            baseline_builder.update(features, features.window_end)

            # 4. Once calibrated, set baseline in detector
            if baseline_builder.is_calibrated and detector.baseline is None:
                detector.baseline = baseline_builder.baseline
                calibration_time = current_time - calibration_start_time
                print(f"\n✅ [Client] Baseline calibrated after {calibration_time:.1f} seconds")
                print(f"   - Avg typing speed: {detector.baseline.avg_typing_speed:.1f} keys/min")
                print(f"   - Avg idle duration: {detector.baseline.avg_idle_duration:.2f}s")
                print(f"   - Avg focus rate: {detector.baseline.avg_focus_rate:.2f}/min\n")

            # 5. If baseline is ready, detect anomalies and compute risk
            if detector.baseline is not None:
                anomaly_scores = detector.compute_scores(features)
                risk_score = risk_engine.compute_risk(anomaly_scores)

                # Send risk data periodically
                if current_time - last_risk_send_time >= Config.RISK_SEND_INTERVAL:
                    # Prepare payload
                    payload = RiskData(
                        timestamp=current_time,
                        risk_score=risk_score,
                        anomaly_scores=AnomalyScores(
                            idle_burst=anomaly_scores.idle_burst,
                            focus_instability=anomaly_scores.focus_instability,
                            behavioral_drift=anomaly_scores.behavioral_drift,
                            overall=anomaly_scores.overall
                        ),
                        session_id=session_id,
                        source="real" if not demo_mode else "demo"
                    )
                    
                    # POST to backend
                    try:
                        if hasattr(payload, "model_dump"):
                            payload_dict = payload.model_dump()
                        else:
                            payload_dict = payload.dict()
                            
                        resp = requests.post(
                            f"{Config.SERVER_URL}/risk",
                            json=payload_dict,
                            timeout=2.0
                        )
                        
                        if resp.status_code == 200:
                            risk_count += 1
                            
                            # Color-coded risk output
                            if risk_score >= 80:
                                risk_color = "🔴"
                            elif risk_score >= 60:
                                risk_color = "🟠"
                            elif risk_score >= 30:
                                risk_color = "🟡"
                            else:
                                risk_color = "🟢"
                            
                            print(f"{risk_color} [Client] Risk: {risk_score:.1f} | "
                                  f"Events: {event_count} | "
                                  f"Anomalies: I:{anomaly_scores.idle_burst:.0f} "
                                  f"F:{anomaly_scores.focus_instability:.0f} "
                                  f"D:{anomaly_scores.behavioral_drift:.0f}")
                            
                            last_risk_send_time = current_time
                        else:
                            print(f"⚠️ [Client] Server error: {resp.status_code}")
                            
                    except requests.exceptions.ConnectionError:
                        print(f"⚠️ [Client] Cannot connect to server - retrying...")
                    except Exception as e:
                        print(f"⚠️ [Client] Error sending risk: {e}")

            # Show calibration progress
            if not baseline_builder.is_calibrated:
                elapsed = current_time - calibration_start_time
                progress = min(100, int((elapsed / Config.CALIBRATION_DURATION) * 100))
                print(f"📈 [Client] Calibrating baseline... {progress}% | Events: {event_count}", end="\r")

            # Sleep a bit to avoid busy loop
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n[Client] Received shutdown signal")
    except Exception as e:
        print(f"\n[Client] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean shutdown
        listener.stop()
        
        # Print session summary
        duration = time.time() - calibration_start_time
        print("\n" + "="*60)
        print("📊 SESSION SUMMARY")
        print("="*60)
        print(f"Session ID: {session_id}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Total events captured: {event_count}")
        print(f"Risk scores sent: {risk_count}")
        print(f"Final risk score: {risk_engine.current_risk:.1f}")
        print("="*60 + "\n")


# ----------------------------------------------------------------------
# 5. Main Orchestrator
# ----------------------------------------------------------------------

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SentinelX Proctoring System")
    parser.add_argument("--demo", action="store_true", 
                       help="Run in demo mode with mock data (no permissions needed)")
    parser.add_argument("--no-dashboard", action="store_true",
                       help="Skip launching the dashboard")
    parser.add_argument("--calibration", type=int, default=180,
                       help="Calibration duration in seconds (default: 180)")
    parser.add_argument("--interval", type=int, default=5,
                       help="Risk send interval in seconds (default: 5)")
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Update config
    Config.DEMO_MODE = args.demo
    Config.CALIBRATION_DURATION = args.calibration
    Config.RISK_SEND_INTERVAL = args.interval
    
    # Print startup banner
    print("\n" + "="*70)
    print("🛡️  SENTINELX - Privacy-First Proctoring System")
    print("="*70)
    print(f"Mode: {'DEMO (mock data)' if Config.DEMO_MODE else 'PRODUCTION (real data)'}")
    print(f"Calibration: {Config.CALIBRATION_DURATION}s")
    print(f"Risk interval: {Config.RISK_SEND_INTERVAL}s")
    print("="*70 + "\n")
    
    # Set multiprocessing start method
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    # Initialize database
    init_database()

    # Create processes
    server_process = multiprocessing.Process(target=run_server, name="Server")
    client_process = multiprocessing.Process(
        target=run_simulation, 
        kwargs={"demo_mode": Config.DEMO_MODE},
        name="Client"
    )
    
    dashboard_process = None
    if not args.no_dashboard:
        dashboard_process = multiprocessing.Process(target=run_dashboard, name="Dashboard")

    # Start all processes
    print("[Main] Starting SentinelX components...")
    
    server_process.start()
    time.sleep(2)  # Give server time to start
    
    if dashboard_process:
        dashboard_process.start()
        time.sleep(1)
    
    client_process.start()

    print("\n[Main] ✅ All components launched")
    print(f"[Main] 📊 Dashboard: http://localhost:{Config.DASHBOARD_PORT}")
    print(f"[Main] 🖥️  Server: {Config.SERVER_URL}")
    print("[Main] Press Ctrl+C to stop all components\n")

    try:
        # Wait for processes
        server_process.join()
        if dashboard_process:
            dashboard_process.join()
        client_process.join()
        
    except KeyboardInterrupt:
        print("\n\n[Main] ⚡ Shutdown signal received")
        
        # Terminate all processes
        for proc in [server_process, dashboard_process, client_process]:
            if proc and proc.is_alive():
                print(f"[Main] Terminating {proc.name}...")
                proc.terminate()
                proc.join(timeout=3.0)
                
        print("[Main] ✅ Shutdown complete")
        sys.exit(0)