import cv2
import numpy as np
from pupil_apriltags import Detector
import math, time, socket, json

# ------------ CONFIG ------------
ARENA_TAGS = {  # meters; change if arena isn’t 1x1
    0: (0.0, 0.0),   # bottom-left
    1: (1.0, 0.0),   # bottom-right
    2: (0.0, 1.0),   # top-left
    3: (1.0, 1.0)    # top-right
}
ROVER_TAG_ID = 10
TAG_SIZE = 0.065
CAMERA_PARAMS = (600, 600, 320, 240)  # fx, fy, cx, cy (approx)
SMOOTHING_ALPHA = 0.2                 # 0=frozen, 1=no smoothing
PI_IP = "192.168.1.211"               # <<< PUT YOUR PI’S IP HERE
PORT = 5005
HOMOGRAPHY_MAX_AGE_S = 3.0            # reuse last H this long if corners drop
# ---------------------------------

smoothed_pose = None
H_last, H_last_ts = None, 0.0

def rotation_matrix_to_yaw(R):
    sy = math.sqrt(R[0,0]**2 + R[1,0]**2)
    yaw = math.atan2(R[1,0], R[0,0]) if sy >= 1e-6 else 0.0
    return math.degrees(yaw)

def main():
    global smoothed_pose, H_last, H_last_ts

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    detector = Detector(families="tag36h11")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    last_print = 0.0

    cv2.namedWindow("AprilTag Detection", cv2.WINDOW_NORMAL)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Error: Failed to read frame.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dets = detector.detect(
            gray, estimate_tag_pose=True,
            camera_params=CAMERA_PARAMS, tag_size=TAG_SIZE
        )

        arena_pts, arena_xy = [], []
        rover_pixel, rover_yaw = None, None

        for d in dets:
            corners = d.corners.astype(int)
            cx, cy = np.mean(corners, axis=0).astype(int)
            cv2.polylines(frame, [corners], True, (0,255,0), 2)
            cv2.putText(frame, f"ID:{d.tag_id}", (cx, cy+40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

            if d.tag_id == ROVER_TAG_ID and d.pose_R is not None:
                rover_pixel = (cx, cy)
                rover_yaw = rotation_matrix_to_yaw(np.array(d.pose_R))
                cv2.putText(frame, f"Yaw:{rover_yaw:.1f}", (cx, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

            if d.tag_id in ARENA_TAGS:
                arena_pts.append([cx, cy])
                arena_xy.append(ARENA_TAGS[d.tag_id])

        world_pt = None

        # Compute/update homography if all 4 corners are visible
        if len(arena_pts) == 4:
            H, _ = cv2.findHomography(np.float32(arena_pts), np.float32(arena_xy))
            if H is not None:
                H_last, H_last_ts = H, time.time()

        # Use current or recent homography to project rover center → arena XY
        if rover_pixel is not None and H_last is not None and (time.time() - H_last_ts) <= HOMOGRAPHY_MAX_AGE_S:
            px = np.array([[rover_pixel]], dtype=np.float32)
            world_pt = cv2.perspectiveTransform(px, H_last)[0][0]  # (x,y)

        # If we have a world point, smooth + send it to the Pi
        if world_pt is not None and rover_yaw is not None:
            new_pose = {"x": float(world_pt[0]), "y": float(world_pt[1]), "yaw": float(rover_yaw)}
            if smoothed_pose is None:
                smoothed_pose = new_pose
            else:
                smoothed_pose = {
                    "x": (1-SMOOTHING_ALPHA)*smoothed_pose["x"] + SMOOTHING_ALPHA*new_pose["x"],
                    "y": (1-SMOOTHING_ALPHA)*smoothed_pose["y"] + SMOOTHING_ALPHA*new_pose["y"],
                    "yaw": (1-SMOOTHING_ALPHA)*smoothed_pose["yaw"] + SMOOTHING_ALPHA*new_pose["yaw"],
                }

            msg = {**smoothed_pose, "stamp": time.time()}
            sock.sendto(json.dumps(msg).encode("utf-8"), (PI_IP, PORT))

            if time.time() - last_print > 0.5:
                print(f"TX -> X:{smoothed_pose['x']:.2f} Y:{smoothed_pose['y']:.2f} Yaw:{smoothed_pose['yaw']:.1f}")
                last_print = time.time()

            cv2.putText(frame, f"X:{smoothed_pose['x']:.2f}m Y:{smoothed_pose['y']:.2f}m",
                        (30,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

        cv2.imshow("AprilTag Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    sock.close()

if __name__ == "__main__":
    main()


      
