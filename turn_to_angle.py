#!/usr/bin/env python3
import serial, time

PORT = "/dev/ttyACM0"
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

def send(cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()
    print(f"> Sent: {cmd}")

def wait_for_completion():
    """
    Blocks until Teensy reports 'Turn complete' message.
    This message comes from your firmware in updateOtosTurnPID().
    """
    print("  Waiting for turn to finish...")
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print("    Teensy:", line)
            if "Turn complete" in line:
                return
        time.sleep(0.05)

def run_turn_experiment(trials=10, delta_angle=90):
    print("\n=== TURN-TO-ANGLE EXPERIMENT ===")
    print(f"Performing {trials} turns of {delta_angle}° each.")
    print("Place rover on protractor reference line. Starting in 5 seconds...\n")
    time.sleep(5)

    for i in range(1, trials + 1):
        print(f"\n--- Trial {i}/{trials} ---")

        # Send turn command
        send(f"TURN:{delta_angle}")

        # Wait for Teensy to reach target heading
        wait_for_completion()

        print("  Turn finished. Record the final heading on your protractor.")

        # Give user measurement time
        MEASURE_TIME = 6
        for t in range(MEASURE_TIME, 0, -1):
            print(f"    Logging pause: {t}s", end="\r")
            time.sleep(1)
        print()

    print("\n=== EXPERIMENT COMPLETE ===\n")

if __name__ == "__main__":
    try:
        run_turn_experiment(trials=10, delta_angle=90)
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        ser.close()
