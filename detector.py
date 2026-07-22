import cv2
import dlib
import imutils
import numpy as np
import threading
import time
import serial
import os
import requests
from collections import deque
from flask import Flask, jsonify, request, send_from_directory, Response
from imutils import face_utils
from scipy.spatial import distance
from pygame import mixer
from emotiefflib.facial_analysis import EmotiEffLibRecognizer
from twilio.rest import Client
from dotenv import load_dotenv
from config import (
    ARDUINO_PORT,
    CAMERA_INDEX,
    EVENT_LOG_PATH,
    FLASK_HOST,
    FLASK_PORT,
    LANDMARK_MODEL_PATH,
    MUSIC_PATH,
    PROJECT_ROOT,
)

# Load environment variables
load_dotenv(override=True)

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
EMERGENCY_CONTACT_PHONE = os.getenv('EMERGENCY_CONTACT_PHONE')

# --- Configuration & State ---
app = Flask(__name__, static_folder=str(PROJECT_ROOT), static_url_path='')
is_monitoring = False
monitor_thread = None
output_frame = None
lock = threading.Lock()
ser = None

# Ensure event log directory exists on startup
EVENT_LOG_PATH.mkdir(exist_ok=True)

# Global state for dashboard
current_ear = 0.0
current_mar = 0.0
current_blink_freq = 0
safety_score = 100
current_emotion = ""
current_emotion_score = 0.0
session_logs = []
is_stressed = False
drowsy_alarm_active = False

drowsy_start_time = None
sos_triggered = False
last_sos_time = 0
sos_trigger_time = None

def add_log(msg, level="warning"):
    timestamp = time.strftime("[%H:%M:%S]")
    session_logs.append({"time": timestamp, "msg": msg, "level": level})
    if len(session_logs) > 50:
        session_logs.pop(0)

# --- 1. INITIALIZATION ---
try:
    mixer.init()
    mixer.music.load(str(MUSIC_PATH))
except Exception as error:
    print(f"Warning: audio alarm disabled: {error}")

def connect_arduino():
    global ser
    if not ARDUINO_PORT:
        add_log("Arduino disabled; set ARDUINO_PORT to enable it.", "info")
        return False
    try:
        if ser:
            ser.close()
        ser = serial.Serial(ARDUINO_PORT, 9600, timeout=1)
        time.sleep(2) 
        print(f"SUCCESS: Arduino Connected on {ARDUINO_PORT}")
        add_log(f"Arduino connected on {ARDUINO_PORT}", "info")
        return True
    except Exception as e:
        ser = None
        print(f"ERROR: Could not connect to Arduino: {e}")
        add_log(f"Arduino connection failed: {e}", "warning")
        return False

# Connect only when explicitly configured.
if ARDUINO_PORT:
    connect_arduino()

# --- 2. MODELS ---
fer = None
try:
    fer = EmotiEffLibRecognizer(model_name="enet_b0_8_best_afew", engine="onnx", device="cpu")
except Exception as error:
    print(f"Warning: emotion recognition disabled: {error}")
detect = dlib.get_frontal_face_detector()
try:
    predict = dlib.shape_predictor(str(LANDMARK_MODEL_PATH))
except Exception as error:
    predict = None
    print(f"Error loading landmark model: {error}")

def eye_aspect_ratio(eye):
    A = distance.euclidean(eye[1], eye[5])
    B = distance.euclidean(eye[2], eye[4])
    C = distance.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)

def mouth_aspect_ratio(mouth):
    # Inner lips indices for better yawn detection
    v1 = distance.euclidean(mouth[13], mouth[19]) 
    v2 = distance.euclidean(mouth[14], mouth[18]) 
    v3 = distance.euclidean(mouth[15], mouth[17]) 
    h = distance.euclidean(mouth[12], mouth[16]) 
    return (v1 + v2 + v3) / (2.0 * h)

