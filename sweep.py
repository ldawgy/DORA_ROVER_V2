#!/usr/bin/env python3
import serial, time

PORT = "/dev/ttyACM0"
BAUD = 9600
FRAME = 0.05
ser = serial.Serial(PORT, BAUD, timeout=1)

def send(vx, vy, w):
    ser.write(f"VX:{int(vx)},VY:{int(vy)},W:{int(w)}\n".encode())
    ser.flush()

def stop():
    ser.write(b"S\n"); ser.flush()

def drive(vx, vy, w, dur):
    t0 = time.time()
    while time.time() - t0 < dur:
        send(vx, vy, w)
        time.sleep(FRAME)
    stop(); time.sleep(0.1)

def pattern_square(side=1.5, mps=0.30, fwd=130, turn=100, tturn=0.35):
    side_t = side / mps
    for _ in range(4):
        drive(0, fwd, 0, side_t)   # forward
        drive(turn, 0, 0, tturn)   # rotate 90
    stop()

if __name__ == "__main__":
    time.sleep(2)
    pattern_square()
    ser.close()


    stop()
    ser.close()


