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
    #print(f"Argument provided: {sys.argv[1]}")
    if (sys.argv[1] == "debug"):
        debug = True
logging.basicConfig(
    filename='/tmp/ball_detect.log',  # Name of the log file
    filemode='a',                   # 'a' for append mode, 'w' for overwrite
    level=logging.INFO,             # Minimum level of messages to log (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s' # Format of log messages
)
class PurpleBallDetector:
    def __init__(self):
        self.picam2 = Picamera2()
        self.configure_camera()
        self.detection_radius = 20  # Minimum radius for detection

    def configure_camera(self):
        # Configure camera for color detection
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        #time.sleep(2)  # Allow camera to initialize

    def detect_purple_ball(self, frame):
        # Convert to HSV color space for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

        # Define range for purple color in HSV
        # Purple ranges from approximately 125-160 in HSV hue
        lower_purple = np.array([125, 50, 50])    # Lower bound for purple
        upper_purple = np.array([160, 255, 255])  # Upper bound for purple

        # Alternative ranges for different purple shades
        lower_purple_light = np.array([130, 40, 40])   # Lighter purple
        upper_purple_light = np.array([155, 255, 255]) # Lighter purple

        # Create masks for purple ranges
        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)
        purple_mask_light = cv2.inRange(hsv, lower_purple_light, upper_purple_light)

        # Combine masks
        final_mask = cv2.bitwise_or(purple_mask, purple_mask_light)

        # Clean up the mask using morphological operations
        kernel = np.ones((5, 5), np.uint8)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel)
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, kernel)

        # Find contours in the mask
        contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_balls = []

        for contour in contours:
            # Calculate area and filter small contours
            area = cv2.contourArea(contour)
            if area < 100:  # Minimum area threshold
                continue

            # Get the minimum enclosing circle
            ((x, y), radius) = cv2.minEnclosingCircle(contour)

            # Filter based on circularity and size
            if radius > self.detection_radius:
                circularity = 4 * np.pi * area / (cv2.arcLength(contour, True) ** 2)
                if circularity > 0.6:  # Reasonable circularity for balls
                    detected_balls.append((int(x), int(y), int(radius)))

        return detected_balls, final_mask

    def draw_detections(self, frame, balls):
        for (x, y, radius) in balls:
            # Draw circle around detected ball
            cv2.circle(frame, (x, y), radius, (255, 0, 0), 2)  # Blue circle
            # Draw center point
            cv2.circle(frame, (x, y), 2, (0, 255, 0), 3)  # Green center
            # Add text with coordinates
            cv2.putText(frame, f"Purple Ball: ({x}, {y})", (x - radius, y - radius - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Draw radius information
            cv2.putText(frame, f"Radius: {radius}px", (x - radius, y - radius - 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def run_detection(self):
        print("Starting purple ball detection...")
        print("Press 'q' to quit")
        print("Press 'h' to show HSV color calibration helper")

        show_hsv = False

        try:
            while True:
                # Capture frame
                frame = self.picam2.capture_array()

                # Detect purple balls
                balls, mask = self.detect_purple_ball(frame)

                # Draw detections on frame
                output_frame = frame.copy()
                self.draw_detections(output_frame, balls)

                # Display results
                if (debug == True): #draw windows
                    cv2.imshow('Purple Ball Detection', output_frame)
                    cv2.imshow('Purple Mask', mask)

                if show_hsv:
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    if (debug == True): #draw windows
                        cv2.imshow('HSV View', hsv_frame)

                # Print detection info
                if balls:
                    print(f"Detected {len(balls)} purple ball(s) at positions: {balls}")
                    logging.info(f"Detected {len(balls)} purple ball(s) at positions: {balls}")
                    if(len(balls) == 1):
                        print(f"Detected one ball!")
                        sendByte.send_to_teensy(1) ##send true that one ball was seen
                        x = balls[0][0]
                        y = balls[0][1]
                        radius = balls[0][2]
                        ###Byte map####
                        #0 = no ball
                        #1 = ball found
                        #2 = go forward
                        #3 = go right and forward
                        #4 = go left and forward
                        #5 = go left and back
                        #6 = go back
                        #7 = go right and back
                        #8 = stop
                        if( ((x >= 380) and (x <= 639)) and ( ((radius >=25) and (radius <= 60)) )):
                            print(f"SHOULD TURN RIGHT AND GO FORWARD")
                            sendByte.send_to_teensy(3)
                            #time.sleep(0.5) 
                        if( ((x >= 220) and (x <= 379)) and ( ((radius >=25) and (radius <= 399)) )):
                            print(f"GO FORWARD!")
                            sendByte.send_to_teensy(2)
                        if( ((x >= 20) and (x <= 200)) and ( ((radius >=25) and (radius <= 60)) )):
                            print(f"SHOULD TURN LEFT AND GO FORWARD")
                            sendByte.send_to_teensy(4)
                            
                if not balls:
                    sendByte.send_to_teensy(0)



                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('h'):
                    show_hsv = not show_hsv
                    if show_hsv:
                        print("HSV view enabled - useful for color calibration")
                    else:
                        cv2.destroyWindow('HSV View')

        except KeyboardInterrupt:
            print("\nStopping detection...")
        finally:
            cv2.destroyAllWindows()
            self.picam2.stop()

if __name__ == "__main__":
    print (f"Debug mode is {debug}")
    detector = PurpleBallDetector()
    detector.run_detection()
