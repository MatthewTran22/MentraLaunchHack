import cv2
import mediapipe as mp
import numpy as np
import math

class FingerGunDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

        # Track thumb position for cocking detection
        self.prev_thumb_y = {}  # Store previous thumb Y position for each hand
        self.is_cocked = {}  # Track if gun is cocked for each hand
        self.cock_threshold = 0.02  # Minimum movement to register as cocking
        self.shoot_cooldown = {}  # Prevent rapid fire
        self.cooldown_frames = 10

    def is_finger_extended(self, landmarks, finger_tip_id, finger_pip_id):
        tip = landmarks[finger_tip_id]
        pip = landmarks[finger_pip_id]
        return tip.y < pip.y

    def is_finger_gun(self, hand_landmarks):
        landmarks = hand_landmarks.landmark

        # For POV (first-person), the hand appears from the side/bottom of frame
        # Index finger should be pointing forward (away from camera)
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        index_mcp = landmarks[5]
        wrist = landmarks[0]

        # Index finger extended forward (towards camera/screen)
        # Check if index is extended using Z-depth (closer to camera = smaller z)
        index_extended = index_tip.z < index_pip.z

        # Also check traditional Y extension as backup
        index_extended_y = index_tip.y < index_pip.y
        index_extended = index_extended or index_extended_y

        # Thumb should be up (perpendicular to index)
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]

        # For POV, thumb up means lower Y value OR significant X offset
        thumb_up = thumb_tip.y < thumb_mcp.y or abs(thumb_tip.x - thumb_mcp.x) > 0.08

        # Check if middle, ring, and pinky fingers are curled
        # For POV, curled means tips are not extending forward in Z
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        # Fingers curled if not extending forward or if Y values indicate curl
        middle_curled = middle_tip.z >= middle_pip.z or middle_tip.y >= middle_pip.y
        ring_curled = ring_tip.z >= ring_pip.z or ring_tip.y >= ring_pip.y
        pinky_curled = pinky_tip.z >= pinky_pip.z or pinky_tip.y >= pinky_pip.y

        # Finger gun: index extended forward, thumb up, others curled
        return index_extended and thumb_up and middle_curled and ring_curled and pinky_curled

    def get_finger_direction(self, landmarks, frame_shape):
        h, w, _ = frame_shape

        # Get index finger tip (landmark 8) and PIP joint (landmark 6)
        tip = landmarks[8]
        pip = landmarks[6]

        # Convert normalized coordinates to pixel coordinates
        tip_x, tip_y = int(tip.x * w), int(tip.y * h)
        pip_x, pip_y = int(pip.x * w), int(pip.y * h)

        # Calculate direction vector
        dx = tip_x - pip_x
        dy = tip_y - pip_y

        # Normalize the vector
        length = math.sqrt(dx**2 + dy**2)
        if length > 0:
            dx /= length
            dy /= length

        return tip_x, tip_y, dx, dy

    def detect_cock_motion(self, hand_landmarks, hand_id):
        landmarks = hand_landmarks.landmark
        thumb_tip = landmarks[4]

        # For POV, track thumb movement in both Y (up/down) and Z (forward/back)
        current_thumb_y = thumb_tip.y
        current_thumb_z = thumb_tip.z

        # Initialize tracking for this hand if not exists
        if hand_id not in self.prev_thumb_y:
            self.prev_thumb_y[hand_id] = current_thumb_y
            self.is_cocked[hand_id] = False
            self.shoot_cooldown[hand_id] = 0
            return False

        # Decrease cooldown
        if self.shoot_cooldown[hand_id] > 0:
            self.shoot_cooldown[hand_id] -= 1

        # Calculate thumb movement (negative Y = moving up, positive Y = moving down)
        # For POV cocking: thumb pulls back (higher Y or similar) then snaps forward (lower Y)
        thumb_movement = current_thumb_y - self.prev_thumb_y[hand_id]

        shot_fired = False

        # Detect cocking motion (thumb moves back/up)
        # Relaxed threshold for POV - any upward or backward motion
        if thumb_movement < -self.cock_threshold and not self.is_cocked[hand_id]:
            self.is_cocked[hand_id] = True

        # Detect shooting motion (thumb snaps forward/down after being cocked)
        elif thumb_movement > self.cock_threshold and self.is_cocked[hand_id]:
            if self.shoot_cooldown[hand_id] == 0:
                shot_fired = True
                self.shoot_cooldown[hand_id] = self.cooldown_frames
            self.is_cocked[hand_id] = False

        # Update previous position
        self.prev_thumb_y[hand_id] = current_thumb_y

        return shot_fired

    def draw_vector(self, frame, start_x, start_y, dx, dy, length=300):
        # Calculate end point of vector
        end_x = int(start_x + dx * length)
        end_y = int(start_y + dy * length)

        # Draw the vector line
        cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 255), 3)

        # Draw arrow head
        arrow_length = 20
        arrow_angle = math.pi / 6

        angle = math.atan2(dy, dx)

        # Calculate arrow head points
        arrow_p1_x = int(end_x - arrow_length * math.cos(angle - arrow_angle))
        arrow_p1_y = int(end_y - arrow_length * math.sin(angle - arrow_angle))
        arrow_p2_x = int(end_x - arrow_length * math.cos(angle + arrow_angle))
        arrow_p2_y = int(end_y - arrow_length * math.sin(angle + arrow_angle))

        cv2.line(frame, (end_x, end_y), (arrow_p1_x, arrow_p1_y), (0, 255, 255), 3)
        cv2.line(frame, (end_x, end_y), (arrow_p2_x, arrow_p2_y), (0, 255, 255), 3)

        # Draw a glow effect at the tip
        cv2.circle(frame, (start_x, start_y), 8, (0, 255, 255), -1)
        cv2.circle(frame, (start_x, start_y), 12, (0, 200, 200), 2)

    def draw_shot_effect(self, frame, start_x, start_y, dx, dy):
        # Draw multiple shot lines with varying opacity for effect
        for i in range(5):
            length = 500 + i * 50
            end_x = int(start_x + dx * length)
            end_y = int(start_y + dy * length)
            thickness = max(1, 5 - i)
            cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 100 + i * 30, 255), thickness)

        # Draw muzzle flash
        for radius in [15, 25, 35]:
            alpha = 255 - (radius * 5)
            cv2.circle(frame, (start_x, start_y), radius, (0, 255, 255), 2)

    def process_frame(self, frame):
        # Don't flip for POV mode - Ray-Bans show natural perspective
        # frame = cv2.flip(frame, 1)  # Disabled for POV
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        finger_gun_detected = False
        shot_fired = False

        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
                # Get hand ID (left or right)
                hand_id = handedness.classification[0].label

                # Draw hand landmarks
                self.mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                )

                # Check for finger gun gesture
                if self.is_finger_gun(hand_landmarks):
                    finger_gun_detected = True

                    # Get finger tip position and direction
                    tip_x, tip_y, dx, dy = self.get_finger_direction(
                        hand_landmarks.landmark,
                        frame.shape
                    )

                    # Detect cocking motion
                    is_shot = self.detect_cock_motion(hand_landmarks, hand_id)

                    if is_shot:
                        shot_fired = True
                        # Draw shot effect
                        self.draw_shot_effect(frame, tip_x, tip_y, dx, dy)
                        cv2.putText(frame, "BANG!", (10, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                    else:
                        # Draw aiming vector
                        self.draw_vector(frame, tip_x, tip_y, dx, dy)

                        # Show cocked status with POV-friendly text
                        if hand_id in self.is_cocked and self.is_cocked[hand_id]:
                            cv2.putText(frame, "READY", (10, 60),
                                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                        else:
                            cv2.putText(frame, "AIM", (10, 60),
                                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        return frame, shot_fired

    def release(self):
        self.hands.close()

def main():
    # Initialize detector
    detector = FingerGunDetector()

    # Open webcam (Meta Ray-Bans typically appear as camera device)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open camera")
        print("Make sure your Meta Ray-Bans are connected and recognized as a camera device")
        return

    print("POV Finger Gun Detector Started!")
    print("Hold your hand in front of the camera in a finger gun gesture")
    print("Pull your thumb back to cock, release forward to shoot")
    print("Press 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break

        # Process frame
        processed_frame, detected = detector.process_frame(frame)

        # Display frame
        cv2.imshow('Finger Gun Detector', processed_frame)

        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    detector.release()
    print("Application closed")

if __name__ == "__main__":
    main()
