"""
Hand Gesture Zoom Control (v6 - Lightweight smooth animation)
------------------------------------------------------------------
Camera background me chalta hai. Terminal me ek HALKA, SMOOTH,
single-line animation dikhta hai (bahut kam CPU/terminal load,
isliye atakta nahi) jo aapke thumb-index finger ki doori ke
hisaab se badhta/ghatta hai.

Kaise use karein:
1. Script run karein
2. Apna THUMB aur INDEX FINGER camera ke saamne dikhayein
3. Fingers PAAS laayein (pinch)  -> Zoom OUT
4. Fingers DOOR le jaayein (spread) -> Zoom IN
5. Band karne ke liye Terminal me Ctrl + C dabayein
"""

import cv2
import math
import time
import os
import sys
import urllib.request

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# ---------- Settings ----------
CAM_INDEX = 0
ZOOM_SENSITIVITY = 3
SMOOTHING_FRAMES = 10          # zyada frames = zyada stable distance
COOLDOWN_SECONDS = 0.18        # har frame pe trigger nahi hoga ab
MIN_DIFF_THRESHOLD = 6         # chhoti jitter ko ignore karega
DIRECTION_CONFIRM_FRAMES = 3   # itni baar same direction dikhe tabhi zoom trigger hoga
EMA_ALPHA = 0.3                # extra exponential smoothing (0-1, chhota = zyada smooth)
MODEL_PATH = "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

MAX_DISTANCE = 250      # approx max pinch distance in pixels
DISPLAY_FPS = 15        # terminal ko sirf itni baar per second update karo

GRID_ROWS = 9            # circle animation ki height (characters)
GRID_COLS = 23           # circle animation ki width (characters)
MIN_RADIUS_NORM = 0.12   # sabse chhota circle size (0-1 scale)
MAX_RADIUS_NORM = 1.0    # sabse bada circle size (0-1 scale)
# --------------------------------

import pyautogui
pyautogui.FAILSAFE = False

if not os.path.exists(MODEL_PATH):
    print("Hand-tracking model download ho raha hai (pehli baar, ~1-2 min)...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model download ho gaya!\n")

BaseOptions = mp_python.BaseOptions
HandLandmarker = mp_vision.HandLandmarker
HandLandmarkerOptions = mp_vision.HandLandmarkerOptions
VisionRunningMode = mp_vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_tracking_confidence=0.6,
)
landmarker = HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)   # chhota frame = kam CPU load
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

if not cap.isOpened():
    print("Webcam open nahi ho paya. CAM_INDEX badal ke try karein (0 -> 1).")
    sys.exit()

prev_distance = None
distance_history = []
ema_distance = None
last_zoom_time = 0
frame_timestamp_ms = 0
last_render_time = 0
frame_count = 0

pending_direction = None   # "IN" ya "OUT" jiska confirmation chal raha hai
pending_count = 0

COLOR_GREEN = "\x1b[32m"
COLOR_RED = "\x1b[31m"
COLOR_CYAN = "\x1b[36m"
COLOR_GRAY = "\x1b[90m"
COLOR_DIM_CYAN = "\x1b[2;36m"
RESET = "\x1b[0m"

SPINNER = ["\u28CB", "\u28D9", "\u28E4", "\u28E2", "\u28E1", "\u28D1", "\u2887", "\u2847"]
spin_idx = 0

CENTER_R = GRID_ROWS // 2
CENTER_C = GRID_COLS // 2


def zoom_shade(dist, radius_norm):
    """Distance se ek 'lens' jaisa gradient character return karta hai."""
    if radius_norm <= 0 or dist > radius_norm:
        return None
    edge_frac = (radius_norm - dist) / radius_norm
    if edge_frac < 0.15:
        return "\u2591"   # ░ halka edge
    elif edge_frac < 0.35:
        return "\u2592"   # ▒
    elif edge_frac < 0.6:
        return "\u2593"   # ▓
    else:
        return "\u2588"   # █ solid core


