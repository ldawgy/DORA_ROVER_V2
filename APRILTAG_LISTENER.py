# apriltag_listener.py  (PI SIDE)
import socket, json

UDP_HOST = "0.0.0.0"   # listen on all interfaces
UDP_PORT = 5005

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    print(f"[Pi Listener] Waiting on UDP {UDP_PORT} ...")

    while True:
        data, addr = sock.recvfrom(2048)
        try:
            pose = json.loads(data.decode("utf-8"))
            x = pose.get("x"); y = pose.get("y"); yaw = pose.get("yaw")
            print(f"RX from {addr[0]} -> X:{x:.2f} m  Y:{y:.2f} m  Yaw:{yaw:.1f}°")
        except Exception as e:
            print("Bad packet:", e)

if __name__ == "__main__":
    main()
