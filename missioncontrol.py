#!/usr/bin/env python3
import time
import threading
import cv2
import os

from sweep import pattern_square_1p5m, stop as sweep_stop, ser, drive
from object_detector import PurpleBallDetector


# ======================================================
# GLOBAL STATE FLAGS
# ======================================================
RUN_SWEEP = True
BALL_FOUND = False
STOP_ALL = False
BALL_DATA = None
LOCK = threading.Lock()


# ======================================================
# STOP ALL VELOCITY
# ======================================================
def send_stop():
    """Send zero velocity packet to Teensy."""
    try:
        ser.write(b"VX:0,VY:0,W:0\n")
        ser.flush()
    except:
        pass


# ======================================================
# CAMERA THREAD
# ======================================================
def camera_loop():
    global BALL_FOUND, BALL_DATA, RUN_SWEEP, STOP_ALL

    detector = PurpleBallDetector()
    print("📷 Camera thread running...")

    while RUN_SWEEP and not STOP_ALL:
        frame = detector.picam2.capture_array()
        balls, _ = detector.detect_purple_ball(frame)

        if balls:
            x, y, radius = balls[0]

            with LOCK:
                BALL_FOUND = True
                STOP_ALL = True
                BALL_DATA = (x, y, radius)
                RUN_SWEEP = False

            print(f"🟣 BALL DETECTED! {BALL_DATA}")

            # ---- HARD TERMINATE EVERYTHING ----
            send_stop()
            sweep_stop()
            print("🟥 TERMINATING PROGRAM DUE TO BALL DETECTION")
            time.sleep(0.1)
            os._exit(0)   # <- FINAL KILL SWITCH

        time.sleep(0.01)

    detector.picam2.stop()
    cv2.destroyAllWindows()
    print("📷 Camera thread stopped.")


# ======================================================
# MAIN LOOP
# ======================================================
def main():
    global RUN_SWEEP, BALL_FOUND, STOP_ALL

    print("🟢 Starting robot MAIN PROGRAM...")
    time.sleep(2)

    # ---- Start camera thread ----
    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()

    # ---- Phase 1: Sweep pattern ----
    print("🟦 Phase 1: Sweep Pattern Running...")
    pattern_square_1p5m(
        side_m=1.5,
        speed_mps=0.30,
        forward_pwm=130,
        turn_pwm=100,
        turn_time=0.35
    )

    # If sweep ends before ball spotted
    if not BALL_FOUND:
        print("🟡 Sweep finished but no ball detected… waiting for camera…")
        while not BALL_FOUND and not STOP_ALL:
            time.sleep(0.1)

    print("🟣 BALL FOUND! BREAKING SWEEP!")

    STOP_ALL = True
    sweep_stop()
    send_stop()

    print("🟥 ALL MOVEMENT STOPPED DUE TO BALL DETECTION")
    print("Program complete.")


# ======================================================
# PROGRAM ENTRY
# ======================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🟥 Program terminated by user.")
        sweep_stop()
        send_stop()
        ser.close()


