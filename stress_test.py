#!/usr/bin/env python3
import serial, time

PORT  = "/dev/ttyACM0"
BAUD  = 9600
FRAME = 0.05

ser = serial.Serial(PORT, BAUD, timeout=1)

def send(vx, vy, w):
    ser.write(f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n".encode())
    ser.flush()

def stop():
    ser.write(b"S\n")
    ser.flush()

def drive(vx, vy, w, dur):
    t0 = time.time()
    while time.time() - t0 < dur:
        send(vx, vy, w)
        time.sleep(FRAME)
    stop()
    time.sleep(0.1)


# ----------------------------------------------------------
# SPEED CONSTANTS (adjust if needed)
# ----------------------------------------------------------
FWD  = 130
BACK = -130
LEFT = -130
RIGHT = 130
CW   = 120
CCW  = -120

BURST = 0.75   # 0.75-second movement
REST  = 0.25   # optional rest between motions

TEST_DURATION = 5 * 60   # 5-minute stress test


# ----------------------------------------------------------
# MAIN TEST LOOP
# ----------------------------------------------------------
if __name__ == "__main__":
    print("Starting 5-minute stress test in 3 seconds...")
    time.sleep(3)
    start = time.time()

    try:
        while time.time() - start < TEST_DURATION:

            print("[+] Forward burst")
            drive(0, FWD, 0, BURST)
            time.sleep(REST)

            print("[+] Backward burst")
            drive(0, BACK, 0, BURST)
            time.sleep(REST)

            print("[+] Strafe Left")
            drive(LEFT, 0, 0, BURST)
            time.sleep(REST)

            print("[+] Strafe Right")
            drive(RIGHT, 0, 0, BURST)
            time.sleep(REST)

            print("[+] Rotate CCW")
            drive(0, 0, CCW, BURST)
            time.sleep(REST)

            print("[+] Rotate CW")
            drive(0, 0, CW, BURST)
            time.sleep(REST)

        print("\n=== STRESS TEST COMPLETE ===")

    except KeyboardInterrupt:
        print("\nInterrupted manually.")
    finally:
        stop()
        ser.close()