(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["right_eye"]
(mStart, mEnd) = face_utils.FACIAL_LANDMARKS_68_IDXS["mouth"]

# --- 3. TUNED THRESHOLDS ---
ear_thresh = 0.25       # EAR threshold for drowsiness/blink
mar_thresh = 0.35       # MAR threshold for yawn
anger_thresh = 0.35     # Anger probability threshold
frame_check = 10        # Consecutive frames before triggering alert

# --- Core Detection Loop ---
def send_sos_sms_async():
    global sos_triggered, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, EMERGENCY_CONTACT_PHONE
    
    if not all((TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, EMERGENCY_CONTACT_PHONE)):
        message = "Twilio is not fully configured; SOS SMS was not sent."
        print(message)
        add_log(message, "warning")
        return

    # 1. Fetch approximate location via IP geolocation
    location_text = "\n\nLocation: Could not determine."
    try:
        print("DEBUG: Fetching location for SOS...")
        geo = requests.get("https://ipinfo.io/json", timeout=8).json()
        loc = geo.get("loc", "")  # "lat,lng"
        city = geo.get("city", "Unknown")
        region = geo.get("region", "")
        if loc:
            maps_link = f"https://www.google.com/maps?q={loc}"
            location_text = f"\n\nApprox. Location: {city}, {region}\nGoogle Maps: {maps_link}"
        else:
            location_text = f"\n\nApprox. Location: {city}, {region} (coordinates unavailable)"
    except Exception as loc_err:
        print(f"DEBUG: Could not fetch location: {loc_err}")

    # 2. Send SMS with retry mechanism
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            print(f"DEBUG: Sending SOS SMS (Attempt {attempt+1}/{max_retries+1})...")
            message = client.messages.create(
                body=f"!!! URGENT: DANGER !!! SafelyDriven has detected that the driver is unresponsive or completely asleep for a prolonged period. Please check on them immediately.{location_text}",
                from_=TWILIO_PHONE_NUMBER,
                to=EMERGENCY_CONTACT_PHONE
            )
            print(f"SUCCESS: SOS SMS sent successfully: {message.sid}")
            add_log("SOS SMS sent to emergency contact.", "danger")
            return # Success, exit function
        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: SOS SMS Attempt {attempt+1} failed: {error_msg}")
            if attempt < max_retries:
                print("DEBUG: Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print(f"CRITICAL ERROR: All SOS SMS attempts failed: {error_msg}")
                add_log(f"Failed to send SOS SMS: {error_msg}", "danger")


def run_detector():
    global is_monitoring, output_frame, current_ear, current_mar, current_blink_freq, safety_score, current_emotion, current_emotion_score, is_stressed, drowsy_start_time, sos_triggered, last_sos_time, sos_trigger_time, drowsy_alarm_active
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        add_log(f"Could not open camera index {CAMERA_INDEX}.", "danger")
        is_monitoring = False
        cap.release()
        return
    drowsy_flag = 0
    yawn_flag = 0
    anger_flag = 0
    face_lost_time = None
    face_alarm_logged = False
    last_safe_time = time.time()  # Track safe driving time for score recovery
    
    print("SafelyDriven Engine: Monitoring Thread Started")
    
    while is_monitoring:
        ret, frame = cap.read()
        if not ret:
            break

        frame = imutils.resize(frame, width=640)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rects = detect(gray, 0)

        # Capture current time ONCE per frame
        current_time = time.time()

        # DEFAULT COMMAND IS SAFE (GREEN)
        current_command = b'S'

        if len(rects) == 0:
            with lock:
                current_ear = 0.0
                current_mar = 0.0
                current_emotion = "" # Clear emotion if face is gone
                current_emotion_score = 0.0
            
            # Start tracking how long face is missing
            if face_lost_time is None:
                face_lost_time = current_time
            
            # If face missing for > 3 seconds, trigger alarm
            if (current_time - face_lost_time) > 3.0:
                current_command = b'D' # Use Drowsy/Alarm command
                # Draw a cleaner bottom bar instead of a floating box
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 430), (640, 480), (0, 0, 150), -1) # Dark red bar at bottom
                cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame) # Apply semi-transparency
                
                cv2.putText(frame, "!!! FACE NOT DETECTED !!!", (120, 465),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                if not face_alarm_logged:
                    add_log("ALARM: Face missing for 3 seconds!", "danger")
                    face_alarm_logged = True
            
            drowsy_flag = 0
            yawn_flag = 0
            anger_flag = 0
        else:
            face_lost_time = None
            face_alarm_logged = False


        for rect in rects:
            shape = predict(gray, rect)
            shape = face_utils.shape_to_np(shape)

            # Get face ROI for emotion detection
            (fx, fy, fw, fh) = face_utils.rect_to_bb(rect)
            face_roi = frame[max(0, fy):fy+fh, max(0, fx):fx+fw]

            # Emotion Detection
            is_angry = False
            if face_roi.size > 0:
                try:
                    if fer is None:
                        raise RuntimeError("Emotion recognizer is unavailable")
                    emotion_label, scores = fer.predict_emotions(face_roi, logits=False)
                    # Support both list/string formats from various recognizer versions
                    if isinstance(emotion_label, list):
                        emotion_label = emotion_label[0]
                    
                    with lock:
                        current_emotion = str(emotion_label).capitalize()
                        current_emotion_score = round(float(np.max(scores)) * 100, 1)
                        
                        # Assess Stress (Refined: Anger > 80%)
                        is_stressed = False
                        if current_emotion.lower() == "anger" and current_emotion_score > 80.0:
                            is_stressed = True

                    if str(emotion_label).lower() == "anger" and np.max(scores) > anger_thresh:
                        is_angry = True
                except:
                    pass

            # Calculate EAR and MAR
            ear = (eye_aspect_ratio(shape[lStart:lEnd]) + eye_aspect_ratio(shape[rStart:rEnd])) / 2.0
            mar = mouth_aspect_ratio(shape[mStart:mEnd])
            
            # Update global for dashboard
            with lock:
                current_ear = ear
                current_mar = mar

            # --- TRACKING FLAGS ---
            if ear < ear_thresh:
                drowsy_flag += 1
            else:
                drowsy_flag = 0

            if is_angry:
                anger_flag += 1
            else:
                anger_flag = 0

            # Volatility Overlay (Priority 0 - highest mental health alert)
            with lock:
                local_stressed = is_stressed
            
            if local_stressed:
                # We do not override Arduino command here to avoid conflicting with drowsy/yawn, 
                # but we show it prominently on GUI and logs
                cv2.putText(frame, "!!! HIGH STRESS DETECTED !!!", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                # optionally log it once per 'stress' period
                if np.random.rand() < 0.05: # throttle log spam
                     add_log("HIGH EMOTIONAL STRESS (Anger > 80%)", "danger")

            # --- DECISION LOGIC ---
            # A. DROWSY (Priority 1)
            if ear < ear_thresh:
                if drowsy_start_time is None:
                    drowsy_start_time = current_time
                
                # Check for SOS Condition
                if (current_time - drowsy_start_time) >= 4.0:
                    with lock:
                        if not sos_triggered:
                            sos_triggered = True
                            sos_trigger_time = current_time
                    # Only send SMS if 30 seconds have passed since last one (reduced from 5m for testing/reliability)
                    if (current_time - last_sos_time) > 30:
                        last_sos_time = current_time
                        add_log("SOS TRIGGERED! Driver asleep for 4s.", "danger")
                        threading.Thread(target=send_sos_sms_async, daemon=True).start()
            else:
                drowsy_start_time = None

            with lock:
                # SOS Auto-Clear Logic (5 Seconds)
                if sos_triggered and sos_trigger_time is not None:
                    if (current_time - sos_trigger_time) > 5.0:
                        sos_triggered = False
                        sos_trigger_time = None
                local_sos = sos_triggered

            if local_sos:
                cv2.putText(frame, "!!! SOS EMERGENCY TRIGGERED !!!", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

            if drowsy_flag >= frame_check:
                current_command = b'D'
                cv2.putText(frame, "!!! DROWSINESS ALERT !!!", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                if drowsy_flag == frame_check:  # Log once per event
                    add_log(f"DROWSINESS DETECTED (EAR: {ear:.2f})", "danger")
                    # Save "Black Box" Snapshot
                    ts = time.strftime("%H%M%S")
                    img_name = f"drowsy_{ts}.jpg"
                    img_path = os.path.join(EVENT_LOG_PATH, img_name)
                    success = cv2.imwrite(img_path, frame)
                    if success:
                        print(f"DEBUG: Saved Drowsiness Snapshot: {img_path}")
                    else:
                        print(f"DEBUG ERROR: Failed to save snapshot to {img_path}")
                    with lock:
                        safety_score = max(0, safety_score - 5)
            # B. ANGER (Priority 2)
            elif anger_flag >= frame_check:
                current_command = b'A'
                cv2.putText(frame, "!!! ANGER DETECTED !!!", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                if anger_flag == frame_check:
                    add_log(f"ANGER DETECTED ({current_emotion_score}%)", "danger")
                    # Save "Black Box" Snapshot
                    ts = time.strftime("%H%M%S")
                    img_name = f"anger_{ts}.jpg"
                    img_path = os.path.join(EVENT_LOG_PATH, img_name)
                    success = cv2.imwrite(img_path, frame)
                    if success:
                        print(f"DEBUG: Saved Anger Snapshot: {img_path}")
                    else:
                        print(f"DEBUG ERROR: Failed to save snapshot to {img_path}")
                    with lock:
                        safety_score = max(0, safety_score - 3)
            # C. YAWN (Priority 3)
            elif mar > mar_thresh:
                yawn_flag += 1
                if yawn_flag >= frame_check:
                    current_command = b'Y'
                    cv2.putText(frame, "!!! YAWN ALERT !!!", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    if yawn_flag == frame_check:
                        add_log(f"YAWN DETECTED (MAR: {mar:.2f})", "warning")
                        with lock:
                            safety_score = max(0, safety_score - 2)
            else:
                yawn_flag = 0

            # Debug text on screen
            cv2.putText(frame, f"LIVE EAR: {round(ear, 2)}", (500, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"MAR: {round(mar, 2)}", (500, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # --- 4. EXECUTE HARDWARE COMMANDS ---
        if ser:
            try:
                ser.write(current_command)
            except:
                pass

        # --- SAFETY SCORE RECOVERY ---
        if current_command == b'S':
            if current_time - last_safe_time >= 5:
                with lock:
                    safety_score = min(100, safety_score + 1)
                last_safe_time = current_time
        else:
            last_safe_time = current_time

        with lock:
            current_blink_freq = 0
            output_frame = frame.copy()

        # --- 5. AUDIO FEEDBACK (Browser Voice Integration) ---
        with lock:
            if current_command == b'D' or current_command == b'Y':
                drowsy_alarm_active = True
                # mixer.music.play()
            else:
                drowsy_alarm_active = False
                # mixer.music.stop()

    # Clean up when stopped
    if ser:
        try:
            ser.write(b'S') # Reset LEDs to Safe before closing
        except:
            pass
    cap.release()
    print("SafelyDriven Engine: Monitoring Thread Stopped")

# --- Video Streaming Generator ---
def generate():
    global output_frame, is_monitoring
    while True:
        with lock:
            if output_frame is None:
                continue
            (flag, encodedImage) = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue
        
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
            bytearray(encodedImage) + b'\r\n')
        time.sleep(0.03) # Limit framerate for stability

# --- API Routes ---
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start', methods=['POST'])
def start_monitoring():
    global is_monitoring, monitor_thread, safety_score, drowsy_start_time, sos_triggered, sos_trigger_time, is_stressed, drowsy_alarm_active
    if not is_monitoring:
        if predict is None:
            return jsonify({
                "status": "error",
                "message": f"Missing or invalid landmark model: {LANDMARK_MODEL_PATH.name}",
            }), 503
        is_monitoring = True
        # Full Reset of All Session States
        safety_score = 100 
        drowsy_start_time = None
        sos_triggered = False
        sos_trigger_time = None
        is_stressed = False
        drowsy_alarm_active = False
        
        add_log("System Monitoring Started", "info")
        monitor_thread = threading.Thread(target=run_detector)
        monitor_thread.daemon = True
        monitor_thread.start()
        return jsonify({"status": "started", "message": "Detection loop initiated."})
    return jsonify({"status": "already_running"})

@app.route('/stop', methods=['POST'])
def stop_monitoring():
    global is_monitoring, output_frame
    is_monitoring = False
    with lock:
        output_frame = None
    add_log("System Monitoring Stopped", "info")
    return jsonify({"status": "stopped", "message": "Detection loop terminated."})

@app.route('/status')
def get_status():
    global current_ear, current_mar, ear_thresh, mar_thresh, current_blink_freq, safety_score, current_emotion, current_emotion_score, is_stressed, sos_triggered, EMERGENCY_CONTACT_PHONE, drowsy_alarm_active
    with lock:
        return jsonify({
            "is_monitoring": is_monitoring,
            "ear": round(current_ear, 3),
            "mar": round(current_mar, 3),
            "blink_freq": current_blink_freq,
            "safety_score": safety_score,
            "emotion": current_emotion,
            "emotion_score": current_emotion_score,
            "is_stressed": is_stressed,
            "sos_triggered": sos_triggered,
            "drowsy_alarm_active": drowsy_alarm_active,
            "arduino_connected": ser is not None,
            "ear_thresh": ear_thresh,
            "mar_thresh": mar_thresh,
            "emergency_contact": EMERGENCY_CONTACT_PHONE if EMERGENCY_CONTACT_PHONE else ""
        })

@app.route('/logs')
def get_logs():
    return jsonify({"logs": session_logs})

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    global ear_thresh, mar_thresh, EMERGENCY_CONTACT_PHONE
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Expected a JSON object."}), 400

    try:
        if 'ear_thresh' in data:
            value = float(data['ear_thresh'])
            if not 0 < value < 1:
                raise ValueError("EAR threshold must be between 0 and 1.")
            ear_thresh = value
            add_log(f"EAR Threshold changed to {ear_thresh}", "info")
        if 'mar_thresh' in data:
            value = float(data['mar_thresh'])
            if not 0 < value < 2:
                raise ValueError("MAR threshold must be between 0 and 2.")
            mar_thresh = value
            add_log(f"MAR Threshold changed to {mar_thresh}", "info")
    except (TypeError, ValueError) as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    if 'emergency_contact' in data:
        EMERGENCY_CONTACT_PHONE = data['emergency_contact']
        add_log(f"Emergency Contact updated to {EMERGENCY_CONTACT_PHONE}", "info")
    return jsonify({"status": "success"})

@app.route('/reconnect_arduino', methods=['POST'])
def reconnect_arduino():
    success = connect_arduino()
    return jsonify({"status": "success" if success else "failed"})

@app.route('/event_logs')
def get_event_logs():
    files = []
    if os.path.exists(EVENT_LOG_PATH):
        files = [f for f in os.listdir(EVENT_LOG_PATH) if f.endswith('.jpg')]
        files.sort(reverse=True)
    return jsonify({"snapshots": files})

@app.route('/event_log/<path:filename>')
def serve_event_log(filename):
    return send_from_directory(EVENT_LOG_PATH, filename)

if __name__ == '__main__':
    print(f"SafelyDriven Web Server running at http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True)
