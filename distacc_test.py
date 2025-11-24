#!/usr/bin/env python3
import serial, time

PORT  = "/dev/ttyACM0"
BAUD  = 9600
FRAME = 0.05

# -------------------------
# SERIAL SETUP
# -------------------------
ser = serial.Serial(PORT, BAUD, timeout=1)

def send(vx, vy, w):
    ser.write(f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n".encode())
    ser.flush()

def stop():
    ser.write(b"S\n")
    ser.flush()

def drive(vx, vy, w, dur):
    """Send constant velocity for duration (sec)."""
    t0 = time.time()
    while time.time() - t0 < dur:
        send(vx, vy, w)
        time.sleep(FRAME)
    stop()
    time.sleep(0.2)


# ----------------------------------------------------------
# MOTION COMMANDS FOR EXPERIMENT
# ----------------------------------------------------------
FWD_SPEED = 130
REV_SPEED = -130

# UPDATED REAL MEASURED SPEED (no calibration, just fixed)
MPS       = 0.305     # corrected from 0.30
PAUSE     = 45        # seconds of stop time at each 0.5m mark


# ----------------------------------------------------------
# DRIVE EXACTLY 0.5 METERS, THEN STOP FOR MEASUREMENT
# ----------------------------------------------------------
def drive_half_meter(vy_speed):
    duration = 0.5 / MPS     # time = distance / mps
    drive(0, vy_speed, 0, duration)
    stop()
    print(f"Reached next 0.5m mark. WAITING {PAUSE} seconds for measurement.")
    time.sleep(PAUSE)


# ----------------------------------------------------------
# FULL 5 METER PASS (FORWARD or BACKWARD)
# ----------------------------------------------------------
def run_pass(vy_speed, label="FORWARD"):
    print(f"\n=== STARTING {label} PASS ===")
    print("Align the rover on the 0-meter mark. Starting in 5 seconds...")
    time.sleep(5)

    # 10 stops → 0.5m, 1.0m, ..., 5.0m
    for i in range(1, 11):
        dist = i * 0.5
        print(f"\nMoving to {dist:.2f} meters...")
        drive_half_meter(vy_speed)

    stop()
    print(f"\n=== {label} PASS COMPLETE ===\n")


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------
if __name__ == "__main__":
    try:
        time.sleep(2)

        # FORWARD 5m
        run_pass(FWD_SPEED, label="FORWARD")

        print("\nTake a break and re-align the rover at the 0-meter mark for backward run...")
        time.sleep(20)

        # BACKWARD 5m
        run_pass(REV_SPEED, label="BACKWARD")

        stop()
        ser.close()

    except KeyboardInterrupt:
        stop()
        ser.close()
        print("Experiment interrupted.")
