# 🛡️ SentinelX – Privacy-First Proctoring System

SentinelX is a real-time, privacy-preserving proctoring and risk detection system designed to monitor behavioral anomalies during online exams or assessments.  
It detects suspicious patterns (like copy-paste bursts, window switching, or abnormal typing behavior) **without capturing any sensitive content** such as keystrokes, window titles, screenshots, or video.

> 🔒 Privacy by Design: SentinelX only uses timing and motion metadata. No raw interaction content is stored.

---

## 🚀 Key Features

- **Real-time Behavioral Monitoring**
  - Keystroke timing (no characters recorded)
  - Mouse movement & clicks
  - Idle detection
  - Window focus changes (optional, privacy-safe)

- **Anomaly Detection Engine**
  - Idle-to-Burst Detection (possible copy-paste behavior)
  - Focus Instability (excessive tab/window switching)
  - Behavioral Drift (significant typing pattern changes)

- **Risk Scoring Engine**
  - Weighted risk aggregation
  - Moving average smoothing
  - Risk levels: Normal, Low, Medium, High, Critical

- **Live Proctor Dashboard (Streamlit)**
  - Real-time risk graphs
  - Session filtering
  - Anomaly explanations
  - Proctor-friendly UI

- **Mock Mode for Testing**
  - Synthetic interaction generator
  - Useful for development without system permissions

---

## 🧠 System Architecture

```text
[Interaction Listener]
        ↓
[Feature Extractor]
        ↓
[Baseline Builder] → establishes "normal" user behavior
        ↓
[Activity Shift Detector] → anomaly scores
        ↓
[Risk Engine] → smoothed risk score (0–100)
        ↓
[Dashboard] → real-time monitoring & alerts
```

##📁 Project Structure
```text
client/
  ├── interaction_listener.py
  ├── feature_extractor.py
  ├── baseline_builder.py
  ├── activity_shift_detector.py
  └── risk_engine.py

dashboard/
  └── app.py

shared/
  └── models.py
```
### Installation
***1️⃣ Clone the Repository***
``` text
git clone https://github.com/your-org/sentinelx.git
cd sentinelx
```

***2️⃣ Create Virtual Environment (Recommended)***
```
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```
***3️⃣ Install Dependencies***
```
pip install -r requirements.txt
Optional system hooks (for real interaction capture):
pip install pynput


Platform-specific (optional):

Windows: pip install pywin32

macOS: pip install pyobjc-framework-Cocoa

Linux: pip install python-xlib
```
##🔐 Privacy Guarantees

***SentinelX never collects:**
❌ Keystroke characters
❌ Window titles
❌ Screenshots or video
❌ Screen content

***SentinelX only collects:***
✅ Event timestamps
✅ Aggregate typing speed
✅ Idle durations
✅ Focus change counts
✅ Mouse movement distance

This makes SentinelX suitable for privacy-sensitive environments.

##⚠️ Disclaimer
SentinelX provides behavioral risk signals, not proof of misconduct.
Human review and institutional policy should always be used alongside automated detection.
