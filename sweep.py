#!/usr/bin/env python3
import serial, time, sys

# ---------------- Serial Setup ----------------
PORT = "/dev/ttyACM0"
BAUD = 9600
FRAME = 0.05    # 50 ms → 20 Hz control loop

print("🟢 Initializing serial link to Teensy...")
ser = serial.Serial(PORT, BAUD, timeout=0.1)
time.sleep(2)  # give Teensy time to boot

# ---------------- Motion Helpers ---------------
def send(vx, vy, w):
    """Send velocity packet to Teensy."""
    packet = f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n"
    ser.write(packet.encode("utf-8"))
    ser.flush()

def stop():
    ser.write(b"S\n")
    ser.flush()
    print("🛑 STOP command sent.")
    time.sleep(0.25)

def check_color_detection():
    """
    Read from Teensy serial.
    Returns True if HuskyLens detects color ("Color:ID1" or "K1").
    """
    try:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            if "Color:ID1" in line or line.startswith("K1"):
                print(f"🎨 Color Detected → {line}")
                return True
    except Exception as e:
        print("Serial read error:", e)
    return False

def drive(vx, vy, w, duration):
    """
    Hold velocity for duration seconds,
    but if color detected — STOP FOREVER.
    """
    t0 = time.time()
    while time.time() - t0 < duration:
        if check_color_detection():
            stop()
            print("🧠 DORA has detected color and will remain stopped forever.")
            ser.close()
            sys.exit(0)  # terminate script permanently
        send(vx, vy, w)
        time.sleep(FRAME)
    stop()

# ---------------- Square Exploration Pattern -----------
def pattern_square_explore(side_time=1.2, turn_time=0.35,
                           speed_pwm=130, turn_pwm=100, passes=4):
    """
    Forward-only square pattern.
    Stops permanently if color detected at any point.
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
    try:
        pattern_square_explore(side_time=1.2, turn_time=0.35,
                               speed_pwm=130, turn_pwm=100, passes=4)
    except KeyboardInterrupt:
        print("\n🧠 Interrupted by user.")
    finally:
        stop()
        ser.close()
        print("🔌 Serial closed. Goodbye!")


    stop()
    ser.close()


