import time
import serial
import threading

# -------- CONFIG --------
PORT = '/dev/ttyACM0'
BAUD = 9600

print("\n============================")
print("🧠  DORA CONTROL INTERFACE")
print(f"🔌  Port: {PORT} | Baud: {BAUD}")
print("============================\n")

# -------- TRY TO LOAD GUI --------
try:
    import tkinter as tk
    GUI_ENABLED = True
except Exception:
    print("⚠️  No display detected — GUI disabled.")
    GUI_ENABLED = False

# -------- SERIAL SETUP --------
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)  # allow Teensy reset
    print("✅  Serial connection established.\n")
except Exception as e:
    print(f"❌  Failed to open serial port: {e}")
    exit(1)

# -------- GLOBALS --------
keys_pressed = set()
last_command_time = time.time()


# -------- SEND COMMANDS --------
def send_command(cmd):
    global last_command_time
    try:
        ser.write((cmd + "\n").encode())
        last_command_time = time.time()
        print(f"Sent: {cmd}")
    except Exception as e:
        print("Serial error:", e)


# Immediately send STOP on startup
send_command("S")


# -------- FAILSAFE WATCHDOG --------
def watchdog():
    while True:
        if time.time() - last_command_time > 1.0:
            send_command("S")
        time.sleep(0.1)


# -------- HEADLESS MODE (REALTIME KEYBOARD) --------
def headless_mode():
    print("🧠  DORA Headless Mode Active — hold keys to drive.")
    print("Controls: W,A,S,D,Q,E | Ctrl+C to quit.\n")

    try:
        import keyboard  # requires `pip install keyboard`
    except ImportError:
        print("❌  Missing 'keyboard' library. Run: pip install keyboard")
        return

    threading.Thread(target=watchdog, daemon=True).start()

    # Key press handler
    def on_press(event):
        key = event.name.lower()
        if key not in keys_pressed:
            keys_pressed.add(key)
            mapping = {
                "w": "F",
                "s": "B",
                "a": "L",
                "d": "R",
                "q": "CCW",
                "e": "CW"
            }
            if key in mapping:
                send_command(mapping[key])

    # Key release handler
    def on_release(event):
        key = event.name.lower()
        if key in keys_pressed:
            keys_pressed.remove(key)
            send_command("S")

    # Register keyboard events
    keyboard.on_press(on_press)
    keyboard.on_release(on_release)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        send_command("S")
        ser.close()
        print("\n🛑  Session ended safely.")


# -------- GUI MODE --------
if GUI_ENABLED:
    try:
        root = tk.Tk()
        root.title("DORA Drive Control")

        def on_key_press(event):
            key = event.keysym.lower()
            if key not in keys_pressed:
                keys_pressed.add(key)
                mapping = {
                    "w": "F",
                    "s": "B",
                    "a": "L",
                    "d": "R",
                    "q": "CCW",
                    "e": "CW"
                }
                if key in mapping:
                    send_command(mapping[key])

        def on_key_release(event):
            key = event.keysym.lower()
            if key in keys_pressed:
                keys_pressed.remove(key)
                send_command("S")

        btns = {
            "Forward (W)": "F",
            "Backward (S)": "B",
            "Left (A)": "L",
            "Right (D)": "R",
            "Spin CW (E)": "CW",
            "Spin CCW (Q)": "CCW",
            "STOP": "S"
        }

        for i, (text, cmd) in enumerate(btns.items()):
            tk.Button(
                root, text=text, width=15, height=2,
                command=lambda c=cmd: send_command(c),
                font=('Arial', 12)
            ).grid(row=i, column=0, padx=5, pady=5)

        root.bind("<KeyPress>", on_key_press)
        root.bind("<KeyRelease>", on_key_release)

        def on_close():
            send_command("S")
            ser.close()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)
        threading.Thread(target=watchdog, daemon=True).start()

        print("🧠  GUI Mode Active — window launched.\n")
        root.mainloop()

    except tk.TclError:
        print("⚠️  No display available — switching to headless mode.\n")
        GUI_ENABLED = False
        headless_mode()
else:
    headless_mode()
