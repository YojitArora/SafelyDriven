# 🚗 SafelyDriven — AI Driver Drowsiness Detection System

A real-time AI-powered driver safety system that detects drowsiness, blink rate, yawning, and head pose — with SOS SMS alerts and a live analytics dashboard.

## ✨ Features

- 👁️ **Drowsiness Detection** — Monitors Eye Aspect Ratio (EAR) in real-time
- 😮 **Yawn Detection** — Detects yawning using mouth aspect ratio
- 🧠 **Head Pose Estimation** — Tracks head tilt and nodding
- 🔔 **Audio Alarm** — Plays an alert sound when drowsiness is detected
- 📱 **SOS SMS** — Sends emergency SMS via Twilio after 10s of drowsy state
- 📊 **Live Analytics Dashboard** — Real-time charts with Chart.js
- 🗺️ **Emergency Map** — Interactive Leaflet.js map for incident location
- 🎞️ **Black Box History** — Session snapshot gallery for post-event analysis
- 🛡️ **Face Liveness Check** — Anti-spoofing using head movement detection

## 🛠️ Tech Stack

- **Backend:** Python, OpenCV, dlib, Flask/WebSocket
- **Frontend:** HTML, CSS, JavaScript (Chart.js, Leaflet.js)
- **SMS:** Twilio API
- **Face Detection:** dlib 68-point facial landmarks

## 📦 Setup

### 1. Clone the repository
```bash
git clone https://github.com/ARYAN2307A/MDP.git
cd MDP
```

### 2. Create a virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> On macOS, `dlib` may need Xcode Command Line Tools: `xcode-select --install`.

### 4. Download the AI Model / Dataset (Required)
The Dlib facial landmark model is too large for GitHub (100MB) and is required to run the code. 
*(Note: This pre-trained model was originally trained on the **iBUG 300-W face landmark dataset**).*

1. Download the compressed model here: **[shape_predictor_68_face_landmarks.dat.bz2](http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2)**
2. Extract the `.bz2` archive to get the `.dat` file.
3. Place the extracted `shape_predictor_68_face_landmarks.dat` file directly in your main project folder.

### 5. Set up environment variables
Create a `.env` file in the root directory:
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
EMERGENCY_CONTACT_PHONE=+91xxxxxxxxxx

# Optional runtime configuration
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
CAMERA_INDEX=0
# Leave empty to run without Arduino. Otherwise use COM5 or /dev/tty.*
ARDUINO_PORT=
```

Twilio and Arduino are optional. SMS alerts are enabled only when all Twilio
values are configured; the dashboard can run without either integration.

### 6. Run the application
```bash
python detector.py
```

Then open `http://127.0.0.1:5000` in your browser. Change `FLASK_PORT` when
port 5000 is already in use, and set `CAMERA_INDEX=1` if your camera is not
available at index 0.

## ⚠️ Notes

- The `shape_predictor_68_face_landmarks.dat` file (~99MB) is **not** included in the repo. Download it separately.
- Never commit your `.env` file — it contains API secrets.
- Requires a webcam for real-time detection.
- If startup reports a missing landmark model, download and extract the model
  described above into the project root.
- Set `ARDUINO_PORT` only when an Arduino is connected; leaving it empty avoids
  a failed connection attempt on machines without one.

## 📸 Dashboard Preview

> Real-time drowsiness monitoring with live analytics, emergency map, and session history.
>
> <img width="1835" height="1066" alt="Screenshot 2026-04-01 000204" src="https://github.com/user-attachments/assets/e3ab5882-ce13-4546-9a21-6b2276bffc6b" />


  <img width="1890" height="1066" alt="Screenshot 2026-04-01 081210" src="https://github.com/user-attachments/assets/503146bc-23a2-4dad-9f39-365aec537838" />

  
  <img width="1883" height="1069" alt="image" src="https://github.com/user-attachments/assets/25d15cc3-7601-4b3a-8440-209ac8763b2d" />

  
  <img width="1419" height="689" alt="image" src="https://github.com/user-attachments/assets/0d8afe09-28ba-445f-9fc5-e683e36ded34" />

  
  <img width="1889" height="1066" alt="image" src="https://github.com/user-attachments/assets/0667eb97-77df-4aa4-9f39-3e8c460643f3" />



## Final Product Presentation

[AI-Powered-Driver-Drowsiness-Detection-System.pptx](https://github.com/user-attachments/files/26393826/AI-Powered-Driver-Drowsiness-Detection-System.pptx)

## Project Report

[REPORT.docx](https://github.com/user-attachments/files/26394145/REPORT.docx)

## Project Demo Video

https://drive.google.com/file/d/1sTdp0ql23iBH1qJZIPliGIuT1RuPcvT9/view?usp=sharing
