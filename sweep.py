#!/usr/bin/env python3
import serial, time

# =========================================================
# 🧭 DORA SWEEP v2 — "DORA the Explora" Edition
# Forward-only lawnmower search pattern with 180° turns.
# =========================================================

# ---------------- Serial Setup ----------------
PORT = "/dev/ttyACM0"
BAUD = 9600
FRAME = 0.05    # 50 ms → 20 Hz control loop
ser = serial.Serial(PORT, BAUD, timeout=1)

# ---------------- Motion Helpers ---------------
def send(vx, vy, w):
    """
    Send velocity packet to Teensy.
    NOTE: baseline convention => VX = rotation, VY = forward, W = strafe
    """
    packet = f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n"
    ser.write(packet.encode("utf-8"))
    ser.flush()

def stop():
    ser.write(b"S\n")
    ser.flush()

def drive(vx, vy, w, duration):
    """Hold a velocity for a set time (seconds)."""
    t0 = time.time()
    while time.time() - t0 < duration:
        send(vx, vy, w)
        time.sleep(FRAME)
    stop()
    time.sleep(0.25)   # short settle pause

# ---------------- Pattern Definition -----------
def pattern_explora(width_s=1.0, height_s=1.2, passes=5,
                    speed_pwm=130, strafe_pwm=110,
                    turn_pwm=100, turn_time=0.6):
    """
    FORWARD-ONLY lawnmower sweep pattern.
    Moves forward each lane, turns 180°, strafes to next lane, and continues forward.
    """

    print(f"🟢 Starting DORA Explora sweep ({passes} passes)...")

    for p in range(passes):
        print(f"🟩 Pass {p+1}/{passes}: FORWARD")
        # Drive forward along the lane
        drive(0, speed_pwm, 0, height_s)

        # Skip turn/strafe after final pass
        if p == passes - 1:
            break

        # Turn 180° at end of lane
        print("↪️ Turning 180°")
        drive(turn_pwm, 0, 0, turn_time)
        stop()

        # Strafe sideways to the next lane
        print("➡️ Shifting to next lane")
        drive(0, 0, strafe_pwm, width_s)
        stop()

        # Turn back to original heading (now facing forward again)
        print("↩️ Re-aligning heading")
        drive(-turn_pwm, 0, 0, turn_time)
        stop()

    stop()
    print("✅ Sweep complete — Dora has explored the area!")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🚀 Booting DORA the Explora sweep sequence...")
    time.sleep(2)  # give Teensy time to boot
    pattern_explora(width_s=1.0, height_s=1.2, passes=5,
                    speed_pwm=130, strafe_pwm=110,
                    turn_pwm=100, turn_time=0.6)
    stop()
    ser.close()


