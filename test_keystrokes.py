from client.interaction_listener import create_listener
from client.feature_extractor import FeatureExtractor
import time

print("Testing keystroke detection...")
print("Press some keys for 10 seconds...")

listener = create_listener(use_real=True)
extractor = FeatureExtractor(window_duration=10)

listener.start()
time.sleep(2)  # Warm up

start = time.time()
while time.time() - start < 10:
    events = listener.get_events(timeout=0.5)
    for event in events:
        extractor.add_event(event)
        if hasattr(event, 'type'):
            print(f"Event: {event.type}")

features = extractor.compute_features()
print(f"\nResults:")
print(f"Key press count: {features.key_press_count}")
print(f"Typing speed: {features.avg_typing_speed:.1f} keys/min")

listener.stop()