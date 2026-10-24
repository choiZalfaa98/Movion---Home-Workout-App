from ultralytics import YOLO
import numpy as np
import torch

class YOLODetector:
    CONFIDENCE_THRESHOLD = 0.20

    def __init__(self, model_path="models/yolo26n.pt"):
        self.device = ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[YOLO] Running on: {self.device}")
        self.model = YOLO(model_path)

    def detect(self, frame: np.ndarray) -> list[dict]:
        results = self.model.predict(
            frame,
            classes=[0],
            verbose=False,
            conf=self.CONFIDENCE_THRESHOLD,
            device=self.device
        )

        persons = []

        for result in results:

            if result.boxes is None:
                continue

            for box in result.boxes:

                x1, y1, x2, y2 = (
                    box.xyxy[0]
                    .cpu()
                    .numpy()
                )

                conf = float(
                    box.conf[0]
                )

                persons.append({
                    "bbox": (
                        int(x1),
                        int(y1),
                        int(x2),
                        int(y2)
                    ),
                    "confidence": conf
                })

        return persons

    def track(
    self,
    frame: np.ndarray
    ):

        results = self.model.track(
        frame,
        classes=[0],
        persist=True,
        verbose=False,
        conf=self.CONFIDENCE_THRESHOLD,
        tracker="bytetrack.yaml",
        device=self.device
        )

        persons = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                if box.id is None:
                    continue

                x1,y1,x2,y2 = (
                box.xyxy[0]
                .cpu()
                .numpy()
                )

                track_id = int(
                box.id[0]
                .cpu()
                .numpy()
                )

                conf = float(
                box.conf[0]
                )

                persons.append({
                    "bbox":
                        (
                        int(x1),
                        int(y1),
                        int(x2),
                        int(y2)
                        ),

                    "confidence":
                        conf,

                    "track_id":
                        track_id
                })
        return persons
