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
def pattern_lawnmower(width_s=1.0, height_s=0.8, passes=4,
                      speed_pwm=130, strafe_pwm=110):
    """
    width_s   = seconds spent strafing each lane
    height_s  = seconds spent moving forward per pass
    passes    = number of sweep lines
    """
    direction = 1
    for p in range(passes):
        print(f"Pass {p+1}/{passes}")
        # forward sweep
        drive(0, speed_pwm, 0, height_s)
        # strafe to next lane
        drive(0, 0, strafe_pwm * direction, width_s)
        direction *= -1

    stop()
    print("✅ Sweep complete.")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("🟢 Starting DORA sweep sequence...")
    time.sleep(2)  # give Teensy time to boot
    pattern_lawnmower(width_s=1.0, height_s=1.2, passes=5)
    stop()
    ser.close()
