#!/usr/bin/env python3
import serial, time

# ---------------- Serial Setup ----------------
PORT = "/dev/ttyACM0"
BAUD = 9600
ser = serial.Serial(PORT, BAUD, timeout=1)
FRAME = 0.05    # 50 ms → 20 Hz control loop

# ---------------- Motion Helpers ---------------
def send(vx, vy, w):
    """
    Send velocity packet to Teensy.
    NOTE: VX = rotation, VY = forward, W = strafe
    """
    packet = f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n"
    ser.write(packet.encode("utf-8"))
    ser.flush()

def stop():
    ser.write(b"S\n")
    ser.flush()

def drive(vx, vy, w, duration):
    """Hold a velocity for given seconds."""
    t0 = time.time()
    while time.time() - t0 < duration:
        send(vx, vy, w)
        time.sleep(FRAME)
    stop()
    time.sleep(0.25)

# ---------------------------------------------------
# 🟥🟦 1.5 m × 1.5 m SQUARE EXPLORATION PATTERN
# ---------------------------------------------------
def pattern_square_1p5m(
        side_m=1.5,
        speed_mps=0.30,
        forward_pwm=130,
        turn_pwm=100,
        turn_time=0.35):

    """
    Drive a square of a given size in meters.
    We convert meters → seconds using approximate rover speed.
    """

    # estimate duration for one side
    side_time = side_m / speed_mps

    print(f"🟢 Starting 1.5m square: side_time ≈ {side_time:.2f} sec")

    for i in range(4):
        print(f"🟩 Side {i+1}/4 — Forward {side_m} m")
        drive(0, forward_pwm, 0, side_time)

        print("↩️ 90° Right Turn")
        drive(turn_pwm, 0, 0, turn_time)

    stop()
    print("✅ Completed 1.5 × 1.5 meter square!")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🟢 Initializing serial link to Teensy...")
    time.sleep(2)

    pattern_square_1p5m(
        side_m=1.5,
        speed_mps=0.30,
        forward_pwm=130,
        turn_pwm=100,
        turn_time=0.35
    )

    stop()
    ser.close()


