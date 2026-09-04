# Hand Gesture Zoom Control

Control zoom (Ctrl + Scroll) on your screen using just your **thumb and index finger** — no mouse, no keyboard. A lightweight webcam-based hand tracker reads the distance between your fingers and triggers zoom in/out, with a smooth animated visualizer right in your terminal.

## Features

- 🖐️ **Pinch to zoom out, spread to zoom in** — natural gesture control
- 🎯 Single-hand tracking using [MediaPipe](https://developers.google.com/mediapipe)
- 🎨 Smooth, low-CPU ASCII "lens" animation in the terminal (no GUI window needed)
- 🧠 Double-layer smoothing (moving average + exponential moving average) to avoid jittery zoom
- ⏱️ Direction-confirmation + cooldown logic so accidental hand shake doesn't spam-zoom
- ⚡ Runs the camera in the background — only a lightweight terminal animation is shown

## How It Works

1. The webcam captures your hand in the background (no video window pops up).
2. MediaPipe's Hand Landmarker detects your **thumb tip** and **index finger tip**.
3. The distance between them is smoothed and tracked frame-to-frame.
4. When that distance increases or decreases significantly and consistently, the script sends a `Ctrl + Scroll` event via `pyautogui` to zoom in or out on whatever app is focused.
5. A small animated circle in the terminal grows/shrinks and changes color to reflect your pinch distance in real time.

## Requirements

- Python 3.8+
- A working webcam
- Packages:
  ```bash
  pip install opencv-python mediapipe pyautogui
  ```

> On first run, the script automatically downloads the MediaPipe hand-tracking model (`hand_landmarker.task`, ~1–2 min) if it isn't already present.

## Usage

```bash
python hand_gesture_zoom.py
```

1. Run the script.
2. Hold up your **thumb and index finger** in front of the camera.
3. **Bring fingers together (pinch)** → Zoom **OUT**
4. **Move fingers apart (spread)** → Zoom **IN**
5. Press **Ctrl + C** in the terminal to stop.

## Terminal Display Guide

| Symbol / Color | Meaning |
|---|---|
| Gray spinner | No hand detected — searching |
| Cyan circle | Hand detected, tracking |
| Green `ZOOM IN` | Zoom-in triggered |
| Red `ZOOM OUT` | Zoom-out triggered |
| Circle size | Reflects current pinch distance (bigger = fingers farther apart) |

## Configuration

All tunable settings are at the top of the script:

| Setting | Description | Default |
|---|---|---|
| `CAM_INDEX` | Which webcam to use (`0`, `1`, ...) | `0` |
| `ZOOM_SENSITIVITY` | How strongly a distance change affects zoom | `3` |
| `SMOOTHING_FRAMES` | Frames averaged for distance smoothing | `10` |
| `EMA_ALPHA` | Extra exponential smoothing factor (lower = smoother) | `0.3` |
| `COOLDOWN_SECONDS` | Minimum time between zoom triggers | `0.18` |
| `MIN_DIFF_THRESHOLD` | Minimum distance change to count as intentional movement | `6` |
| `DIRECTION_CONFIRM_FRAMES` | Consecutive same-direction frames needed before triggering zoom | `3` |
| `DISPLAY_FPS` | How often the terminal animation refreshes per second | `15` |
| `MAX_DISTANCE` | Approx. max pinch distance (pixels) used to scale the animation | `250` |

Adjust these if zoom feels too sensitive, too slow, or too jittery for your setup.

## Troubleshooting

- **"Webcam open nahi ho paya" / camera won't open** → Try changing `CAM_INDEX` from `0` to `1` (or vice versa).
- **Zoom feels jumpy** → Increase `SMOOTHING_FRAMES`, lower `EMA_ALPHA`, or increase `MIN_DIFF_THRESHOLD`.
- **Zoom doesn't trigger at all** → Lower `MIN_DIFF_THRESHOLD` or `DIRECTION_CONFIRM_FRAMES`.
- **Terminal animation looks broken/misaligned** → Use a terminal that supports ANSI escape codes and Unicode block characters (most modern terminals do).

## Stopping the Program

Press **Ctrl + C** in the terminal at any time. The webcam is released and the cursor is restored automatically.
