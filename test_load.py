# test_load.py
"""
Simulate multiple concurrent sessions
"""

import threading
import time
import uuid
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.interaction_listener import MockInteractionListener
from client.feature_extractor import FeatureExtractor
from client.baseline_builder import BaselineBuilder
from client.activity_shift_detector import ActivityShiftDetector
from client.risk_engine import RiskEngine
from shared.models import RiskData, AnomalyScores

def run_session(session_id, duration=60):
    """Run a single test session"""
    print(f"[Session {session_id[:8]}] Starting...")
    
    listener = MockInteractionListener()
    extractor = FeatureExtractor()
    baseline_builder = BaselineBuilder(calibration_duration=30)
    detector = ActivityShiftDetector()
    risk_engine = RiskEngine()
    
    listener.start()
    start_time = time.time()
    risk_count = 0
    
    while time.time() - start_time < duration:
        events = listener.get_events(timeout=0.5)
        for event in events:
            extractor.add_event(event)
        
        features = extractor.compute_features()
        baseline_builder.update(features, features.window_end)
        
        if baseline_builder.is_calibrated and detector.baseline is None:
            detector.baseline = baseline_builder.baseline
        
        if detector.baseline is not None:
            anomaly_scores = detector.compute_scores(features)
            risk_score = risk_engine.compute_risk(anomaly_scores)
            
            # Send to API
            payload = RiskData(
                timestamp=time.time(),
                risk_score=risk_score,
                anomaly_scores=AnomalyScores(
                    idle_burst=anomaly_scores.idle_burst,
                    focus_instability=anomaly_scores.focus_instability,
                    behavioral_drift=anomaly_scores.behavioral_drift,
                    overall=anomaly_scores.overall
                ),
                session_id=session_id
            )
            
            try:
                if hasattr(payload, "model_dump"):
                    payload_dict = payload.model_dump()
                else:
                    payload_dict = payload.dict()
                    
                resp = requests.post("http://localhost:8000/risk", json=payload_dict, timeout=1)
                if resp.status_code == 200:
                    risk_count += 1
            except:
                pass
        
        time.sleep(1)
    
    listener.stop()
    print(f"[Session {session_id[:8]}] Completed. Sent {risk_count} risk scores.")

# Run 3 concurrent sessions
print("🚀 Starting load test with 3 concurrent sessions...")
threads = []
for i in range(3):
    session_id = str(uuid.uuid4())
    t = threading.Thread(target=run_session, args=(session_id, 30))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("✅ Load test complete!")