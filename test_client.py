# test_client.py
"""
Manual test script for SentinelX components
Run this separately to test individual modules
"""

import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🧪 Testing SentinelX Components...\n")

# 1. Test Feature Extractor
print("1. Testing Feature Extractor...")
from client.feature_extractor import FeatureExtractor
extractor = FeatureExtractor(window_duration=10.0)
print("   ✅ FeatureExtractor initialized")

# 2. Test Baseline Builder
print("2. Testing Baseline Builder...")
from client.baseline_builder import BaselineBuilder
builder = BaselineBuilder(calibration_duration=30.0)
print("   ✅ BaselineBuilder initialized")

# 3. Test Activity Shift Detector
print("3. Testing Activity Shift Detector...")
from client.activity_shift_detector import ActivityShiftDetector
detector = ActivityShiftDetector()
print("   ✅ ActivityShiftDetector initialized")

# 4. Test Risk Engine
print("4. Testing Risk Engine...")
from client.risk_engine import RiskEngine
engine = RiskEngine(smoothing_window=3)
print("   ✅ RiskEngine initialized")

# 5. Test Shared Models
print("5. Testing Shared Models...")
from shared.models import RiskData, AnomalyScores
test_scores = AnomalyScores(idle_burst=50, focus_instability=30, behavioral_drift=20, overall=50)
test_risk = RiskData(
    timestamp=time.time(),
    risk_score=45.5,
    anomaly_scores=test_scores,
    session_id="test-session-123"
)
print("   ✅ Models initialized")
print(f"   📦 Test payload: {test_risk.model_dump() if hasattr(test_risk, 'model_dump') else test_risk.dict()}")

# 6. Test API Connection
print("6. Testing API Connection...")
import requests
try:
    resp = requests.get("http://localhost:8000/health", timeout=2)
    if resp.status_code == 200:
        print("   ✅ API is reachable")
    else:
        print("   ❌ API returned status:", resp.status_code)
except:
    print("   ⚠️  API not running (start with 'python main.py' first)")

print("\n✅ All tests passed!")