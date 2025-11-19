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

        # SLIGHTLY MORE LENIENT PURPLE RANGE
        lower_purple = np.array([117, 60, 35])   # was [120, 80, 40]
        upper_purple = np.array([155, 255, 255]) # was [150, 255, 200]

        # Mask
        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)

        # LIGHT morphology — not too aggressive
        kernel = np.ones((3, 3), np.uint8)
        purple_mask = cv2.morphologyEx(purple_mask, cv2.MORPH_OPEN, kernel)
        purple_mask = cv2.morphologyEx(purple_mask, cv2.MORPH_CLOSE, kernel)

        # Slight blur to stabilize contour edges
        purple_mask = cv2.GaussianBlur(purple_mask, (5, 5), 0)

        contours, _ = cv2.findContours(
            purple_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        detected_balls = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 60:     # was 100
                continue

            (center, radius) = cv2.minEnclosingCircle(contour)
            x, y = center

            if radius < 15:    # was 20
                continue

            # gentler circularity threshold
            arc = cv2.arcLength(contour, True)
            if arc == 0:
                continue
            circularity = 4 * np.pi * area / (arc * arc)
            if circularity < 0.45:   # was 0.6
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
    FINAL KINEMATICS CONTROLLER — ready for ECE296 demo.
    Natural behavior:
      • Large misalignment → rotate only
      • Small misalignment → rotate + forward
      • Approaches smoothly, brakes automatically near target
      • No reverse (safe for L298N)
      • No strafing (stable)
    """

    if ball is None:
        return 0, 0, 0   # stop if no ball

    x, y, radius = ball

    # -------------------------
    # 1. Compute errors
    # -------------------------
    err_x = x - TARGET_X               # horizontal (pixels)
    err_r = TARGET_R - radius          # positive = too far

    # -------------------------
    # 2. ROTATION CONTROL (VX)
    # -------------------------
    if abs(err_x) <= X_DEADBAND:
        vx = 0
    else:
        # proportional turn
        vx = +Kp_ROT * err_x
        vx = max(-MAX_ROT, min(MAX_ROT, vx))  # clamp

    # If angle is large → do NOT move forward yet
    if abs(err_x) > X_ALIGN_PRIORITY:
        return int(vx), 0, 0

    # -------------------------
    # 3. FORWARD CONTROL (VY)
    # -------------------------
    if err_r <= 0:
        # Too close → no reverse (safe)
        vy = 0
    else:
        # proportional forward
        vy = Kp_FWD * err_r

        # CREEP MODE near the ball
        if radius > 350:
            vy = min(vy, 40)  # very gentle crawl

        # far away → allow more speed
        vy = min(vy, MAX_FWD)

    # -------------------------
    # 4. SMALL-ANGLE COUPLED MOTION
    # -------------------------
    # If alignment is close, allow mixed rotation + forward
    if abs(err_x) < 45:
        pass  # keep vx & vy as-is
    else:
        # mid misalignment → reduce forward to prevent diagonal drift
        vy = min(vy, 50)

    # -------------------------
    # 5. FINAL OUTPUT
    # -------------------------
    w = 0   # NO STRAFE — SAFE MODE

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
