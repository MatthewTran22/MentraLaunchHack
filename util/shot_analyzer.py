import cv2
from ultralytics import YOLO


class ShotAnalyzer:
    def __init__(self):
        self.yolo = YOLO('yolov8n.pt')

    def boxes_overlap(self, box1, box2, threshold=0.3):
        """
        Check if two bounding boxes overlap significantly.

        Args:
            box1: (x1, y1, x2, y2) first bounding box
            box2: (x1, y1, x2, y2) second bounding box
            threshold: minimum IoU or overlap ratio to consider as overlapping

        Returns:
            bool: True if boxes overlap significantly
        """
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i <= x1_i or y2_i <= y1_i:
            return False  # No intersection

        intersection = (x2_i - x1_i) * (y2_i - y1_i)

        # Calculate area of smaller box (hand box)
        area_hand = (x2_1 - x1_1) * (y2_1 - y1_1)

        # Check if hand is mostly inside the person box
        if area_hand > 0 and intersection / area_hand > threshold:
            return True

        return False

    def is_crosshair_on_target(self, image_path, hand_bbox=None):
        """
        Analyze a shot image to check if the crosshair (center of image)
        is within any person's bounding box, excluding the FPV hand.

        Args:
            image_path: Path to the saved shot image
            hand_bbox: (x1, y1, x2, y2) bounding box of the FPV hand to exclude

        Returns:
            bool: True if crosshair is on a person, False otherwise
        """
        # Load the image
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"Error: Could not load image {image_path}")
            return False

        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2

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
                    return True

        return False


def analyze_shot(image_path, hand_bbox=None):
    """Convenience function to analyze a single shot"""
    analyzer = ShotAnalyzer()
    hit = analyzer.is_crosshair_on_target(image_path, hand_bbox)
    print(f"HIT: {hit}")
    return hit


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        analyze_shot(image_path)
    else:
        print("Usage: python shot_analyzer.py <image_path>")