def build_zoom_frame(hand_visible, smooth_distance, status_label, spin_char):
    """Ek 'zoom lens' circle ka multi-line ASCII frame banata hai (list of strings)."""
    if status_label.strip() == "ZOOM IN":
        color = COLOR_GREEN
    elif status_label.strip() == "ZOOM OUT":
        color = COLOR_RED
    elif hand_visible:
        color = COLOR_CYAN
    else:
        color = COLOR_GRAY

    radius_norm = 0.0
    if hand_visible:
        t = min(max(smooth_distance / MAX_DISTANCE, 0.0), 1.0)
        radius_norm = MIN_RADIUS_NORM + (MAX_RADIUS_NORM - MIN_RADIUS_NORM) * t

    lines = []
    for r in range(GRID_ROWS):
        row_chars = []
        for c in range(GRID_COLS):
            ny = (r - CENTER_R) / (GRID_ROWS / 2)
            nx = (c - CENTER_C) / (GRID_COLS / 2)
            dist = math.hypot(nx, ny)
            ch = zoom_shade(dist, radius_norm) if hand_visible else None
            row_chars.append(ch if ch else " ")
        lines.append(f" {color}{''.join(row_chars)}{RESET}")

    if not hand_visible:
        status_text = f"{COLOR_GRAY}{spin_char} Hath dhoondh raha hoon...{RESET}"
    else:
        pct = int(min(smooth_distance / MAX_DISTANCE, 1.0) * 100)
        status_text = f" {spin_char} {color}{status_label or 'TRACKING '}{RESET}  {COLOR_DIM_CYAN}({pct}%){RESET}"

    lines.append("")
    lines.append(f" {status_text}")
    return lines


prev_frame_line_count = 0

sys.stdout.write("\x1b[?25l")  # hide cursor
sys.stdout.flush()

print("=" * 50)
print(" Hand Gesture Zoom Control")
print(" Thumb + Index finger dikhayein. Ctrl+C se band karein.")
print("=" * 50)
print()

try:
    while True:
        success, frame = cap.read()
        if not success:
            print("\nFrame nahi mil raha, webcam check karein.")
            break

        # Hand tracking - HAR frame pe (taaki zoom smooth/responsive rahe)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        frame_timestamp_ms += 33
        result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        status_label = ""
        hand_visible = False
        smooth_distance = 0

        if result.hand_landmarks:
            hand_visible = True
            hand_landmarks = result.hand_landmarks[0]
            thumb_tip = hand_landmarks[4]
            index_tip = hand_landmarks[8]

            h, w = frame.shape[:2]
            thumb_x, thumb_y = thumb_tip.x * w, thumb_tip.y * h
            index_x, index_y = index_tip.x * w, index_tip.y * h

            distance = math.hypot(index_x - thumb_x, index_y - thumb_y)

            # Layer 1: simple moving average
            distance_history.append(distance)
            if len(distance_history) > SMOOTHING_FRAMES:
                distance_history.pop(0)
            moving_avg = sum(distance_history) / len(distance_history)

            # Layer 2: exponential moving average (extra smoothing on top)
            if ema_distance is None:
                ema_distance = moving_avg
            else:
                ema_distance = EMA_ALPHA * moving_avg + (1 - EMA_ALPHA) * ema_distance
            smooth_distance = ema_distance

            if prev_distance is not None:
                diff = smooth_distance - prev_distance
                now = time.time()

                if abs(diff) > MIN_DIFF_THRESHOLD:
                    direction = "IN" if diff > 0 else "OUT"

                    # Direction confirmation: noise ke chhote spikes ko ignore karta hai
                    if direction == pending_direction:
                        pending_count += 1
                    else:
                        pending_direction = direction
                        pending_count = 1

                    if pending_count >= DIRECTION_CONFIRM_FRAMES and (now - last_zoom_time) > COOLDOWN_SECONDS:
                        scroll_amount = int(diff * ZOOM_SENSITIVITY)
                        if scroll_amount != 0:
                            pyautogui.keyDown('ctrl')
                            pyautogui.scroll(scroll_amount)
                            pyautogui.keyUp('ctrl')
                            last_zoom_time = now
                            status_label = "ZOOM IN " if diff > 0 else "ZOOM OUT"
                        pending_count = 0
                else:
                    # diff dead-zone ke andar hai -> koi jitter nahi, reset confirmation
                    pending_direction = None
                    pending_count = 0

            prev_distance = smooth_distance
        else:
            prev_distance = None
            distance_history.clear()
            ema_distance = None
            pending_direction = None
            pending_count = 0

        # ---- TERMINAL UPDATE: throttled, sirf DISPLAY_FPS baar/second ----
        now = time.time()
        if now - last_render_time >= (1.0 / DISPLAY_FPS):
            last_render_time = now
            spin_idx = (spin_idx + 1) % len(SPINNER)
            spin_char = SPINNER[spin_idx]

            frame_lines = build_zoom_frame(hand_visible, smooth_distance, status_label, spin_char)

            if prev_frame_line_count > 0:
                sys.stdout.write(f"\x1b[{prev_frame_line_count}A")  # cursor upar le jao
            for fl in frame_lines:
                sys.stdout.write("\r\x1b[2K" + fl + "\n")            # line clear karke likho
            prev_frame_line_count = len(frame_lines)
            sys.stdout.flush()

except KeyboardInterrupt:
    pass

finally:
    cap.release()
    sys.stdout.write("\x1b[?25h")  # show cursor again
    print("\n\nProgram band ho gaya. Dhanyavaad!")
