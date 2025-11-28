import cv2
import mediapipe as mp
import numpy as np
import math
import os
from datetime import datetime
from ultralytics import YOLO
from shot_analyzer import analyze_shot

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

        # Person detection using YOLOv8n
        self.yolo = YOLO('yolov8n.pt')

        # Directory to save shot images
        self.save_dir = os.path.dirname(os.path.abspath(__file__))
        self.shots_dir = os.path.join(self.save_dir, 'shots')
        os.makedirs(self.shots_dir, exist_ok=True)

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

        # For FPV: Use wrist, MCP (base of index), and fingertip to calculate 3D direction
        wrist = landmarks[0]
        mcp = landmarks[5]   # Base of index finger
        pip = landmarks[6]   # Middle joint of index
        tip = landmarks[8]   # Fingertip

        # Convert to pixel coordinates
        tip_x, tip_y = int(tip.x * w), int(tip.y * h)
        mcp_x, mcp_y = int(mcp.x * w), int(mcp.y * h)

        # Calculate 3D direction vector from MCP to tip
        dx_3d = tip.x - mcp.x
        dy_3d = tip.y - mcp.y
        dz_3d = tip.z - mcp.z  # Negative Z = pointing toward camera/forward

        # For FPV, when finger points forward (into screen), Z is dominant
        # We need to project the 3D vector onto the 2D screen

        # Check if pointing primarily forward (Z-dominant)
        xy_magnitude = math.sqrt(dx_3d**2 + dy_3d**2)
        z_magnitude = abs(dz_3d)

        if z_magnitude > xy_magnitude * 0.3 and dz_3d < 0:
            # Finger is pointing forward - use fingertip position relative to screen center
            # as the aiming direction (like a laser pointer)
            center_x, center_y = w // 2, h // 2

            # Vector from center of screen toward fingertip position
            dx = tip_x - center_x
            dy = tip_y - center_y
        else:
            # Traditional side-pointing - use finger bone direction
            dx = tip_x - mcp_x
            dy = tip_y - mcp_y

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

    def draw_trigger_skeleton(self, frame, hand_landmarks):
        """Draw only the index finger and thumb (trigger mechanism)"""
        landmarks = hand_landmarks.landmark
        h, w, _ = frame.shape

        # Index finger landmarks: 5 (MCP), 6 (PIP), 7 (DIP), 8 (tip)
        index_points = [5, 6, 7, 8]
        # Thumb landmarks: 1 (CMC), 2 (MCP), 3 (IP), 4 (tip)
        thumb_points = [1, 2, 3, 4]
        # Wrist for connection
        wrist = 0

        # Convert landmarks to pixel coordinates
        def get_point(idx):
            lm = landmarks[idx]
            return (int(lm.x * w), int(lm.y * h))

        # Draw index finger
        for i in range(len(index_points) - 1):
            pt1 = get_point(index_points[i])
            pt2 = get_point(index_points[i + 1])
            cv2.line(frame, pt1, pt2, (0, 255, 0), 3)
            cv2.circle(frame, pt1, 4, (0, 255, 0), -1)
        cv2.circle(frame, get_point(index_points[-1]), 4, (0, 255, 0), -1)

        # Draw thumb
        for i in range(len(thumb_points) - 1):
            pt1 = get_point(thumb_points[i])
            pt2 = get_point(thumb_points[i + 1])
            cv2.line(frame, pt1, pt2, (255, 0, 0), 3)
            cv2.circle(frame, pt1, 4, (255, 0, 0), -1)
        cv2.circle(frame, get_point(thumb_points[-1]), 4, (255, 0, 0), -1)

        # Connect wrist to index MCP and thumb CMC
        wrist_pt = get_point(wrist)
        cv2.line(frame, wrist_pt, get_point(5), (0, 255, 0), 2)
        cv2.line(frame, wrist_pt, get_point(1), (255, 0, 0), 2)
        cv2.circle(frame, wrist_pt, 5, (255, 255, 255), -1)

    def draw_crosshair(self, frame):
        """Draw a crosshair in the center of the screen"""
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        size = 20
        gap = 5

        # Draw crosshair lines with gap in center
        color = (0, 255, 255)  # Cyan
        thickness = 2

        # Top
        cv2.line(frame, (center_x, center_y - gap - size), (center_x, center_y - gap), color, thickness)
        # Bottom
        cv2.line(frame, (center_x, center_y + gap), (center_x, center_y + gap + size), color, thickness)
        # Left
        cv2.line(frame, (center_x - gap - size, center_y), (center_x - gap, center_y), color, thickness)
        # Right
        cv2.line(frame, (center_x + gap, center_y), (center_x + gap + size, center_y), color, thickness)

        # Center dot
        cv2.circle(frame, (center_x, center_y), 2, color, -1)

    def get_hand_bbox(self, hand_landmarks, frame_shape):
        """Get bounding box of the hand"""
        h, w, _ = frame_shape
        landmarks = hand_landmarks.landmark

        x_coords = [int(lm.x * w) for lm in landmarks]
        y_coords = [int(lm.y * h) for lm in landmarks]

        padding = 30
        x_min = max(0, min(x_coords) - padding)
        x_max = min(w, max(x_coords) + padding)
        y_min = max(0, min(y_coords) - padding)
        y_max = min(h, max(y_coords) + padding)

        return (x_min, y_min, x_max, y_max)

    def save_shot(self, frame, hand_bbox=None):
        """Save the current frame when a shot is fired"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"shot_{timestamp}.jpg"
        filepath = os.path.join(self.shots_dir, filename)
        cv2.imwrite(filepath, frame)
        print(f"Shot saved: {filepath}")
        return filepath, hand_bbox

    def boxes_overlap(self, box1, box2, threshold=0.3):
        """Check if two bounding boxes overlap significantly"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i <= x1_i or y2_i <= y1_i:
            return False

        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)

        if area1 > 0 and intersection / area1 > threshold:
            return True
        return False

    def detect_and_draw_person(self, frame, hand_bboxes):
        """Detect person using YOLOv8n and draw bounding box, excluding hands"""
        # Run YOLO inference (class 0 = person)
        results = self.yolo(frame, classes=[0], verbose=False)
        person_boxes = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = box.conf[0].cpu().numpy()
                person_box = (x1, y1, x2, y2)

                # Skip if this person box overlaps with any detected hand
                is_hand = False
                for hand_bbox in hand_bboxes:
                    if self.boxes_overlap(hand_bbox, person_box):
                        is_hand = True
                        break

                if is_hand:
                    continue

                # Store bounding box
                person_boxes.append(person_box)

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

                # Draw label with confidence
                label = f"PERSON {confidence:.2f}"
                cv2.putText(frame, label, (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        return person_boxes

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

        # Collect all hand bounding boxes first
        hand_bboxes = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                hand_bbox = self.get_hand_bbox(hand_landmarks, frame.shape)
                hand_bboxes.append(hand_bbox)

        # Detect and draw bounding box around person (excluding hands)
        self.detect_and_draw_person(frame, hand_bboxes)

        # Always draw crosshair in center
        self.draw_crosshair(frame)

        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
                # Get hand ID (left or right)
                hand_id = handedness.classification[0].label

                # Only draw index finger and thumb (the "trigger" parts)
                self.draw_trigger_skeleton(frame, hand_landmarks)

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
                        # Get hand bounding box to exclude from person detection
                        hand_bbox = self.get_hand_bbox(hand_landmarks, frame.shape)
                        # Save the shot image and analyze it
                        filepath, hand_bbox = self.save_shot(frame, hand_bbox)
                        analyze_shot(filepath, hand_bbox)
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
