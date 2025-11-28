import cv2
from ultralytics import YOLO


class ShotAnalyzer:
    def __init__(self):
        self.yolo = YOLO('yolov8n.pt')

    def is_crosshair_on_target(self, image_path):
        """
        Analyze a shot image to check if the crosshair (center of image)
        is within any person's bounding box.

        Args:
            image_path: Path to the saved shot image

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

                # Check if crosshair is within bounding box
                if x1 <= center_x <= x2 and y1 <= center_y <= y2:
                    return True

        return False


def analyze_shot(image_path):
    """Convenience function to analyze a single shot"""
    analyzer = ShotAnalyzer()
    hit = analyzer.is_crosshair_on_target(image_path)
    print(f"HIT: {hit}")
    return hit


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        analyze_shot(image_path)
    else:
        print("Usage: python shot_analyzer.py <image_path>")
