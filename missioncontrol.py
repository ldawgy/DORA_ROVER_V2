#!/usr/bin/env python3

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import logging
import sys
import serial
import threading

# ==========================
# DEBUG FLAG
# ==========================
debug = False
if len(sys.argv) > 1 and sys.argv[1] == "debug":
    debug = True

# ==========================
# LOGGING
# ==========================
logging.basicConfig(
    filename="/tmp/ball_sweep_follow.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================
# SERIAL / ROVER CONTROL
# ==========================
PORT = "/dev/ttyACM0"
BAUD = 9600
FRAME = 0.05  # 50 ms → 20 Hz

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)  # allow Teensy to boot/reset


def send(vx, vy, w):
    """
    Send velocity packet to Teensy.
    Coordinate frame (from firmware):
      VX = rotation (X axis)
      VY = forward  (Y axis)
      W  = strafe   (R axis)
    """
    packet = f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n"
    ser.write(packet.encode("utf-8"))
    ser.flush()


def stop():
    """Send stop command."""
    try:
        ser.write(b"S\n")
        ser.flush()
    except Exception as e:
        print("Stop serial error:", e)


def hard_break():
    """
    STRONG BREAK: spam stop a few times quickly.
    This is what forces the rover out of sweep into follow behavior.
    """
    print("🛑 HARD BREAK → STOPPING SWEEP & ROVER")
    for _ in range(5):
        stop()
        time.sleep(0.05)


# ==========================
# GLOBAL STATE FLAGS
# ==========================
RUN_SWEEP = True      # controls sweep thread
STOP_ALL = False      # global shutdown
BALL_FOUND = False    # latched once we see a ball
BALL_DATA = None      # (x, y, r) from camera thread

LOCK = threading.Lock()


# ==========================
# SWEEP PATTERN (from sweep.py)
# ==========================
def drive_for_duration(vx, vy, w, dur):
    """
    Sweep-only drive primitive.
    Respect RUN_SWEEP, STOP_ALL, and BALL_FOUND so we can break out early.
    """
    global RUN_SWEEP, STOP_ALL, BALL_FOUND

    t0 = time.time()
    while (time.time() - t0 < dur and
           RUN_SWEEP and
           not STOP_ALL and
           not BALL_FOUND):
        send(vx, vy, w)
        time.sleep(FRAME)

    stop()
    time.sleep(0.1)


def pattern_square_sweep(side=1.5, mps=0.30, fwd=130, turn=100, tturn=5):
    """
    Same behavior as your sweep.pattern_square but cooperative with the state machine.
    """
    global RUN_SWEEP, STOP_ALL, BALL_FOUND

    side_t = side / mps
    for _ in range(4):
        if STOP_ALL or BALL_FOUND or not RUN_SWEEP:
            break
        # forward
        drive_for_duration(0, fwd, 0, side_t)

        if STOP_ALL or BALL_FOUND or not RUN_SWEEP:
            break
        # rotate 90
        drive_for_duration(turn, 0, 0, tturn)

    stop()


def sweep_thread_fn():
    """
    Thread that runs the square pattern until:
      - BALL_FOUND becomes True, or
      - RUN_SWEEP is set False, or
      - STOP_ALL is True.
    """
    print("🧹 SWEEP thread starting...")
    try:
        pattern_square_sweep()
    except Exception as e:
        print("Sweep thread error:", e)
    finally:
        print("🧹 SWEEP thread exiting.")
        stop()


# ==========================
# TARGET / TUNING PARAMS (from your follow script)
# ==========================

TARGET_X = 486
TARGET_Y = 15
TARGET_R = 390

TOL_X = 25
TOL_Y = 25
TOL_R = 40

Kp_ROT = 0.4   # pixels → rotation command
Kp_FWD = 0.5   # radius error → forward command

MAX_ROT = 90    # |VX| ≤ 90
MAX_FWD = 110   # |VY| ≤ 110

X_DEADBAND = 25
X_ALIGN_PRIORITY = 120
R_DEADBAND = 30


