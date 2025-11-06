#!/usr/bin/env python3
import serial, time, math

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
    time.sleep(0.25)   # small settle delay

# ---------------- Zig-Zag Forward Scan Pattern -----------
def pattern_zigzag_scan(width_s=1.0, height_s=1.2, passes=6,
                        forward_pwm=130, strafe_pwm=90, turn_pwm=0):
    """
    Continuous forward 'zig-zag' pattern:
    - move diagonally forward-right
    - move diagonally forward-left
    - repeat, always progressing forward
    """
    print(f"🟢 Starting DORA ZIG-ZAG SCAN ({passes} segments)...")

    direction = 1  # start strafing right first
    for p in range(passes):
        print(f"🟩 Segment {p+1}/{passes}: moving forward + {'right' if direction==1 else 'left'}")

        # combine forward motion and lateral strafe
        vy = forward_pwm
        w = strafe_pwm * direction
        drive(0, vy, w, height_s)

        # gentle yaw correction if you want a subtle camera sweep (optional)
        if turn_pwm != 0:
            print("↩️ slight heading correction turn")
            drive(turn_pwm * direction, 0, 0, 0.2)

        # alternate strafe direction each pass
        direction *= -1

    stop()
    print("✅ Zig-zag scan complete!")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🟢 Initializing serial link to Teensy...")
    time.sleep(2)  # give Teensy time to boot

    # adjust width_s / height_s as needed for your test area
    pattern_zigzag_scan(width_s=1.0, height_s=1.2, passes=8,
                        forward_pwm=130, strafe_pwm=90, turn_pwm=0)

    stop()
    ser.close()



    stop()
    ser.close()


