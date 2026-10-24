from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from time import perf_counter

class WorkoutProcessorWorker(QObject):
    """
    Background inference worker.

    The worker supports two independent operations in one payload:
    - YOLO/ByteTrack, used only for placement and recovery.
    - MediaPipe Pose, used continuously for per-user fixed ROIs.

    Normal workout frames set `run_yolo=False` so pose inference no longer
    waits for YOLO. During placement/recovery, both operations may run in the
    same worker invocation.
    """

    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.yolo = None
        self.pose_extractors: dict[str, object] = {}

    def _ensure_yolo_loaded(self):
        if self.yolo is None:
            from services.workout_backends.yolo_detector import YOLODetector

            self.yolo = YOLODetector()

    def _ensure_pose_extractor(self, user_key: str):
        extractor = self.pose_extractors.get(user_key)
        if extractor is None:
            from services.workout_backends.pose_extractor import PoseExtractor

            extractor = PoseExtractor()
            self.pose_extractors[user_key] = extractor
        return extractor

    def _reset_pose_extractors(self, user_keys=None):
        keys = user_keys or list(self.pose_extractors.keys())
        for user_key in keys:
            extractor = self.pose_extractors.get(user_key)
            if extractor is not None:
                extractor.reset()

    @pyqtSlot(object)
    def process_image(self, payload):
        t0 = perf_counter()

        frame_id = None
        captured_at = None
        image = None
        run_yolo = False
        yolo_purpose = None
        recovery_users = []
        pose_jobs = {}

        try:
            if isinstance(payload, dict):
                image = payload.get("image")
                frame_id = payload.get("frame_id")
                captured_at = payload.get("captured_at")
                run_yolo = bool(payload.get("run_yolo", False))
                yolo_purpose = payload.get("yolo_purpose")
                recovery_users = list(payload.get("recovery_users") or [])
                pose_jobs = payload.get("pose_jobs") or {}
                reset_pose = bool(payload.get("reset_pose", False))
                reset_pose_users = payload.get("reset_pose_users")
            else:
                image = payload
                reset_pose = False
                reset_pose_users = None

            if reset_pose:
                self._reset_pose_extractors(reset_pose_users)

            if image is None:
                self.result_ready.emit(
                    {
                        "image": None,
                        "persons": [],
                        "pose_results": {},
                        "frame_id": frame_id,
                        "captured_at": captured_at,
                        "processing_ok": False,
                        "run_yolo": run_yolo,
                        "yolo_purpose": yolo_purpose,
                        "recovery_users": recovery_users,
                        "timing": {
                            "yolo_ms": 0.0,
                            "pose_ms": 0.0,
                            "worker_total_ms": 0.0,
                            "frame_age_ms": 0.0,
                        },
                    }
                )
                return

            persons = []
            yolo_ms = 0.0
            pose_ms = 0.0

            if run_yolo:
                yolo_t0 = perf_counter()
                self._ensure_yolo_loaded()
                persons = self.yolo.track(image)
                yolo_ms = (perf_counter() - yolo_t0) * 1000.0

            pose_results = {}
            if pose_jobs:
                pose_t0 = perf_counter()
                timestamp_ms = (
                    int(float(captured_at) * 1000.0)
                    if captured_at is not None
                    else None
                )

                for user_key, job in pose_jobs.items():
                    crop = job.get("crop") if isinstance(job, dict) else None
                    crop_bbox = job.get("crop_bbox") if isinstance(job, dict) else None

                    extractor = self._ensure_pose_extractor(user_key)
                    pose_result = extractor.process(
                        crop,
                        timestamp_ms=timestamp_ms,
                    )

                    pose_results[user_key] = {
                        "pose_result": pose_result,
                        "crop_bbox": crop_bbox,
                    }

                pose_ms = (perf_counter() - pose_t0) * 1000.0

            t1 = perf_counter()
            frame_age_ms = (
                (t1 - captured_at) * 1000.0
                if captured_at is not None
                else 0.0
            )

            self.result_ready.emit(
                {
                    "image": image,
                    "persons": persons or [],
                    "pose_results": pose_results,
                    "frame_id": frame_id,
                    "captured_at": captured_at,
                    "processing_ok": True,
                    "run_yolo": run_yolo,
                    "yolo_purpose": yolo_purpose,
                    "recovery_users": recovery_users,
                    "timing": {
                        "yolo_ms": yolo_ms,
                        "pose_ms": pose_ms,
                        "worker_total_ms": (t1 - t0) * 1000.0,
                        "frame_age_ms": frame_age_ms,
                    },
                }
            )

        except Exception as exc:
            self.error.emit(str(exc))
            self.result_ready.emit(
                {
                    "image": image,
                    "persons": [],
                    "pose_results": {},
                    "frame_id": frame_id,
                    "captured_at": captured_at,
                    "processing_ok": False,
                    "run_yolo": run_yolo,
                    "yolo_purpose": yolo_purpose,
                    "recovery_users": recovery_users,
                    "timing": {
                        "yolo_ms": 0.0,
                        "pose_ms": 0.0,
                        "worker_total_ms": (perf_counter() - t0) * 1000.0,
                        "frame_age_ms": (
                            (perf_counter() - captured_at) * 1000.0
                            if captured_at is not None
                            else 0.0
                        ),
                    },
                }
            )
