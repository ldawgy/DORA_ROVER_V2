#!/usr/bin/env python
import cv2
import numpy as np
from picamera2 import Picamera2
import time
import logging 
import sys
import sendByte 

debug = False
if len(sys.argv) > 1:
    if (sys.argv[1] == "debug"):
        debug = True

logging.basicConfig(
    filename='/tmp/ball_detect.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PurpleBallDetector:
    def __init__(self):
        self.picam2 = Picamera2()
        self.configure_camera()
        self.detection_radius = 20

    def configure_camera(self):
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()

    def detect_purple_ball(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

        lower_purple = np.array([125, 50, 50])
        upper_purple = np.array([160, 255, 255])

        lower_purple_light = np.array([130, 40, 40])
        upper_purple_light = np.array([155, 255, 255])

        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)
        purple_mask_light = cv2.inRange(hsv, lower_purple_light, upper_purple_light)

        final_mask = cv2.bitwise_or(purple_mask, purple_mask_light)

        kernel = np.ones((5, 5), np.uint8)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_balls = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:
                continue

            ((x, y), radius) = cv2.minEnclosingCircle(contour)

            if radius > self.detection_radius:
                arc = cv2.arcLength(contour, True)
                if arc == 0:
                    continue
                circularity = 4 * np.pi * area / (arc ** 2)
                if circularity > 0.6:
                    detected_balls.append((int(x), int(y), int(radius)))

        return detected_balls, final_mask

    def draw_detections(self, frame, balls):
        for (x, y, radius) in balls:
            cv2.circle(frame, (x, y), radius, (255, 0, 0), 2)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), 3)
            cv2.putText(frame, f"Purple Ball: ({x}, {y})", (x - radius, y - radius - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, f"Radius: {radius}px", (x - radius, y - radius - 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def run_detection(self):
        print("Starting purple ball detection...")
        print("Press 'q' to quit")
        print("Press 'h' to show HSV color calibration helper")

        show_hsv = False

        try:
            while True:
                frame = self.picam2.capture_array()

                balls, mask = self.detect_purple_ball(frame)

                output_frame = frame.copy()
                self.draw_detections(output_frame, balls)

                if (debug == True):
                    cv2.imshow('Purple Ball Detection', output_frame)
                    cv2.imshow('Purple Mask', mask)

                if show_hsv:
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    if (debug == True):
                        cv2.imshow('HSV View', hsv_frame)

                # ----------------------------------------------------
                # SAFE PATCHED BLOCK — NO MORE LIST INDEX ERRORS
                # ----------------------------------------------------
                if balls:
                    print(f"Detected {len(balls)} purple ball(s) at positions: {balls}")
                    logging.info(f"Detected {len(balls)} purple ball(s) at positions: {balls}")

                    # pick the "main" ball safely
                    main_ball = None

                    if len(balls) == 1:
                        main_ball = balls[0]
                    else:
                        # sort by radius descending, pick largest
                        try:
                            main_ball = sorted(balls, key=lambda b: b[2], reverse=True)[0]
                        except Exception as e:
                            print(f"[ERROR selecting ball] balls={balls}, error={e}")
                            logging.error(f"Ball selection error: {balls}")
                            main_ball = None

                    if main_ball is not None and len(main_ball) >= 3:
                        sendByte.send_to_teensy(1)

                        x, y, radius = main_ball

                        # Right + forward
                        if 380 <= x <= 639 and 25 <= radius <= 60:
                            print("SHOULD TURN RIGHT AND GO FORWARD")
                            sendByte.send_to_teensy(3)

                        # Forward
                        elif 220 <= x <= 379 and 25 <= radius <= 399:
                            print("GO FORWARD!")
                            sendByte.send_to_teensy(2)

                        # Left + forward
                        elif 20 <= x <= 200 and 25 <= radius <= 60:
                            print("SHOULD TURN LEFT AND GO FORWARD")
                            sendByte.send_to_teensy(4)

                        else:
                            print(f"Ball but no zone matched: x={x}, r={radius}")

                    else:
                        print(f"[WARN] Invalid main_ball: {main_ball}")
                        logging.warning(f"Invalid main_ball: {main_ball}")

                else:
                    sendByte.send_to_teensy(0)
                # ----------------------------------------------------

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('h'):
                    show_hsv = not show_hsv
                    if show_hsv:
                        print("HSV view enabled")
                    else:
                        cv2.destroyWindow('HSV View')

        except KeyboardInterrupt:
            print("\nStopping detection...")
        finally:
            cv2.destroyAllWindows()
            self.picam2.stop()

if __name__ == "__main__":
    print(f"Debug mode is {debug}")
    detector = PurpleBallDetector()
    detector.run_detection()

