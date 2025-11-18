#!/usr/bin/env python3

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import logging
import sys
import serial

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
    filename="/tmp/ball_follow.log",
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


# ==========================
# TARGET / TUNING PARAMS
# ==========================

# Mission-complete condition (from your notes)
TARGET_X = 486
TARGET_Y = 15
TARGET_R = 390

# Tolerances (how close is “good enough”)
TOL_X = 25
TOL_Y = 25
TOL_R = 40

# Control gains (tune these)
Kp_ROT = 0.4   # pixels → rotation command
Kp_FWD = 0.5   # radius error → forward command

# Command caps (MUST stay gentle for L298Ns)
MAX_ROT = 90    # |VX| ≤ 90
MAX_FWD = 110   # |VY| ≤ 110

# Deadbands to avoid jitter
X_DEADBAND = 25          # px: inside this, don't rotate
X_ALIGN_PRIORITY = 60    # px: if outside this, rotate-only (no forward)
R_DEADBAND = 30          # px radius error: inside this, don't move forward


# ==========================
# PURPLE BALL DETECTOR
# ==========================
def detect_purple_ball(self, frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

    # Balanced purple range (not too strict, not too loose)
    lower_purple = np.array([115, 70, 40])   # requires some saturation & value
    upper_purple = np.array([155, 255, 255])

    mask = cv2.inRange(hsv, lower_purple, upper_purple)

    # Light smoothing: keeps blobs intact but reduces speckle noise
    mask = cv2.GaussianBlur(mask, (5, 5), 0)

    # Optional small opening to remove random specks
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 60:        # stricter than 20, looser than 100
            continue

        (center, radius) = cv2.minEnclosingCircle(contour)
        x, y = center

        if radius < 12:      # slightly forgiving but not too small
            continue

        # Add mild circularity check (prevents random purple noise)
        arc = cv2.arcLength(contour, True)
        if arc == 0:
            continue

        circularity = 4 * np.pi * area / (arc * arc)
        if circularity < 0.40:   # not too strict (was 0.6)
            continue

        detected.append((int(x), int(y), int(radius)))

    return detected, mask



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
    """Check if we're at the desired final pose."""
    if ball is None:
        return False
    x, y, r = ball
    return (
        abs(x - TARGET_X) <= TOL_X and
        abs(y - TARGET_Y) <= TOL_Y and
        abs(r - TARGET_R) <= TOL_R
    )


def compute_commands(ball):
    """
    Map ball (x, y, radius) → (VX, VY, W) in a gentle, L298N-safe way.
    """
    if ball is None:
        return 0, 0, 0  # no ball = stop

    x, y, radius = ball

    # ----- Rotation (VX) based on x error -----
    err_x = x - TARGET_X

    if abs(err_x) <= X_DEADBAND:
        vx = 0
    else:
        vx = -Kp_ROT * err_x  # sign may need flipping if turns the wrong way
        if vx > 0:
            vx = min(vx, MAX_ROT)
        else:
            vx = max(vx, -MAX_ROT)

    # ----- Forward (VY) based on radius error -----
    err_r = TARGET_R - radius  # positive = too far (need forward)

    if abs(err_r) <= R_DEADBAND:
        vy = 0
    else:
        # Gentle forward only; no aggressive backing up for now
        if err_r > 0:
            vy = Kp_FWD * err_r
            vy = min(vy, MAX_FWD)
        else:
            # too close: for now, just stop instead of reversing
            vy = 0

    # ----- Priority: align before charging -----
    if abs(err_x) > X_ALIGN_PRIORITY:
        # If badly misaligned, rotate in place; don't drive forward
        vy = 0

    # No strafing to keep it gentle
    w = 0

    return int(vx), int(vy), int(w)


# ==========================
# MAIN LOOP
# ==========================
def main():
    print(f"Debug mode is {debug}")
    detector = PurpleBallDetector()

    show_hsv = False
    last_state = "INIT"

    try:
        print("Starting purple ball FOLLOWING...")
        print("Press 'q' in debug window to quit.")

        while True:
            frame = detector.picam2.capture_array()
            balls, mask = detector.detect_purple_ball(frame)

            output_frame = frame.copy()
            detector.draw_detections(output_frame, balls)

            main_ball = None
            if balls:
                # pick the largest ball (closest)
                main_ball = max(balls, key=lambda b: b[2])

            # 1) Check mission complete
            if mission_complete(main_ball):
                state = "AT_TARGET"
                stop()
                msg = f"✅ Mission complete at ball {main_ball}"
                print(msg)
                logging.info(msg)
                # You can break here if you want the script to end:
                # break
            else:
                # 2) Compute gentle movement commands
                vx, vy, w = compute_commands(main_ball)

                if main_ball is None:
                    state = "NO_BALL"
                    stop()
                else:
                    x, y, r = main_ball
                    state = f"TRACKING x={x} y={y} r={r} | cmd VX={vx} VY={vy} W={w}"
                    send(vx, vy, w)

                if state != last_state:
                    logging.info(state)
                    last_state = state

                print(state)

            # 3) Debug windows
            if debug:
                cv2.imshow("Purple Ball Detection", output_frame)
                cv2.imshow("Purple Mask", mask)
                if show_hsv:
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    cv2.imshow("HSV View", hsv_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("h"):
                    show_hsv = not show_hsv
                    if show_hsv:
                        print("HSV view on")
                    else:
                        try:
                            cv2.destroyWindow("HSV View")
                        except cv2.error:
                            pass
            else:
                # Headless mode: just keep loop at ~20Hz
                time.sleep(FRAME)

    except KeyboardInterrupt:
        print("KeyboardInterrupt → stopping rover.")

    finally:
        stop()
        cv2.destroyAllWindows()
        detector.picam2.stop()
        ser.close()
        print("Clean shutdown complete.")


if __name__ == "__main__":
    main()
