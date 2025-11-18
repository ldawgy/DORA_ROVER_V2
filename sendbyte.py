#!/usr/bin/env python
import serial
import time
ser = serial.Serial(
    port='/dev/ttyACM0', #default raspberry pi serial 
    baudrate=9600,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1  # Timeout in seconds for read operations
)


def send_to_teensy(myByte):
    byte_to_send = bytes([myByte])
    ser.write(byte_to_send)
