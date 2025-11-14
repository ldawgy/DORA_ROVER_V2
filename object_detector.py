#!/usr/bin/env python3

import cv2
import numpy as np
from picamera2 import Picamera2
import time
import logging
import sys
import sendByte

debug = False
if len(sys.argv) > 1:
    if sys.argv[1] == "debug":
        debug = True

logging.basicConfig(
    filename="/tmp/ball_detect.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
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

        contours, _ = cv2.findContours(
            final_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        detected_balls = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:
                continue

            (center, radius) = cv2.minEnclosingCircle(contour)
            x, y = center

            if radius > self.detection_radius:
                arc = cv2.arcLength(contour, True)
                if arc == 0:
                    continue

                circularity = 4 * np.pi * area / (arc * arc)
                if circularity > 0.6:
                    detected_balls.append(
                        (int(x), int(y), int(radius))
                    )

        return detected_balls, final_mask

    def draw_detections(self, frame, balls):
        for (x, y, radius) in balls:
            cv2.circle(frame, (x, y), radius, (255, 0, 0), 2)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), 3)
            cv2.putText(
                frame,
                "Purple Ball: ({}, {})".format(x, y),
                (x - radius, y - radius - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            cv2.putText(
                frame,
                "Radius: {}px".format(radius),
                (x - radius, y - radius - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

    def run_detection(self):
        print("Starting purple ball detection...")
        print("Press 'q' to quit")
        print("Press 'h' to show HSV helper")

        show_hsv = False

        try:
            while True:
                frame = self.picam2.capture_array()
                balls, mask = self.detect_purple_ball(frame)

                output_frame = frame.copy()
                self.draw_detections(output_frame, balls)

                if debug:
                    cv2.imshow("Purple Ball Detection", output_frame)
                    cv2.imshow("Purple Mask", mask)

                if show_hsv and debug:
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    cv2.imshow("HSV View", hsv_frame)

                if balls:
                    logging.info("Detected {} purple ball(s): {}".format(
                        len(balls),
                        balls
                    ))
                    print("Detected {} purple ball(s): {}".format(
                        len(balls),
                        balls
                    ))

                    main_ball = None

                    if len(balls) == 1:
                        main_ball = balls[0]
                    else:
                        try:
                            main_ball = sorted(
                                balls,
                                key=lambda b: b[2],
                                reverse=True
                            )[0]
                        except Exception as e:
                            print("Error selecting main ball:", e)
                            logging.error("Ball selection error: {}".format(balls))
                            main_ball = None

                    if (
                        main_ball is not None
                        and isinstance(main_ball, tuple)
                        and len(main_ball) == 3
                    ):
                        x, y, radius = main_ball
                        sendByte.send_to_teensy(1)

                        if 380 <= x <= 639 and 25 <= radius <= 60:
                            print("Right and forward")
                            sendByte.send_to_teensy(3)
                        elif 220 <= x <= 379 and 25 <= radius <= 399:
                            print("Forward")
                            sendByte.send_to_teensy(2)
                        elif 20 <= x <= 200 and 25 <= radius <= 60:
                            print("Left and forward")
                            sendByte.send_to_teensy(4)
                        else:
                            print("Ball detected, no motion zone matched")
                    else:
                        print("Invalid main_ball:", main_ball)
                        logging.warning("Invalid main_ball: {}".format(main_ball))
                else:
                    sendByte.send_to_teensy(0)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("h"):
                    show_hsv = not show_hsv
                    if show_hsv:
                        print("HSV view on")
                    else:
                        cv2.destroyWindow("HSV View")

        except KeyboardInterrupt:
            print("Stopping detection...")

        finally:
            cv2.destroyAllWindows()
            self.picam2.stop()

if __name__ == "__main__":
    print("Debug mode is {}".format(debug))
    detector = PurpleBallDetector()
    detector.run_detection()


