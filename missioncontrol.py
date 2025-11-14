#!/usr/bin/env python3
import time
import threading
import cv2

from sweep import pattern_square_1p5m, stop as sweep_stop, ser, drive
from object_detector import PurpleBallDetector

# ======================================================
# STATE MACHINE FLAGS
# ======================================================
RUN_SWEEP = True
BALL_FOUND = False
STOP_ALL = False
BALL_DATA = None
LOCK = threading.Lock()


# ======================================================
# IMMEDIATE STOP FUNCTION
# ======================================================
def send_stop():
    """Send zero velocity packet."""
    ser.write(b"VX:0,VY:0,W:0\n")
    ser.flush()


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
                STOP_ALL = True    # <<<<<< NEW: Immediate stop trigger
                BALL_DATA = (x, y, radius)
                RUN_SWEEP = False

            print(f"🟣 BALL DETECTED! {BALL_DATA}")
            return

        time.sleep(0.01)

    detector.picam2.stop()
    cv2.destroyAllWindows()
    print("📷 Camera thread stopped.")


# ======================================================
# (NO TRACKING ALLOWED ANYMORE)
# ======================================================
def track_ball():
    """This will no longer be used when STOP_ALL == True."""
    global STOP_ALL

    print("🎯 Tracking ball... (but STOP_ALL overrides this)")

    while not STOP_ALL:
        time.sleep(0.05)

    # Force stop
    send_stop()
    sweep_stop()


# ======================================================
# MAIN LOOP
# ======================================================
def main():
    global RUN_SWEEP, BALL_FOUND, STOP_ALL

    print("🟢 Starting robot MAIN PROGRAM...")
    time.sleep(2)

    # Start camera thread
    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()

    # Phase 1: Sweep
    print("🟦 Phase 1: Sweep Pattern Running...")
    pattern_square_1p5m(
        side_m=1.5,
        speed_mps=0.30,
        forward_pwm=130,
        turn_pwm=100,
        turn_time=0.35
    )

    # If sweep ends and camera hasn't triggered yet
    if not BALL_FOUND:
        print("🟡 Sweep finished but no ball detected… waiting for camera…")
        while not BALL_FOUND and not STOP_ALL:
            time.sleep(0.1)

    print("🟣 BALL FOUND! BREAKING SWEEP!")

    # Stop movement immediately
    STOP_ALL = True
    sweep_stop()
    send_stop()

    print("🟥 ALL MOVEMENT STOPPED DUE TO BALL DETECTION")
    print("Program complete.")

    return


# ======================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sweep_stop()
        send_stop()
        ser.close()
        print("\n🟥 Program terminated by user.")

