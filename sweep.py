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
    NOTE: baseline convention => VX = rotation, VY = forward, W = strafe
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
    time.sleep(0.3)   # brief settle pause

# ---------------- Pattern Definition -----------
def pattern_lawnmower(width_s=1.0, height_s=1.2, passes=5,
                      speed_pwm=130, strafe_pwm=110, turn_pwm=100, turn_time=0.6):
    """
    Realistic 'search' pattern with rotation turns at each end.
    width_s   = time to strafe between lanes
    height_s  = time to drive forward along a lane
    passes    = number of passes (lanes)
    turn_pwm  = rotation PWM for turning
    turn_time = time spent rotating 180 degrees (tune this)
    """
    direction = 1  # forward first

    for p in range(passes):
        print(f"🟩 Pass {p+1}/{passes}: driving {'forward' if direction==1 else 'backward'}")

        # Drive straight (forward or backward)
        drive(0, speed_pwm * direction, 0, height_s)

        # End of pass rotation (simulate turn like a real mower)
        print("↪️ Turning 180°")
        drive(turn_pwm * direction, 0, 0, turn_time)  # rotate CW or CCW depending on direction
        stop()

        # Strafe to next lane (side shift)
        if p != passes - 1:  # skip last lane
            print("➡️ Shifting to next lane")
            drive(0, 0, strafe_pwm, width_s)
            stop()

        # Rotate back to face original direction for next pass
        print("↩️ Re-aligning heading")
        drive(-turn_pwm * direction, 0, 0, turn_time)
        stop()

        direction *= -1  # flip driving direction

    stop()
    print("✅ Full lawnmower pattern complete!")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🟢 Starting DORA sweep sequence with rotation turns...")
    time.sleep(2)  # give Teensy time to boot
    pattern_lawnmower(width_s=1.0, height_s=1.2, passes=5,
                      speed_pwm=130, strafe_pwm=110, turn_pwm=100, turn_time=0.6)
    stop()
    ser.close()


