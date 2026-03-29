# Moves Servo by a configurable step size via UART
# Authored by Omar Sartaj

import serial
import time

STEP_SIZE = 10           # Edit this to change step size 
PORT = "/dev/ttyACM0"
BAUD = 115200

def main():
    print(f"Opening {PORT}...")
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(2)

    ser.reset_input_buffer()

    cmd = f"STEP {STEP_SIZE}\n"
    print(f"Sending: {cmd.strip()}")
    ser.write(cmd.encode())

    response = ser.readline().decode(errors="ignore").strip()
    print(f"Teensy: {response}")

    ser.close()

if __name__ == "__main__":
    main()
