#!/usr/bin/env python3
import time
import threading
import cv2

# ---- Local Imports ----
from sweep import pattern_square_1p5m, stop as sweep_stop, ser, drive
from object_detector import PurpleBallDetector   # rename your file to object_detector.py
                                                  # OR change this import to match your file name

# ======================================================
#   STATE MACHINE
# ======================================================
RUN_SWEEP = True         # Sweep until a ball is detected
BALL_FOUND = False       # Global flag set by camera thread
BALL_DATA = None         # (x,y,radius)
LOCK = threading.Lock()  # Protect shared data


# ======================================================
#   CAMERA THREAD
# ======================================================
def camera_loop():
    global BALL_FOUND, BALL_DATA, RUN_SWEEP

    detector = PurpleBallDetector()
    print("📷 Camera thread running...")

    while RUN_SWEEP:  # Only search during sweep phase
        frame = detector.picam2.capture_array()

        balls, _ = detector.detect_purple_ball(frame)

        if balls:
            x, y, radius = balls[0]  # Take largest/first ball

            with LOCK:
                BALL_FOUND = True
                BALL_DATA = (x, y, radius)
                RUN_SWEEP = False   # Signal main sweep loop to stop

            print(f"🟣 BALL DETECTED! {BALL_DATA}")
            return  # stop camera loop once ball is detected

        # A tiny sleep avoids 100% CPU
        time.sleep(0.01)

    detector.picam2.stop()
    cv2.destroyAllWindows()
    print("📷 Camera thread stopped.")


# ======================================================
#   BEHAVIOR BASED ON BALL POSITION
# ======================================================
def track_ball():
    """
    Drive using VX (rotation), VY (forward), W (strafe)
    Based on ball position (x) and distance (radius)
    """

    print("🎯 Tracking ball...")
    global BALL_DATA

    while True:
        with LOCK:
            if BALL_DATA is None:
                continue
            x, y, radius = BALL_DATA

        # Byte map in object detector:
        # x region + radius → behavior

        vx = 0
        vy = 0
        w = 0

        # -------------------------
        # Right + forward
        # -------------------------
        if 380 <= x <= 639 and 25 <= radius <= 60:
            vx = +120   # rotate right (your “VX is rotation” rule)
            vy = 150    # forward

        # -------------------------
        # Forward
        # -------------------------
        elif 220 <= x <= 379 and 25 <= radius <= 399:
            vx = 0
            vy = 150

        # -------------------------
        # Left + forward
        # -------------------------
        elif 20 <= x <= 200 and 25 <= radius <= 60:
            vx = -120   # rotate left
            vy = 150

        else:
            # No valid behavior → stop
            vx = vy = w = 0

        packet = f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n"
        ser.write(packet.encode())
        ser.flush()

        time.sleep(0.05)  # 20 Hz

    # unreachable but for safety:
    sweep_stop()


# ======================================================
#   MAIN LOOP
# ======================================================
def main():
    global RUN_SWEEP, BALL_FOUND

    print("🟢 Starting robot MAIN PROGRAM...")
    time.sleep(2)

    # Start camera thread
    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()

    # -------------------------------
    # Phase 1: Sweep until ball seen
    # -------------------------------
    print("🟦 Phase 1: Sweep Pattern Running...")
    pattern_square_1p5m(
        side_m=1.5,
        speed_mps=0.30,
        forward_pwm=130,
        turn_pwm=100,
        turn_time=0.35
    )

    # If sweep ends naturally and ball not seen → still check flag
    if not BALL_FOUND:
        print("🟡 Sweep finished but no ball detected yet… waiting for camera…")
        while not BALL_FOUND:
            time.sleep(0.1)

    print("🟣 BALL FOUND! BREAKING SWEEP!")
    sweep_stop()

    # -------------------------------
    # Phase 2: Track the Ball
    # -------------------------------
    track_ball()


# ======================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sweep_stop()
        ser.close()
        print("\n🟥 Program terminated by user.")
