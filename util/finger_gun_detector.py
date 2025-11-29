import cv2
import mediapipe as mp
import numpy as np
import math
import os
import time
import threading
import socket
from datetime import datetime
from ultralytics import YOLO
from shot_analyzer import analyze_shot

try:
    import pygame
    pygame.mixer.init()
    SOUND_ENABLED = True
except ImportError:
    print("Warning: pygame not installed. Sound disabled.")
    SOUND_ENABLED = False

# High-vis color ranges in HSV
HIGHVIS_YELLOW_LOWER = np.array([20, 100, 100])
HIGHVIS_YELLOW_UPPER = np.array([45, 255, 255])

HIGHVIS_ORANGE_LOWER = np.array([5, 150, 150])
HIGHVIS_ORANGE_UPPER = np.array([20, 255, 255])

HIGHVIS_GREEN_LOWER = np.array([45, 100, 100])
HIGHVIS_GREEN_UPPER = np.array([75, 255, 255])

MIN_HIGHVIS_AREA = 500

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class FingerGunDetector:
    def __init__(self, player_id=1):
        self.player_id = player_id
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=4,  # Detect multiple to find the closest one
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
        self.last_shot_time = 0  # Time of last shot
        self.shot_cooldown = 1.0  # 1 second cooldown between shots

        # Team counts
        self.yellow_count = 0
        self.green_count = 0

        # Kill streak tracking
        self.kill_streak = 0

        # Load sounds
        self.sounds = {}
        if SOUND_ENABLED:
            self._load_sounds()

    def _load_sounds(self):
        """Load kill streak sound files"""
        sounds_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sounds')

        sound_files = {
            'pew': 'pew.mp3',
            'kill1': 'kill1.mp3',
            'kill2': 'kill2.mp3',
            'kill3': 'kill3.mp3',
            'kill4': 'kill4.mp3',
            'kill5': 'kill5.mp3',
            'ace': 'ace.mp3'
        }

        for name, filename in sound_files.items():
            filepath = os.path.join(sounds_dir, filename)
            if os.path.exists(filepath):
                try:
                    self.sounds[name] = pygame.mixer.Sound(filepath)
                    print(f"Loaded sound: {filename}")
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
            else:
                print(f"Sound file not found: {filepath}")

    def play_pew_sound(self):
        """Play pew sound when shooting"""
        if not SOUND_ENABLED or 'pew' not in self.sounds:
            return
        threading.Thread(target=self.sounds['pew'].play, daemon=True).start()

    def play_kill_sound(self):
        """Play appropriate kill sound based on streak"""
        if not SOUND_ENABLED or not self.sounds:
            return

        if self.kill_streak >= 5:
            sound_key = 'ace'
        else:
            sound_key = f'kill{self.kill_streak}'

        if sound_key in self.sounds:
            # Play sound in separate thread to avoid blocking
            threading.Thread(target=self.sounds[sound_key].play, daemon=True).start()
            print(f"Playing: {sound_key} (streak: {self.kill_streak})")

    def on_hit(self, is_valid_hit):
        """Handle hit result and update streak"""
        if is_valid_hit:
            self.kill_streak += 1
            self.play_kill_sound()
        else:
            # Reset streak on miss or friendly fire
            self.kill_streak = 0

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
        current_time = time.time()

        # Initialize tracking for this hand if not exists
        if hand_id not in self.prev_thumb_y:
            self.prev_thumb_y[hand_id] = current_thumb_y
            self.is_cocked[hand_id] = False
            return False

        # Check if still on cooldown
        time_since_last_shot = current_time - self.last_shot_time
        on_cooldown = time_since_last_shot < self.shot_cooldown

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
            if not on_cooldown:
                shot_fired = True
                self.last_shot_time = current_time
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

    def get_hand_size(self, hand_landmarks, frame_shape):
        """Get the size of the hand (area of bounding box) - larger = closer"""
        bbox = self.get_hand_bbox(hand_landmarks, frame_shape)
        x_min, y_min, x_max, y_max = bbox
        return (x_max - x_min) * (y_max - y_min)

    def get_closest_hand(self, hand_landmarks_list, frame_shape):
        """Return the closest hand (largest on screen)"""
        if not hand_landmarks_list:
            return None, -1

        max_size = 0
        closest_idx = 0

        for idx, hand_landmarks in enumerate(hand_landmarks_list):
            size = self.get_hand_size(hand_landmarks, frame_shape)
            if size > max_size:
                max_size = size
                closest_idx = idx

        return hand_landmarks_list[closest_idx], closest_idx

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

    def detect_color_masks(self, frame):
        """Detect regions with yellow and green colors separately."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask_yellow = cv2.inRange(hsv, HIGHVIS_YELLOW_LOWER, HIGHVIS_YELLOW_UPPER)
        mask_green = cv2.inRange(hsv, HIGHVIS_GREEN_LOWER, HIGHVIS_GREEN_UPPER)

        kernel = np.ones((5, 5), np.uint8)

        # Process yellow mask
        mask_yellow = cv2.morphologyEx(mask_yellow, cv2.MORPH_OPEN, kernel)
        mask_yellow = cv2.morphologyEx(mask_yellow, cv2.MORPH_CLOSE, kernel)
        mask_yellow = cv2.dilate(mask_yellow, kernel, iterations=2)

        # Process green mask
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_OPEN, kernel)
        mask_green = cv2.morphologyEx(mask_green, cv2.MORPH_CLOSE, kernel)
        mask_green = cv2.dilate(mask_green, kernel, iterations=2)

        return mask_yellow, mask_green

    def classify_person_team(self, frame, x1, y1, x2, y2, mask_yellow, mask_green):
        """Classify what color team a person is on: yellow, green, or None."""
        w, h = x2 - x1, y2 - y1

        # Focus on upper body / torso area (where vest would be)
        upper_y = y1 + int(h * 0.15)
        upper_h = int(h * 0.45)

        upper_y = max(0, upper_y)
        upper_x = max(0, x1)
        end_y = min(frame.shape[0], upper_y + upper_h)
        end_x = min(frame.shape[1], x2)

        roi_yellow = mask_yellow[upper_y:end_y, upper_x:end_x]
        roi_green = mask_green[upper_y:end_y, upper_x:end_x]

        if roi_yellow.size == 0:
            return None

        yellow_pixels = cv2.countNonZero(roi_yellow)
        green_pixels = cv2.countNonZero(roi_green)
        total_pixels = roi_yellow.size

        yellow_pct = (yellow_pixels / total_pixels) * 100
        green_pct = (green_pixels / total_pixels) * 100

        yellow_valid = yellow_pct > 3 and yellow_pixels > MIN_HIGHVIS_AREA
        green_valid = green_pct > 3 and green_pixels > MIN_HIGHVIS_AREA

        if yellow_valid and green_valid:
            return "yellow" if yellow_pixels > green_pixels else "green"
        elif yellow_valid:
            return "yellow"
        elif green_valid:
            return "green"
        else:
            return None

    def detect_and_draw_person(self, frame, hand_bboxes):
        """Detect person using YOLOv8n and draw bounding box only for yellow/green team members"""
        # Run YOLO inference (class 0 = person)
        results = self.yolo(frame, classes=[0], verbose=False)
        person_boxes = []

        # Get color masks for team classification
        mask_yellow, mask_green = self.detect_color_masks(frame)

        # Reset counts
        self.yellow_count = 0
        self.green_count = 0

        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = box.conf[0].cpu().numpy()
                person_box = (x1, y1, x2, y2)
                w, h = x2 - x1, y2 - y1

                # Skip if this person box overlaps with any detected hand
                is_hand = False
                for hand_bbox in hand_bboxes:
                    if self.boxes_overlap(hand_bbox, person_box):
                        is_hand = True
                        break

                if is_hand:
                    continue

                # Classify team
                team = self.classify_person_team(frame, x1, y1, x2, y2, mask_yellow, mask_green)

                # No color detected = green team
                if team is None:
                    team = "green"

                if team == "yellow":
                    color = (0, 255, 255)  # Yellow in BGR
                    label = "YELLOW"
                    self.yellow_count += 1
                else:  # green
                    color = (0, 255, 0)  # Green in BGR
                    label = "GREEN"
                    self.green_count += 1

                # Store bounding box with team info
                person_boxes.append((x1, y1, x2, y2, team))

                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Draw corner accents
                corner_len = min(20, w // 4, h // 4)
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, 4)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, 4)
                cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, 4)
                cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, 4)
                cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, 4)
                cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, 4)
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, 4)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, 4)

                # Draw label with confidence
                label_text = f"{label} {int(confidence * 100)}%"
                label_size, _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x1, y1 - 25), (x1 + label_size[0] + 10, y1), color, -1)
                cv2.putText(frame, label_text, (x1 + 5, y1 - 7),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

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

        # Get only the closest hand (largest on screen)
        closest_hand = None
        closest_idx = -1
        hand_bboxes = []

        if results.multi_hand_landmarks:
            closest_hand, closest_idx = self.get_closest_hand(
                results.multi_hand_landmarks, frame.shape
            )
            if closest_hand:
                hand_bbox = self.get_hand_bbox(closest_hand, frame.shape)
                hand_bboxes.append(hand_bbox)

        # Detect and draw bounding box around person (excluding the closest hand)
        self.detect_and_draw_person(frame, hand_bboxes)

        # Always draw crosshair in center
        self.draw_crosshair(frame)

        # Only process the closest hand
        if closest_hand is not None and results.multi_handedness:
            hand_landmarks = closest_hand
            handedness = results.multi_handedness[closest_idx]
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
                    # Play pew sound
                    self.play_pew_sound()
                    # Get hand bounding box to exclude from person detection
                    hand_bbox = self.get_hand_bbox(hand_landmarks, frame.shape)
                    # Save the shot image and analyze it
                    filepath, hand_bbox = self.save_shot(frame, hand_bbox)
                    is_valid_hit = analyze_shot(filepath, hand_bbox, self.player_id)
                    # Handle hit and play sound
                    self.on_hit(is_valid_hit)
                    # Draw shot effect
                    self.draw_shot_effect(frame, tip_x, tip_y, dx, dy)
                    cv2.putText(frame, "BANG!", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
                else:
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
        self._clear_shots_directory()

    def _clear_shots_directory(self):
        """Clear all images from the shots directory on shutdown"""
        if os.path.exists(self.shots_dir):
            for filename in os.listdir(self.shots_dir):
                filepath = os.path.join(self.shots_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                except Exception as e:
                    print(f"Error deleting {filepath}: {e}")
            print("Shots directory cleared.")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Finger Gun Game')
    parser.add_argument('--player', '-p', type=int, default=1, choices=[1, 2],
                        help='Player number (1 or 2)')
    args = parser.parse_args()

    player_id = args.player
    rtmp_port = 1935 if player_id == 1 else 1937

    print("=" * 50)
    print(f"FINGER GUN GAME - PLAYER {player_id}")
    print("=" * 50)
    print("\nHold your hand in a finger gun gesture")
    print("Pull your thumb back to cock, release forward to shoot")
    print("Teams: GREEN = High-Vis | BLUE = Regular")
    print("Press 'Q' to quit")
    print("=" * 50)

    # Initialize detector
    detector = FingerGunDetector(player_id=player_id)

    # Get local IP and set up RTMP
    local_ip = get_local_ip()
    rtmp_url = f"rtmp://{local_ip}:{rtmp_port}/live/stream"

    config_file = "mediamtx.yml" if player_id == 1 else "mediamtx_player2.yml"
    print(f"\n" + "=" * 50)
    print(f"RTMP SERVER - PLAYER {player_id}")
    print(f"=" * 50)
    print(f"Stream to: {rtmp_url}")
    print(f"=" * 50)
    print(f"\n*** Run MediaMTX first: mediamtx {config_file} ***")
    print("\nWaiting for RTMP stream...")
    print("(Configure your camera now - will keep trying until connected)")
    
    # Set FFMPEG options for low latency (same as ffplay flags)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay|framedrop;1|strict;experimental"
    
    # Keep trying to connect until stream is available
    cap = None
    while cap is None:
        # Use FFMPEG backend explicitly with low-latency options
        cap = cv2.VideoCapture(rtmp_url, cv2.CAP_FFMPEG)
        
        if cap.isOpened():
            # Set additional buffer properties
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                print(f"\n✓ Connected to RTMP stream!")
                break
            else:
                cap.release()
                cap = None
        
        print(".", end="", flush=True)
        time.sleep(2)
    
    print("\nProcessing frames...")

    consecutive_failures = 0
    max_failures = 30  # Reconnect after this many failed frames

    while True:
        ret, frame = cap.read()

        if not ret or frame is None:
            consecutive_failures += 1

            if consecutive_failures >= max_failures:
                print("\nStream disconnected. Attempting to reconnect...")
                cap.release()

                # Reconnect loop
                cap = None
                while cap is None:
                    cap = cv2.VideoCapture(rtmp_url, cv2.CAP_FFMPEG)

                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            print("✓ Reconnected!")
                            consecutive_failures = 0
                            break
                        else:
                            cap.release()
                            cap = None

                    print(".", end="", flush=True)
                    time.sleep(2)

                    # Check for quit during reconnect
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        cap = None
                        break

                if cap is None:
                    break

            time.sleep(0.01)
            continue

        # Reset failure counter on successful frame
        consecutive_failures = 0

        # Process frame
        processed_frame, shot_fired = detector.process_frame(frame)

        # Draw team count on screen
        h, w = processed_frame.shape[:2]
        cv2.putText(processed_frame, f"Yellow: {detector.yellow_count} | Green: {detector.green_count}",
                   (w - 300, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Draw kill streak
        if detector.kill_streak > 0:
            streak_text = f"Streak: {detector.kill_streak}" + (" ACE!" if detector.kill_streak >= 5 else "")
            cv2.putText(processed_frame, streak_text, (10, h - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Display frame
        cv2.imshow(f'Finger Gun Game - Player {player_id}', processed_frame)

        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    detector.release()
    print("\nGame ended. Thanks for playing!")


if __name__ == "__main__":
    main()