# ==========================
# PURPLE BALL DETECTOR
# ==========================
class PurpleBallDetector:
    def __init__(self):
        self.picam2 = Picamera2()
        self.configure_camera()
        self.detection_radius = 20  # minimum radius in px

    def configure_camera(self):
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

    def detect_purple_ball(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

        lower_purple = np.array([117, 60, 35])
        upper_purple = np.array([155, 255, 255])

        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)

        kernel = np.ones((3, 3), np.uint8)
        purple_mask = cv2.morphologyEx(purple_mask, cv2.MORPH_OPEN, kernel)
        purple_mask = cv2.morphologyEx(purple_mask, cv2.MORPH_CLOSE, kernel)

        purple_mask = cv2.GaussianBlur(purple_mask, (5, 5), 0)

        contours, _ = cv2.findContours(
            purple_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        detected_balls = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 60:
                continue

            (center, radius) = cv2.minEnclosingCircle(contour)
            x, y = center

            if radius < 15:
                continue

            arc = cv2.arcLength(contour, True)
            if arc == 0:
                continue
            circularity = 4 * np.pi * area / (arc * arc)
            if circularity < 0.45:
                continue

            detected_balls.append((int(x), int(y), int(radius)))

        return detected_balls, purple_mask

    def draw_detections(self, frame, balls):
        for (x, y, radius) in balls:
            cv2.circle(frame, (x, y), radius, (255, 0, 0), 2)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), 3)
            cv2.putText(
                frame,
                f"Purple Ball: ({x}, {y})",
                (x - radius, y - radius - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            cv2.putText(
                frame,
                f"Radius: {radius}px",
                (x - radius, y - radius - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )


# ==========================
# CONTROL LOGIC
# ==========================
def mission_complete(ball):
    if ball is None:
        return False
    x, y, r = ball
    return (
        abs(x - TARGET_X) <= TOL_X and
        abs(y - TARGET_Y) <= TOL_Y and
        abs(r - TARGET_R) <= TOL_R
    )


def compute_commands(ball):
    if ball is None:
        return 0, 0, 0

    x, y, radius = ball

    err_x = x - TARGET_X
    err_r = TARGET_R - radius  # positive = too far

    # --- ROTATION (VX) ---
    if abs(err_x) <= X_DEADBAND:
        vx = 0
    else:
        vx = +Kp_ROT * err_x
        vx = max(-MAX_ROT, min(MAX_ROT, vx))

    # --- FORWARD (VY) ---
    if err_r <= 0:
        vy = 0
    else:
        vy = Kp_FWD * err_r
        if radius > 350:
            vy = min(vy, 40)
        vy = min(vy, MAX_FWD)

    # --- COUPLED MOTION ---
    if abs(err_x) >= 45:
        vy = min(vy, 50)

    w = 0  # no strafe

    return int(vx), int(vy), int(w)


# ==========================
# CAMERA THREAD
# ==========================
def camera_thread_fn(detector):
    """
    Continuously updates BALL_DATA and BALL_FOUND.
    Also handles optional debug windows.
    """
    global BALL_FOUND, BALL_DATA, STOP_ALL

    print("📷 Camera thread starting...")
    show_hsv = False

    try:
        while not STOP_ALL:
            frame = detector.picam2.capture_array()
            balls, mask = detector.detect_purple_ball(frame)

            main_ball = None
            if balls:
                main_ball = max(balls, key=lambda b: b[2])

            with LOCK:
                BALL_DATA = main_ball
                if main_ball is not None:
                    if not BALL_FOUND:
                        print(f"🟣 BALL DETECTED! {main_ball}")
                        logging.info(f"Ball detected: {main_ball}")
                    BALL_FOUND = True

            # --- debug windows ---
            if debug:
                output_frame = frame.copy()
                detector.draw_detections(output_frame, balls)

                cv2.imshow("Purple Ball Detection", output_frame)
                cv2.imshow("Purple Mask", mask)

                if show_hsv:
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    cv2.imshow("HSV View", hsv_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    STOP_ALL = True
                    break
                elif key == ord("h"):
                    show_hsv = not show_hsv
                    if not show_hsv:
                        try:
                            cv2.destroyWindow("HSV View")
                        except cv2.error:
                            pass
            else:
                time.sleep(FRAME)

    except Exception as e:
        print("Camera thread error:", e)
    finally:
        print("📷 Camera thread exiting.")
        detector.picam2.stop()


# ==========================
# FOLLOW LOOP (runs on main thread AFTER break)
# ==========================
def follow_loop():
    global STOP_ALL

    print("🎯 ENTERING FOLLOW MODE...")
    last_state = "INIT"

    while not STOP_ALL:
        with LOCK:
            ball = BALL_DATA

        if mission_complete(ball):
            state = f"✅ Mission complete at ball {ball}"
            print(state)
            logging.info(state)
            stop()
            STOP_ALL = True
            break

        if ball is None:
            state = "NO_BALL → STOP"
            stop()
        else:
            vx, vy, w = compute_commands(ball)
            x, y, r = ball
            state = f"TRACKING x={x} y={y} r={r} | cmd VX={vx} VY={vy} W={w}"
            send(vx, vy, w)

        if state != last_state:
            logging.info(state)
            last_state = state

        print(state)
        time.sleep(FRAME)


# ==========================
# MAIN
# ==========================
def main():
    global RUN_SWEEP, STOP_ALL, BALL_FOUND

    print(f"Debug mode is {debug}")
    detector = PurpleBallDetector()

    # Start threads
    cam_thread = threading.Thread(
        target=camera_thread_fn, args=(detector,), daemon=True
    )
    sweep_thread = threading.Thread(
        target=sweep_thread_fn, daemon=True
    )

    cam_thread.start()
    sweep_thread.start()

    print("🚗 Starting in SWEEP mode. Waiting for ball...")

    try:
        # 1) Wait until a ball is seen (or shutdown)
        while not STOP_ALL and not BALL_FOUND:
            time.sleep(0.05)

        if STOP_ALL:
            print("STOP_ALL set before ball detected. Exiting.")
            return

        # 2) We saw a ball → kill sweep & hard break
        RUN_SWEEP = False
        hard_break()

        # Optional: give sweep thread a moment to exit
        time.sleep(0.2)

        # 3) Enter follow mode on main thread
        follow_loop()

    except KeyboardInterrupt:
        print("KeyboardInterrupt → stopping rover.")
        STOP_ALL = True
    finally:
        print("Cleaning up...")
        STOP_ALL = True
        RUN_SWEEP = False
        stop()
        time.sleep(0.1)
        try:
            cam_thread.join(timeout=1.0)
            sweep_thread.join(timeout=1.0)
        except RuntimeError:
            pass
        cv2.destroyAllWindows()
        ser.close()
        print("Clean shutdown complete.")


if __name__ == "__main__":
    main()



