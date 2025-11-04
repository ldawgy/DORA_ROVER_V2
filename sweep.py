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
    time.sleep(0.25)   # small settle delay

# ---------------- Square Exploration Pattern -----------
def pattern_square_explore(side_time=1.2, turn_time=0.35,
                            speed_pwm=130, turn_pwm=100, passes=4):
    """
    Forward-only square pattern:
    - Move forward one side
    - Turn 90° right (clockwise)
    - Repeat for 4 sides (default)
    """

    print(f"🟢 Starting DORA EXPLORA pattern ({passes} sides)...")

    for i in range(passes):
        print(f"🟩 Side {i+1}/{passes}: Moving forward")
        drive(0, speed_pwm, 0, side_time)

        print("↩️ Turning right 90°")
        drive(turn_pwm, 0, 0, turn_time)

    stop()
    print("✅ DORA EXPLORA pattern complete!")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🟢 Initializing serial link to Teensy...")
    time.sleep(2)  # give Teensy time to boot

    # Adjust side_time and turn_time for your setup
    pattern_square_explore(side_time=1.2, turn_time=0.35,
                           speed_pwm=130, turn_pwm=100, passes=4)

    stop()
    ser.close()


