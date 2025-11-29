import cv2
import numpy as np
import requests
from ultralytics import YOLO

# API endpoint for hit registration
HITS_API_URL = "https://gobbler-working-bluebird.ngrok-free.app/api/hits"

# Player config: player_id -> (username, target_team)
PLAYER_CONFIG = {
    1: ("Phil", "yellow"),
    2: ("Kevin", "green"),
}

# High-vis color ranges in HSV (same as finger_gun_detector)
HIGHVIS_YELLOW_LOWER = np.array([20, 100, 100])
HIGHVIS_YELLOW_UPPER = np.array([45, 255, 255])

HIGHVIS_ORANGE_LOWER = np.array([5, 150, 150])
HIGHVIS_ORANGE_UPPER = np.array([20, 255, 255])

HIGHVIS_GREEN_LOWER = np.array([45, 100, 100])
HIGHVIS_GREEN_UPPER = np.array([75, 255, 255])

MIN_HIGHVIS_AREA = 500

# User is on REGULAR team (not wearing high-vis)
USER_TEAM = "regular"


class ShotAnalyzer:
    def __init__(self, player_id=1):
        self.yolo = YOLO('yolov8n.pt')
        self.player_id = player_id
        self.username, self.target_team = PLAYER_CONFIG.get(player_id, ("unknown", "yellow"))

    def boxes_overlap(self, box1, box2, threshold=0.3):
        """Check if two bounding boxes overlap significantly."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i <= x1_i or y2_i <= y1_i:
            return False

        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area_hand = (x2_1 - x1_1) * (y2_1 - y1_1)

        if area_hand > 0 and intersection / area_hand > threshold:
            return True

        return False

    def detect_highvis_regions(self, frame):
        """Detect regions with high-visibility colors."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask_yellow = cv2.inRange(hsv, HIGHVIS_YELLOW_LOWER, HIGHVIS_YELLOW_UPPER)
        mask_orange = cv2.inRange(hsv, HIGHVIS_ORANGE_LOWER, HIGHVIS_ORANGE_UPPER)
        mask_green = cv2.inRange(hsv, HIGHVIS_GREEN_LOWER, HIGHVIS_GREEN_UPPER)

        combined_mask = cv2.bitwise_or(mask_yellow, mask_orange)
        combined_mask = cv2.bitwise_or(combined_mask, mask_green)

        kernel = np.ones((5, 5), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.dilate(combined_mask, kernel, iterations=2)

        return combined_mask

    def classify_person_team(self, frame, x1, y1, x2, y2, highvis_mask):
        """Classify if a person is wearing high-vis or not."""
        w, h = x2 - x1, y2 - y1

        upper_y = y1 + int(h * 0.15)
        upper_h = int(h * 0.45)

        upper_y = max(0, upper_y)
        upper_x = max(0, x1)
        end_y = min(frame.shape[0], upper_y + upper_h)
        end_x = min(frame.shape[1], x2)

        roi_mask = highvis_mask[upper_y:end_y, upper_x:end_x]

        if roi_mask.size == 0:
            return "regular"

        highvis_pixels = cv2.countNonZero(roi_mask)
        total_pixels = roi_mask.size
        percentage = (highvis_pixels / total_pixels) * 100

        is_highvis = percentage > 3 and highvis_pixels > MIN_HIGHVIS_AREA

        return "highvis" if is_highvis else "regular"

    def send_hit_to_api(self):
        """Send hit data to the API endpoint."""
        payload = {
            "hitter_username": self.username,
            "target_team": self.target_team
        }
        headers = {
            "ngrok-skip-browser-warning": "true",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(HITS_API_URL, json=payload, headers=headers, timeout=5)
            print(f"API Response: {response.status_code} - {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"API Error: {e}")
            return False

    def is_valid_hit(self, image_path, hand_bbox=None):
        """
        Analyze a shot image to check if the crosshair hit an opponent.

        User is on REGULAR team, so:
        - Hit HIGH-VIS player = True (valid hit, different team)
        - Hit REGULAR player = False (friendly fire, same team)
        - Miss = False

        Args:
            image_path: Path to the saved shot image
            hand_bbox: (x1, y1, x2, y2) bounding box of the FPV hand to exclude

        Returns:
            bool: True if hit an opponent, False if miss or friendly fire
        """
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error: Could not load image {image_path}")
            return False

        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2

        # Get high-vis mask for team classification
        highvis_mask = self.detect_highvis_regions(frame)

        # Detect persons in the image
        results = self.yolo(frame, classes=[0], verbose=False)

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                person_box = (x1, y1, x2, y2)

                # Skip if this person box overlaps with the FPV hand
                if hand_bbox is not None and self.boxes_overlap(hand_bbox, person_box):
                    continue

                # Check if crosshair is within bounding box
                if x1 <= center_x <= x2 and y1 <= center_y <= y2:
                    # Classify the person's team
                    target_team = self.classify_person_team(frame, x1, y1, x2, y2, highvis_mask)

                    # Valid hit only if target is on different team
                    if target_team != USER_TEAM:
                        print(f"HIT: True (hit {target_team.upper()} - opponent)")
                        # Send hit to API
                        self.send_hit_to_api()
                        return True
                    else:
                        print(f"HIT: False (friendly fire - same team: {target_team.upper()})")
                        return False

        print("HIT: False (missed)")
        return False


def analyze_shot(image_path, hand_bbox=None, player_id=1):
    """Convenience function to analyze a single shot"""
    analyzer = ShotAnalyzer(player_id=player_id)
    return analyzer.is_valid_hit(image_path, hand_bbox)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        analyze_shot(image_path)
    else:
        print("Usage: python shot_analyzer.py <image_path>")
