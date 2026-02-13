"""
SentinelX - Complete Anomaly Test Script
----------------------------------------
This script automatically tests all three anomaly detection types:
1. Idle Burst (copy-paste behavior)
2. Focus Instability (tab switching)
3. Behavioral Drift (typing speed change)

Run this AFTER the system is calibrated (after 3 minutes of normal typing)
"""

import time
import threading
import pyautogui
import keyboard
import random
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from client.interaction_listener import create_listener
    from client.feature_extractor import FeatureExtractor
    from client.risk_engine import RiskEngine
    from client.activity_shift_detector import ActivityShiftDetector, AnomalyScores
    from client.baseline_builder import BaselineProfile
except ImportError:
    print("❌ Could not import SentinelX modules. Make sure you're in the project root.")
    sys.exit(1)


class AnomalyTester:
    """Automated tester for SentinelX anomaly detection"""
    
    def __init__(self):
        self.listener = None
        self.extractor = FeatureExtractor(window_duration=10)  # Shorter window for testing
        self.risk_engine = RiskEngine(smoothing_window=1)  # No smoothing for raw scores
        self.detector = ActivityShiftDetector()
        
        # Test results storage
        self.results = {
            'idle_burst': {'detected': False, 'max_score': 0, 'timing': []},
            'focus_instability': {'detected': False, 'max_score': 0, 'timing': []},
            'behavioral_drift': {'detected': False, 'max_score': 0, 'timing': []}
        }
        
        # Control flags
        self.running = True
        self.test_phase = "idle"
        self.phase_start_time = 0
        
        # Sample text for typing tests
        self.sample_texts = [
            "The quick brown fox jumps over the lazy dog. ",
            "Now is the time for all good men to come to the aid of their country. ",
            "To be or not to be, that is the question. ",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. ",
            "Python is a powerful programming language for data science. "
        ]
        
    def setup_baseline(self):
        """Create a mock baseline for testing"""
        print("\n📊 Setting up test baseline...")
        self.detector.baseline = BaselineProfile(
            avg_typing_speed=150.0,    # Normal typing speed
            avg_idle_duration=2.0,      # Normal idle duration
            avg_focus_rate=0.5          # Normal focus loss rate
        )
        print("✅ Test baseline configured")
        print(f"   - Typing speed: 150 keys/min")
        print(f"   - Idle duration: 2.0s")
        print(f"   - Focus rate: 0.5/min")
        
    def start_listener(self):
        """Start real interaction listener"""
        print("\n🎯 Starting interaction listener...")
        self.listener = create_listener(use_real=True, track_focus=True)
        self.listener.start()
        time.sleep(2)
        print("✅ Listener started")
        
    def stop_listener(self):
        """Stop interaction listener"""
        if self.listener:
            self.listener.stop()
            print("🛑 Listener stopped")
            
    def collect_events(self, duration=5):
        """Collect events for specified duration"""
        events = []
        start = time.time()
        while time.time() - start < duration:
            new_events = self.listener.get_events(timeout=0.1)
            events.extend(new_events)
            for event in new_events:
                self.extractor.add_event(event)
            time.sleep(0.1)
        return events
        
    def compute_current_risk(self):
        """Compute risk score from current features"""
        features = self.extractor.compute_features()
        scores = self.detector.compute_scores(features)
        risk = self.risk_engine.compute_risk(scores)
        return risk, scores, features
        
    def print_header(self, text):
        """Print formatted header"""
        print("\n" + "="*60)
        print(f"🔬 {text}")
        print("="*60)
        
    def print_result(self, test_name, success, score, details=""):
        """Print test result with color"""
        if success:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
            
        if score >= 60:
            level = "🔴 HIGH"
        elif score >= 30:
            level = "🟠 MEDIUM"
        else:
            level = "🟢 LOW"
            
        print(f"\n{status} - {test_name}")
        print(f"   Max Score: {score:.1f} ({level})")
        if details:
            print(f"   Details: {details}")
            
    def test_idle_burst(self):
        """
        Test 1: Idle Burst (Copy-Paste Behavior)
        Steps:
        1. Stop typing (idle period)
        2. Simulate copy-paste with rapid typing
        """
        self.print_header("TEST 1: IDLE BURST (Copy-Paste Detection)")
        
        print("\n📝 Phase 1: Establishing normal typing...")
        # Type normally for 10 seconds
        end_time = time.time() + 10
        while time.time() < end_time:
            text = random.choice(self.sample_texts)
            pyautogui.write(text, interval=0.1)  # Normal typing speed
            time.sleep(0.5)
            
        # Collect events during normal typing
        self.collect_events(5)
        normal_risk, normal_scores, _ = self.compute_current_risk()
        print(f"   Normal typing risk: {normal_risk:.1f}")
        print(f"   Normal scores - I:{normal_scores.idle_burst:.1f} "
              f"F:{normal_scores.focus_instability:.1f} "
              f"D:{normal_scores.behavioral_drift:.1f}")
        
        print("\n⏸️ Phase 2: Idle period (8 seconds)...")
        time.sleep(8)  # Idle period
        
        print("\n⚡ Phase 3: Rapid typing (simulating copy-paste)...")
        # Simulate copy-paste with very fast typing
        rapid_text = "PASTED TEXT PASTED TEXT PASTED TEXT PASTED TEXT " * 3
        start_time = time.time()
        pyautogui.write(rapid_text, interval=0.01)  # Very fast typing
        typing_duration = time.time() - start_time
        
        # Collect events during burst
        self.collect_events(3)
        burst_risk, burst_scores, features = self.compute_current_risk()
        
        # Check if detected
        detected = burst_scores.idle_burst > 30
        self.results['idle_burst']['detected'] = detected
        self.results['idle_burst']['max_score'] = burst_scores.idle_burst
        
        self.print_result(
            "Idle Burst Detection",
            detected,
            burst_scores.idle_burst,
            f"Typed {len(rapid_text)} chars in {typing_duration:.1f}s"
        )
        
        return detected, burst_scores.idle_burst
        
    def test_focus_instability(self):
        """
        Test 2: Focus Instability (Tab Switching)
        Steps:
        1. Normal focus
        2. Rapid Alt-Tab switching
        """
        self.print_header("TEST 2: FOCUS INSTABILITY (Tab Switching)")
        
        print("\n📝 Phase 1: Normal focus period...")
        # Type normally for 5 seconds
        pyautogui.write("Normal typing during focus test. ", interval=0.1)
        time.sleep(2)
        
        # Collect baseline
        self.collect_events(3)
        normal_risk, normal_scores, _ = self.compute_current_risk()
        print(f"   Normal focus score: {normal_scores.focus_instability:.1f}")
        
        print("\n🔄 Phase 2: Rapid Alt-Tab switching (10 seconds)...")
        print("   (Press Ctrl+C to stop if needed)")
        
        # Simulate Alt-Tab switching
        start_time = time.time()
        switch_count = 0
        
        while time.time() - start_time < 10:
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.3)  # Quick switch
            switch_count += 1
            
        print(f"   Performed {switch_count} window switches")
        
        # Collect events during switching
        self.collect_events(3)
        switch_risk, switch_scores, features = self.compute_current_risk()
        
        # Check if detected
        detected = switch_scores.focus_instability > 30
        self.results['focus_instability']['detected'] = detected
        self.results['focus_instability']['max_score'] = switch_scores.focus_instability
        
        self.print_result(
            "Focus Instability Detection",
            detected,
            switch_scores.focus_instability,
            f"{switch_count} window switches in 10s"
        )
        
        return detected, switch_scores.focus_instability
        
    def test_behavioral_drift(self):
        """
        Test 3: Behavioral Drift (Typing Speed Change)
        Steps:
        1. Type very slowly
        2. Type very rapidly
        """
        self.print_header("TEST 3: BEHAVIORAL DRIFT (Speed Change)")
        
        print("\n🐢 Phase 1: Slow typing (30 seconds)...")
        slow_text = "Slow typing test. " * 10
        start_time = time.time()
        pyautogui.write(slow_text, interval=0.3)  # Very slow typing
        slow_duration = time.time() - start_time
        slow_wpm = (len(slow_text) / 5) / (slow_duration / 60)  # Words per minute
        
        self.collect_events(3)
        slow_risk, slow_scores, _ = self.compute_current_risk()
        print(f"   Slow typing: {slow_wpm:.1f} WPM")
        
        print("\n🐇 Phase 2: Fast typing (30 seconds)...")
        fast_text = "Fast typing test. " * 30
        start_time = time.time()
        pyautogui.write(fast_text, interval=0.03)  # Very fast typing
        fast_duration = time.time() - start_time
        fast_wpm = (len(fast_text) / 5) / (fast_duration / 60)
        
        self.collect_events(3)
        fast_risk, fast_scores, features = self.compute_current_risk()
        print(f"   Fast typing: {fast_wpm:.1f} WPM")
        print(f"   Speed ratio: {fast_wpm/slow_wpm:.1f}x")
        
        # Check if detected
        detected = fast_scores.behavioral_drift > 30
        self.results['behavioral_drift']['detected'] = detected
        self.results['behavioral_drift']['max_score'] = fast_scores.behavioral_drift
        
        self.print_result(
            "Behavioral Drift Detection",
            detected,
            fast_scores.behavioral_drift,
            f"Speed change: {slow_wpm:.0f} → {fast_wpm:.0f} WPM"
        )
        
        return detected, fast_scores.behavioral_drift
        
    def run_all_tests(self):
        """Run all three anomaly tests"""
        print("\n" + "="*70)
        print("🚀 SENTINELX - COMPLETE ANOMALY TEST SUITE")
        print("="*70)
        print("\n📋 This will test all three anomaly detection types:")
        print("   1. Idle Burst (copy-paste detection)")
        print("   2. Focus Instability (tab switching)")
        print("   3. Behavioral Drift (typing speed change)")
        print("\n⏱️  Total time: ~3-4 minutes")
        print("\n⚠️  IMPORTANT:")
        print("   - Don't use mouse/keyboard during tests (script will automate)")
        print("   - Keep this window in focus")
        print("   - Tests will start in 5 seconds...")
        
        time.sleep(5)
        
        try:
            # Setup
            self.setup_baseline()
            self.start_listener()
            
            # Run tests
            results = []
            
            # Test 1: Idle Burst
            input("\n\nPress Enter to start Test 1 (Idle Burst)...")
            result1 = self.test_idle_burst()
            results.append(result1)
            
            # Short pause between tests
            print("\n⏸️  Resting for 5 seconds...")
            time.sleep(5)
            
            # Test 2: Focus Instability
            input("\nPress Enter to start Test 2 (Focus Instability)...")
            result2 = self.test_focus_instability()
            results.append(result2)
            
            time.sleep(5)
            
            # Test 3: Behavioral Drift
            input("\nPress Enter to start Test 3 (Behavioral Drift)...")
            result3 = self.test_behavioral_drift()
            results.append(result3)
            
            # Final summary
            self.print_summary()
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Tests interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during tests: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_listener()
            
    def print_summary(self):
        """Print final test summary"""
        self.print_header("FINAL TEST SUMMARY")
        
        print("\n" + "-"*60)
        print("ANOMALY DETECTION RESULTS")
        print("-"*60)
        
        total_score = 0
        max_possible = 0
        
        for test_name, result in self.results.items():
            display_name = {
                'idle_burst': 'Idle Burst (Copy-Paste)',
                'focus_instability': 'Focus Instability (Tab Switching)',
                'behavioral_drift': 'Behavioral Drift (Speed Change)'
            }.get(test_name, test_name)
            
            status = "✅ DETECTED" if result['detected'] else "❌ NOT DETECTED"
            score = result['max_score']
            
            if score >= 60:
                level = "🔴 HIGH"
            elif score >= 30:
                level = "🟠 MEDIUM"
            else:
                level = "🟢 LOW"
                
            print(f"\n{display_name}:")
            print(f"   Status: {status}")
            print(f"   Max Score: {score:.1f} - {level}")
            
            if result['detected']:
                total_score += score
                max_possible += 100
                
        # Overall rating
        print("\n" + "-"*60)
        if max_possible > 0:
            success_rate = (total_score / max_possible) * 100
        else:
            success_rate = 0
            
        print(f"\n📊 OVERALL DETECTION RATE: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🏆 EXCELLENT - All anomalies detected strongly!")
        elif success_rate >= 50:
            print("👍 GOOD - Most anomalies detected")
        elif success_rate >= 20:
            print("⚠️ FAIR - Some anomalies detected")
        else:
            print("🔧 NEEDS TUNING - Adjust detection thresholds")
            
        print("\n" + "="*60)
        print("✅ TESTING COMPLETE")
        print("="*60)
        

def quick_test():
    """Quick test to verify everything is working"""
    print("🔍 Running quick system check...")
    
    try:
        # Test imports
        print("✓ Imports OK")
        
        # Test baseline
        detector = ActivityShiftDetector()
        detector.baseline = BaselineProfile(150, 2.0, 0.5)
        print("✓ Baseline OK")
        
        # Test risk engine
        engine = RiskEngine()
        print("✓ Risk Engine OK")
        
        # Test feature extractor
        extractor = FeatureExtractor()
        print("✓ Feature Extractor OK")
        
        print("\n✅ System check passed! Ready for full tests.\n")
        return True
        
    except Exception as e:
        print(f"\n❌ System check failed: {e}")
        return False


if __name__ == "__main__":
    # First run quick check
    if not quick_test():
        print("\nPlease fix the issues before running full tests.")
        sys.exit(1)
        
    # Ask user what they want to do
    print("\nWhat would you like to do?")
    print("1. Run all three anomaly tests (recommended)")
    print("2. Run quick test only")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        tester = AnomalyTester()
        tester.run_all_tests()
    elif choice == "2":
        print("\nQuick test complete!")
    else:
        print("\nExiting...")
        
    print("\n🎯 Don't forget to check the dashboard at http://localhost:8501")