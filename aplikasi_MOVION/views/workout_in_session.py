from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QFrame,
    QSizePolicy
)

from PyQt6.QtCore import (
    Qt,
    QSize,
    QObject,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    QTimer,
    QThread
)

from PyQt6.QtGui import QIcon

from PyQt6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QVideoSink,
    QMediaDevices
)

from views.components.camera_view import CameraView
from views.components.tracking_overlay import TrackingOverlay

from services.workout_backends.workout_controller import WorkoutController
from services.workout_backends.kinematic_rep_engine import (
    KinematicRepEngine,
    RepCycleResult,
)
from services.audio_feedback import AudioFeedback
from services.performance_session_logger import PerformanceSessionLogger

from pathlib import Path
from dataclasses import dataclass, field
from collections import deque, Counter
import numpy as np
from time import perf_counter

BASE_DIR = Path(__file__).resolve().parent.parent

class _LSTMPreloadSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class _LSTMPreloadTask(QRunnable):
    """
    Create AttnLSTMClassifier instances outside the GUI thread.

    This task only initializes the classifiers. Runtime LSTM
    inference remains in WorkoutSession.
    """

    def __init__(self, mode: str, user_keys: list[str]):
        super().__init__()
        self.setAutoDelete(False)
        self.mode = mode
        self.user_keys = list(user_keys)
        self.signals = _LSTMPreloadSignals()

    def run(self):
        started_at = perf_counter()

        try:
            from services.workout_backends.attn_lstm_classifier import (
                AttnLSTMClassifier,
            )

            classifiers = {}
            for user_key in self.user_keys:
                classifiers[user_key] = AttnLSTMClassifier()

            self.signals.finished.emit(
                {
                    "mode": self.mode,
                    "classifiers": classifiers,
                    "elapsed_seconds": perf_counter() - started_at,
                }
            )

        except Exception as exc:
            self.signals.failed.emit(
                f"{type(exc).__name__}: {exc}"
            )

@dataclass
class UserRuntimeState:
    user_key: str

    track_id: int | None = None
    registered: bool = False
    track_box_ready: bool = False
    finished: bool = False

    last_bbox: tuple | None = None
    tracking_roi: tuple | None = None
    display_bbox: tuple | None = None

    initial_center_x: float | None = None
    identity_side: str | None = None

    lost_detection_counter: int = 0
    recovery_pending: bool = False
    recovery_cooldown: int = 0

    pose_bbox: tuple | None = None

    guidebox_candidate_track_id: int | None = None
    guidebox_counter: int = 0

    current_class: str | None = None
    class_confidence: float = 0.0
    class_history: deque = field(default_factory=lambda: deque(maxlen=7))  # legacy, unused
    class_ttl: int = 0
    class_status: str = "UNKNOWN"  # MATCH / MISMATCH / UNKNOWN
    class_test_started_at: float | None = None
    first_stable_prediction_logged: bool = False

    pose_ready: bool = False
    pose_quality_counter: int = 0
    pose_lost_counter: int = 0

    cycle_phase: str = "IDLE"
    last_feedback: str = ""
    exercise_start_pose_ready: bool = False

    valid_reps: int = 0
    total_reps: int = 0

    exercise_context_ttl: int = 0

    # logs: Classification result per repetition
    classification_trial_no: int = 0
    rep_class_active: bool = False
    rep_class_started_at: float | None = None
    rep_stable_prediction: str | None = None
    rep_stable_confidence: float = 0.0
    rep_stable_elapsed_s: float | None = None

    def reset_for_exercise(self):
        self.track_id = None
        self.registered = False
        self.track_box_ready = False
        self.finished = False
        self.last_bbox = None
        self.tracking_roi = None
        self.display_bbox = None
        self.initial_center_x = None
        self.identity_side = None
        self.pose_bbox = None
        self.lost_detection_counter = 0
        self.recovery_pending = False
        self.recovery_cooldown = 0

        self.valid_reps = 0
        self.total_reps = 0
        self.exercise_context_ttl = 0
        self.cycle_phase = "IDLE"
        self.last_feedback = ""
        self.exercise_start_pose_ready = False

        self.reset_guidebox()
        self.reset_classification()
        self.reset_pose_gate()

        self.classification_trial_no = 0
        self.rep_class_active = False
        self.rep_class_started_at = None
        self.rep_stable_prediction = None
        self.rep_stable_confidence = 0.0
        self.rep_stable_elapsed_s = None

    def reset_guidebox(self):
        self.guidebox_candidate_track_id = None
        self.guidebox_counter = 0

    def reset_classification(self):
        self.current_class = None
        self.class_confidence = 0.0
        self.class_history.clear()
        self.class_ttl = 0
        self.class_status = "UNKNOWN"
        self.class_test_started_at = None
        self.first_stable_prediction_logged = False

    def reset_pose_gate(self):
        self.pose_ready = False
        self.pose_quality_counter = 0
        self.pose_lost_counter = 0


class WorkoutSession(QWidget):
    """
    Main workout session page.

    Final pipeline:
    YOLO / ByteTrack
        -> locked user identity from guidebox
        -> MediaPipe PoseExtractor
        -> Attention LSTM movement context classifier
        -> KinematicRepEngine primary phase/cycle detection
        -> valid repetition counter
    """

    back_or_pause = pyqtSignal()
    workout_done = pyqtSignal()
    next_workout_guide = pyqtSignal(object)
    
    process_frame_requested = pyqtSignal(object)

    backend_ready = pyqtSignal(object)
    backend_failed = pyqtSignal(str)

    GUIDEBOX_STABLE_FRAMES = 5

    # AttnLSTMClassifier already performs majority voting. WorkoutSession only
    # holds its latest stable context briefly between scheduled inferences.
    CLASS_GATE_TTL_FRAMES = 15

    SHOW_TOTAL_REPS_IN_UI = True

    SINGLE_PROCESS_EVERY_N_RAW_FRAMES = 2
    SINGLE_POSE_EVERY_N_PROCESSED_FRAMES = 1

    MULTI_PROCESS_EVERY_N_RAW_FRAMES = 2
    MULTI_POSE_EVERY_N_PROCESSED_FRAMES = 1

    SINGLE_SKELETON_EVERY_N_PROCESSED_FRAMES = 1
    MULTI_SKELETON_EVERY_N_PROCESSED_FRAMES = 1

    # Keep False for demo; set True only when debugging.
    DEBUG_VERBOSE = False
    # Turn this on to find lag causes.
    PERF_DEBUG = False
    PERF_LOG_EVERY_N_PROCESSED_FRAMES = 10
    # Toggle them one by one for bottleneck isolation
    PERF_DISABLE_POSITION_PHASE = False
    PERF_DISABLE_TRACKING_PHASE = False
    PERF_DISABLE_POSE = False
    PERF_DISABLE_SKELETON = False
    PERF_DISABLE_LSTM = False
    PERF_DISABLE_REP_ENGINE = False

    POSE_VISIBILITY_THRESHOLD = 0.30
    POSE_IN_FRAME_MARGIN = 0.12

    POSE_READY_STABLE_FRAMES = 3

    POSE_LOST_FRAMES = 14

    POSE_RECOVERY_TRIGGER_FRAMES = 6
    YOLO_RECOVERY_COOLDOWN_FRAMES = 6

    MULTI_ROI_OVERLAP_RATIO = 0.10
    IDENTITY_BOUNDARY_TOLERANCE_RATIO = 0.12
    POSE_DISPLAY_VISIBILITY_THRESHOLD = 0.20

    POSE_REQUIRE_ALL_LANDMARKS = False

    POSE_QUALITY_MIN_RATIO = 0.60

    ENABLE_STRONG_GEOMETRY_FALLBACK = False # fallback active (True) sebagai as tolerance in app, or make it to False LSTM is required to confirm every reps
    
    # Performance test logger
    PERF_TEST_ENABLED = False
    CLASSIFICATION_TEST_LOG_ENABLED = False
    PERF_WARMUP_SECONDS = 45

    def __init__(self):
        super().__init__()

        self._init_session_state()
        self._init_camera()
        self._init_tracking()

        self.build_ui()

        self.duration_ui_timer = QTimer(self)
        self.duration_ui_timer.setInterval(1000)
        self.duration_ui_timer.timeout.connect(self._update_duration_display)

    def _init_session_state(self):
        self.session = None
        self.current_workout = None
        self.tracking_mode = None
        self._exercise_transitioning = False

    def _init_camera(self):
        self.camera = None
        self.capture = QMediaCaptureSession()
        self.video_sink = QVideoSink()

        self._camera_started = False
        self._active_camera_index = None
        self.current_cam_resolution = None

    def _init_tracking(self):
        self.workout_controller = WorkoutController()

        self.pose_extractor: dict[str, object] = {}  # legacy; intentionally unused
        self.lstm: dict[str, object] = {}

        self._backend_ready_modes: set[str] = set()
        self._backend_loading_modes: set[str] = set()
        self._lstm_preload_tasks: dict[str, _LSTMPreloadTask] = {}

        self.rep_engine = KinematicRepEngine(cooldown_frames=8)

        self.user_states = {
            "user1": UserRuntimeState("user1"),
            "user2": UserRuntimeState("user2"),
        }

        self.yolo_active = False

        self._last_frame_shape = (1080, 1920, 3)
        self._tracking_started = False

        self._last_crop_size = {
            "user1": (1, 1),
            "user2": (1, 1),
        }

        self._frame_counter = 0

        self._raw_frame_counter = 0
        self._inference_frame_id = 0

        #DEBUGGING - performance profiling counter.
        self._perf_processed_counter = 0

        self._processing_frame = False
        self._busy_skip_counter = 0

        self.processor_thread = None
        self.processor_worker = None
        self._processor_busy = False
        self._pose_reset_pending = True
        self._identity_boundary_x = None

        self.audio_feedback = AudioFeedback(
            base_dir=BASE_DIR,
            volume=0.65,
            parent=self,
        )

        self.performance_logger = PerformanceSessionLogger(
            output_dir=BASE_DIR / "results" / "performance",
            parent=self,
        )

        self._perf_warmup_scheduled = False

    @staticmethod
    def _normalize_backend_mode(mode) -> str:
        return "multi" if mode == "multi" else "single"

    @classmethod
    def _user_keys_for_backend_mode(cls, mode) -> list[str]:
        normalized = cls._normalize_backend_mode(mode)
        return ["user1", "user2"] if normalized == "multi" else ["user1"]

    def ensure_processor_worker_started(self):
        if self.processor_thread is not None and self.processor_worker is not None:
            return

        from services.workout_backends.workout_processor_worker import (
            WorkoutProcessorWorker,
        )

        self.processor_thread = QThread(self)
        self.processor_worker = WorkoutProcessorWorker()
        self.processor_worker.moveToThread(self.processor_thread)

        self.process_frame_requested.connect(
            self.processor_worker.process_image
        )
        self.processor_worker.result_ready.connect(
            self._on_processor_result
        )
        self.processor_worker.error.connect(
            lambda msg: print(f"[PROCESSOR_WORKER_ERROR] {msg}")
        )

        self.processor_thread.start()
        #print("[PROCESSOR_WORKER] started")

    def stop_processor_worker(self):
        if self.processor_thread is None:
            return

        try:
            self.processor_thread.quit()
            self.processor_thread.wait(1500)
        except Exception as exc:
            print("[PROCESSOR_WORKER_STOP_WARN]", exc)

        self.processor_worker = None
        self.processor_thread = None
        self._processor_busy = False

        #print("[PROCESSOR_WORKER] stopped")

    def prewarm_backends(self, mode):
        """
        Preload only the LSTM classifier constructors outside the GUI thread.

        YOLO and MediaPipe are intentionally not preloaded here. They already
        initialize inside WorkoutProcessorWorker's QThread, so they do not
        cause the 6-7 second GUI-thread freeze.
        """
        normalized_mode = self._normalize_backend_mode(mode)
        required_keys = self._user_keys_for_backend_mode(normalized_mode)
        missing_keys = [key for key in required_keys if key not in self.lstm]

        if not missing_keys:
            self._backend_ready_modes.add(normalized_mode)
            if normalized_mode == "multi":
                self._backend_ready_modes.add("single")

            QTimer.singleShot(
                0,
                lambda m=normalized_mode: self.backend_ready.emit(
                    {"mode": m, "already_loaded": True}
                ),
            )
            return

        if normalized_mode in self._backend_loading_modes:
            return

        self._backend_loading_modes.add(normalized_mode)

        task = _LSTMPreloadTask(
            mode=normalized_mode,
            user_keys=missing_keys,
        )
        task.signals.finished.connect(self._on_lstm_preload_finished)
        task.signals.failed.connect(
            lambda message, m=normalized_mode: self._on_lstm_preload_failed(m, message)
        )

        self._lstm_preload_tasks[normalized_mode] = task

        """print(
            "[LSTM_PRELOAD_REQUESTED]",
            f"mode={normalized_mode}",
            f"users={missing_keys}",
        )"""
        QThreadPool.globalInstance().start(task)

    def _on_lstm_preload_finished(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        mode = self._normalize_backend_mode(payload.get("mode"))
        classifiers = payload.get("classifiers") or {}

        for user_key, classifier in classifiers.items():
            self.lstm[user_key] = classifier

        self._backend_loading_modes.discard(mode)
        self._lstm_preload_tasks.pop(mode, None)

        required_keys = self._user_keys_for_backend_mode(mode)
        if all(key in self.lstm for key in required_keys):
            self._backend_ready_modes.add(mode)
            if mode == "multi":
                self._backend_ready_modes.add("single")

        """print(
            "[LSTM_PRELOAD_FINISHED]",
            f"mode={mode}",
            f"total={float(payload.get('elapsed_seconds', 0.0)):.3f}s",
        )"""
        self.backend_ready.emit(payload)

    def _on_lstm_preload_failed(self, mode, message):
        normalized_mode = self._normalize_backend_mode(mode)
        self._backend_loading_modes.discard(normalized_mode)
        self._lstm_preload_tasks.pop(normalized_mode, None)

        #print("[LSTM_PRELOAD_FAILED]", message)
        self.backend_failed.emit(message)

    def backends_ready_for(self, mode) -> bool:
        normalized_mode = self._normalize_backend_mode(mode)
        required_keys = self._user_keys_for_backend_mode(normalized_mode)
        return all(key in self.lstm for key in required_keys)

    def ensure_backends_loaded(self) -> bool:
        """
        Start the normal processor worker and guard against entering the session
        before the background LSTM constructor preload has completed.
        """
        self.ensure_processor_worker_started()

        if self.backends_ready_for(self.tracking_mode):
            return True

        self.prewarm_backends(self.tracking_mode)
        return False

    def _reset_lstm_classifiers(self, user_keys=None):
        keys = user_keys or self._active_user_keys()
        for user_key in keys:
            classifier = self.lstm.get(user_key)
            if classifier is not None:
                classifier.reset()

    def _raw_frame_stride(self) -> int:
        if self.tracking_mode == "multi":
            return self.MULTI_PROCESS_EVERY_N_RAW_FRAMES
        return self.SINGLE_PROCESS_EVERY_N_RAW_FRAMES

    def _pose_frame_stride(self) -> int:
        if self.tracking_mode == "multi":
            return self.MULTI_POSE_EVERY_N_PROCESSED_FRAMES
        return self.SINGLE_POSE_EVERY_N_PROCESSED_FRAMES

    def _skeleton_frame_stride(self) -> int:
        if self.tracking_mode == "multi":
            return self.MULTI_SKELETON_EVERY_N_PROCESSED_FRAMES
        return self.SINGLE_SKELETON_EVERY_N_PROCESSED_FRAMES

    def build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 6, 4, 6)

        pause = QToolButton()
        pause.setText("Back/Pause")
        pause.setProperty("role", "backPauseButton")
        pause.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "pause.svg")))
        pause.setIconSize(QSize(18, 18))
        pause.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        pause.clicked.connect(self.on_pause)

        title = QLabel("Workout Session")
        title.setProperty("role", "pageTitle")
        title.setContentsMargins(0, 0, 90, 0)

        header_layout.addWidget(pause, alignment=Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch()
        header_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        header_layout.addStretch()

        info = QFrame()
        info.setProperty("role", "workoutSessionFrame")

        info_layout = QHBoxLayout(info)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.setContentsMargins(6, 4, 6, 4)

        self.exercise_counter = QLabel()
        self.exercise_label = QLabel()
        self.duration = QLabel()

        for label in (self.exercise_counter, self.duration):
            label.setProperty("role", "workoutSessionText")

        self.exercise_label.setObjectName("workoutSessionTitle")

        info_layout.addWidget(self.exercise_counter)
        info_layout.addStretch()
        info_layout.addWidget(self.exercise_label)
        info_layout.addStretch()
        info_layout.addWidget(self.duration)

        camera_frame = QFrame()
        camera_frame.setObjectName("workoutCam")
        camera_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        camera_layout = QVBoxLayout(camera_frame)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(0)

        self.camera_view = CameraView()
        self.camera_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        camera_layout.addWidget(self.camera_view)

        self.overlay = TrackingOverlay(self.camera_view.scene)
        self.overlay.init_skeleton_items()

        bottom = QFrame()
        bottom.setProperty("role", "workoutSessionFrame")

        self.bottom_layout = QHBoxLayout(bottom)
        self.bottom_layout.setContentsMargins(6, 4, 6, 4)
        self.bottom_layout.setSpacing(0)

        self.user1_label = QLabel()
        self.user1_label.setProperty("role", "workoutSessionText")
        self.user1_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.user2_label = QLabel()
        self.user2_label.setProperty("role", "workoutSessionText")
        self.user2_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Slot user 1
        self.user1_slot = QWidget()
        self.user1_slot_layout = QHBoxLayout(self.user1_slot)
        self.user1_slot_layout.setContentsMargins(0, 0, 0, 0)
        self.user1_slot_layout.setSpacing(0)
        self.user1_slot_layout.addStretch()
        self.user1_slot_layout.addWidget(self.user1_label)
        self.user1_slot_layout.addStretch()

        # Slot user 2
        self.user2_slot = QWidget()
        self.user2_slot_layout = QHBoxLayout(self.user2_slot)
        self.user2_slot_layout.setContentsMargins(0, 0, 0, 0)
        self.user2_slot_layout.setSpacing(0)
        self.user2_slot_layout.addStretch()
        self.user2_slot_layout.addWidget(self.user2_label)
        self.user2_slot_layout.addStretch()

        self.bottom_layout.addWidget(self.user1_slot, 1)
        self.bottom_layout.addWidget(self.user2_slot, 1)

        self.user1_slot.show()
        self.user2_slot.hide()

        root.addWidget(header, 0)
        root.addWidget(info, 0)
        root.addWidget(camera_frame, 1)
        root.addWidget(bottom, 0)

        self.setLayout(root)

    def on_pause(self):
        self._save_runtime_reps_to_session()
        self._stop_duration_ui_timer()
        self.stop_processing()
        self.overlay.hide_track_boxes()
        self.back_or_pause.emit()

    def _update_duration_display(self):
        if self.session is None:
            return

        if hasattr(self.session, "get_duration_formatted"):
            duration_text = self.session.get_duration_formatted()
        else:
            duration_text = "00:00:00"

        self.duration.setText(duration_text)

    def _start_duration_ui_timer(self):
        self._update_duration_display()

        if hasattr(self, "duration_ui_timer") and not self.duration_ui_timer.isActive():
            self.duration_ui_timer.start()

    def _stop_duration_ui_timer(self):
        if hasattr(self, "duration_ui_timer") and self.duration_ui_timer.isActive():
            self.duration_ui_timer.stop()

    def ensure_camera_started(self, camera_index=0):
        """
        Lazy start camera.
        Called from AppWindow when WorkoutGuide opened,
        and fallback from set_session/resume.
        """

        try:
            camera_index = int(camera_index or 0)
        except Exception:
            camera_index = 0

        if (
            self._camera_started
            and self.camera is not None
            and self._active_camera_index == camera_index
        ):
            #print("[CAMERA] Already started:", camera_index)
            return

        if self.camera is not None:
            self.stop_camera()

        self.setup_camera(camera_index)

    def setup_camera(self, camera_index=0):
        try:
            camera_index = int(camera_index or 0)
        except Exception:
            camera_index = 0

        devices = QMediaDevices.videoInputs()

        if not devices:
            #print("[ERROR] Tidak ada kamera ditemukan")
            self._camera_started = False
            self._active_camera_index = None
            return

        idx = camera_index if camera_index < len(devices) else 0
        device = devices[idx]

        self.camera = QCamera(device)

        """fmt = self.camera.cameraFormat()
        print(
            "[CAMERA FORMAT]",
            fmt.resolution().width(),
            "x",
            fmt.resolution().height(),
            "FPS: ",
            fmt.maxFrameRate()
        )"""

        self.capture.setCamera(self.camera)
        self.capture.setVideoOutput(self.video_sink)

        try:
            self.video_sink.videoFrameChanged.disconnect(self.on_frame)
        except Exception:
            pass

        self.video_sink.videoFrameChanged.connect(self.on_frame)

        self.camera.start()

        self._camera_started = True
        self._active_camera_index = idx

        #print(f"[CAMERA] Started: {device.description()}")
    
    def _on_processor_result(self, payload):
        self._processor_busy = False

        if not self.yolo_active or not isinstance(payload, dict):
            return

        image = payload.get("image")
        persons = payload.get("persons") or []
        pose_results = payload.get("pose_results") or {}
        
        timing = payload.get("timing") or {}
        captured_at = payload.get("captured_at")
        processing_ok = bool(payload.get("processing_ok", True))
        frame_id = payload.get("frame_id")
        run_yolo = bool(payload.get("run_yolo", False))
        recovery_users = payload.get("recovery_users") or []

        if image is None:
            return

        t0 = perf_counter()
        t_position = t0
        t_tracking = t0

        try:
            if run_yolo and not self.PERF_DISABLE_POSITION_PHASE:
                self.process_position_phase(persons, image)
                self._ensure_tracking_rois(image)

            t_position = perf_counter()

            if run_yolo and recovery_users:
                self._apply_yolo_recovery(
                    persons=persons,
                    frame=image,
                    recovery_users=recovery_users,
                )

            if pose_results and not self.PERF_DISABLE_TRACKING_PHASE:
                self.process_pose_results(pose_results, image)

            t_tracking = perf_counter()

        except Exception as exc:
            print("[PROCESSOR_RESULT_ERROR]", exc)

        finally:
            # End-to-end latency is recorded only after LSTM, rule-based
            # analysis, repetition logic, and UI-side result processing finish.
            end_to_end_ms = None

            if captured_at is not None:
                try:
                    end_to_end_ms = (
                        perf_counter() - float(captured_at)
                    ) * 1000.0
                except (TypeError, ValueError):
                    end_to_end_ms = None

            # Backward-compatible fallback when the worker does not echo
            # captured_at. frame_age_ms is capture-to-worker-completion age;
            # add the GUI-side processing performed above.
            if end_to_end_ms is None:
                try:
                    worker_age_ms = float(timing.get("frame_age_ms"))
                    gui_processing_ms = (perf_counter() - t0) * 1000.0
                    end_to_end_ms = worker_age_ms + gui_processing_ms
                except (TypeError, ValueError):
                    end_to_end_ms = None

            if (
                self.performance_logger.running
                and processing_ok
                and end_to_end_ms is not None
            ):
                self.performance_logger.record_processed_frame(
                    end_to_end_ms
                )

            if self.PERF_DEBUG:
                self._perf_processed_counter += 1
                if (
                    self._perf_processed_counter
                    % self.PERF_LOG_EVERY_N_PROCESSED_FRAMES
                    == 0
                ):
                    position_ms = (t_position - t0) * 1000.0
                    tracking_ms = (t_tracking - t_position) * 1000.0
                    """print(
                        "[PERF_FRAME_WORKER]",
                        f"frame_id={frame_id}",
                        f"mode={self.tracking_mode}",
                        f"persons={len(persons)}",
                        f"poses={len(pose_results)}",
                        f"age={float(timing.get('frame_age_ms', 0.0)):.1f}ms",
                        f"yolo={float(timing.get('yolo_ms', 0.0)):.1f}ms",
                        f"pose={float(timing.get('pose_ms', 0.0)):.1f}ms",
                        f"position={position_ms:.1f}ms",
                        f"tracking={tracking_ms:.1f}ms",
                        f"worker_total={float(timing.get('worker_total_ms', 0.0)):.1f}ms",
                        f"busy_skip={self._busy_skip_counter}",
                    )"""

    def on_frame(self, frame):
        frame_received_at = perf_counter()

        frame_width = int(frame.width()) if frame.isValid() else 0
        frame_height = int(frame.height()) if frame.isValid() else 0

        if frame_width > 0 and frame_height > 0:
            self.current_cam_resolution = (
                f"{frame_width}x{frame_height}"
            )

        if self.performance_logger.running:
            self.performance_logger.record_input_frame(
                width=frame_width,
                height=frame_height,
            )

        display_sink = self.camera_view.video_item.videoSink()
        if display_sink:
            display_sink.setVideoFrame(frame)

        if not self.yolo_active or self.processor_worker is None:
            return

        self._raw_frame_counter += 1
        if self._raw_frame_counter % self._raw_frame_stride() != 0:
            return

        if self._processor_busy:
            self._busy_skip_counter += 1
            return

        image = self.frame_to_array(frame)
        if image is None:
            return

        self._ensure_tracking_rois(image)

        placement_needed = self._needs_position_check()
        recovery_users = self._recovery_users_due()
        run_yolo = placement_needed or bool(recovery_users)

        pose_jobs = {}
        if self._tracking_started and not self.PERF_DISABLE_POSE:
            pose_jobs = self._build_pose_jobs(image)

        if not run_yolo and not pose_jobs:
            return

        self._processor_busy = True
        self._inference_frame_id += 1

        reset_pose = bool(self._pose_reset_pending and pose_jobs)
        if reset_pose:
            self._pose_reset_pending = False

        if placement_needed and recovery_users:
            yolo_purpose = "placement_and_recovery"
        elif placement_needed:
            yolo_purpose = "placement"
        elif recovery_users:
            yolo_purpose = "recovery"
        else:
            yolo_purpose = None

        self.process_frame_requested.emit(
            {
                "image": image,
                "frame_id": self._inference_frame_id,
                "captured_at": frame_received_at,
                "run_yolo": run_yolo,
                "yolo_purpose": yolo_purpose,
                "recovery_users": recovery_users,
                "pose_jobs": pose_jobs,
                "reset_pose": reset_pose,
                "reset_pose_users": self._active_user_keys(),
            }
        )

    def frame_to_array(self, frame):
        if not frame.isValid():
            return None

        image = frame.toImage()

        if image.isNull():
            return None
        
        """print(
            "[CAMERA FRAME]",
            image.width(),
            "x",
            image.height()
        )"""

        image = image.convertToFormat(image.Format.Format_RGB888)

        ptr = image.bits()
        ptr.setsize(image.sizeInBytes())

        arr = np.array(ptr).reshape(
            image.height(),
            image.width(),
            3,
        )

        return arr.copy()

    def change_camera(self, camera_index):
        self.stop_camera()
        self.setup_camera(camera_index)
    
    def stop_camera(self):
        self.stop_processing()
        self.stop_processor_worker()

        try:
            self.video_sink.videoFrameChanged.disconnect(self.on_frame)
        except Exception:
            pass

        if self.camera is not None:
            try:
                self.camera.stop()
                #print("[CAMERA] Stopped")
            except Exception as e:
                print("[CAMERA_STOP_ERROR]", e)

        try:
            self.capture.setCamera(None)
        except Exception:
            pass

        self.camera = None
        self._camera_started = False
        self._active_camera_index = None
        self.current_cam_resolution = None

    def showEvent(self, event):
        super().showEvent(event)
        self._defer_overlay_relayout()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_overlay_layout()

    def refresh_overlay_layout(self):
        if not hasattr(self, "camera_view"):
            return
        
        if not hasattr(self, "overlay"):
            return

        w = self.camera_view.viewport().width()
        h = self.camera_view.viewport().height()

        if w <= 10 or h <= 10:
            return
            

        self.overlay.relayout(w, h)

    def _defer_overlay_relayout(self):
        QTimer.singleShot(0, self.refresh_overlay_layout)
        QTimer.singleShot(50, self.refresh_overlay_layout)
        QTimer.singleShot(150, self.refresh_overlay_layout)
        QTimer.singleShot(300, self.refresh_overlay_layout)

    def set_session(self, session) -> bool:
        #print("[SESSION_SET] start")

        self.session = session
        self.current_workout = session.get_current_workout()
        self.tracking_mode = session.mode
        self._exercise_transitioning = False

        if not self.ensure_backends_loaded():
            """print(
                "[SESSION_SET_DEFERRED]",
                f"backend not ready for mode={self.tracking_mode}",
            )"""
            return False

        camera_index = getattr(session, "camera", 0) or 0
        self.ensure_camera_started(camera_index)

        if session.current_index == 0:
            self.workout_controller.reset_full()
        else:
            self.workout_controller.reset_for_next_exercise()

        self.reset_runtime_for_exercise()

        self._reset_lstm_classifiers()
        self._pose_reset_pending = True

        self.load_session()
        if getattr(self.session, "current_index", 0) == 0:
            self._schedule_performance_test()

        self._start_duration_ui_timer()
        return True

    def hard_reset_for_new_workout(self):
        """
        Called by AppWindow before starting each WorkoutSession from WorkoutGuide.
        It guarantees the next workout starts from a clean guidebox/registration state.
        Navigation and current_index changes remain AppWindow's responsibility.
        """
        self._exercise_transitioning = False
        self._stop_duration_ui_timer()

        try:
            self.stop_processing()
        except Exception as e:
            print("[HARD_RESET_STOP_WARN]", e)

        try:
            self.workout_controller.reset_full()
        except Exception as e:
            print("[HARD_RESET_CONTROLLER_WARN]", e)

        try:
            self.reset_runtime_for_exercise()
        except Exception as e:
            print("[HARD_RESET_RUNTIME_WARN]", e)

        try:
            self._reset_lstm_classifiers()
            self._pose_reset_pending = True
        except Exception as e:
            print("[HARD_RESET_BACKEND_WARN]", e)

        try:
            self.overlay.reset_colors()
            self.overlay.show_all(self.tracking_mode or "single")
            self.overlay.hide_track_boxes()
            self.overlay.hide_skeleton("user1")
            self.overlay.hide_skeleton("user2")
            self._defer_overlay_relayout()
        except Exception as e:
            print("[HARD_RESET_OVERLAY_WARN]", e)

    def resume(self, session):
        self.session = session
        self.current_workout = session.get_current_workout()
        self.tracking_mode = session.mode

        if not self.ensure_backends_loaded():
            """print(
                "[RESUME_DEFERRED]",
                f"backend not ready for mode={self.tracking_mode}",
            )"""
            return False

        camera_index = getattr(session, "camera", 0) or 0
        self.ensure_camera_started(camera_index)
        self.workout_controller.reset_for_resume()
        self.reset_runtime_for_resume()
        self._reset_lstm_classifiers()
        self._pose_reset_pending = True
        self._restore_runtime_reps_from_session()
        self.load_session()
        self._restore_runtime_reps_from_session()
        self._update_rep_labels()
        self._hide_finished_user_position_overlays()
        self._start_duration_ui_timer()
        return True

    def load_session(self):
        if self.session is not None:
            self.current_workout = self.session.get_current_workout()
            self.tracking_mode = self.session.mode

        if not self.current_workout:
            return

        workout = self.current_workout
        current_label = self._current_exercise_label()

        total_workouts = len(getattr(self.session, "workouts", []) or [])
        self.exercise_counter.setText(
            f"Exercise {self.session.current_index + 1} of {total_workouts}"
        )

        """print(
            "[CURRENT_WORKOUT]",
            "index=", self.session.current_index,
            "name=", workout.get("name"),
            "label=", current_label,
            "target=", workout.get("reps_target"),
        )"""

        self.exercise_label.setText(workout["name"])
        self._update_duration_display()
        self.setup_overlay()
        self.setup_labels()
        self.rep_engine_reset_current_exercise(current_label)
        self.start_position_check()

    def start_position_check(self):
        """
        Start/restart guidebox registration for the active exercise.

        When the previous exercise finishes and the app returns to WorkoutGuide,
        the next WorkoutSession must not inherit: registered=True, old track_id,
        finished=True, hidden guideboxes, or old WorkoutController mappings.
        """
        if self.performance_logger.running:
            self.performance_logger.resume()

        self.yolo_active = True
        self._tracking_started = False
        self._raw_frame_counter = 0
        self._frame_counter = 0
        self._processing_frame = False
        self._busy_skip_counter = 0
        self._identity_boundary_x = None
        self._pose_reset_pending = True

        try:
            if getattr(self.session, "current_index", 0) == 0:
                self.workout_controller.reset_full()
            else:
                self.workout_controller.reset_for_next_exercise()
        except Exception as e:
            print("[WORKOUT_CONTROLLER_RESET_WARN]", e)

        for user_key, state in self.user_states.items():
            was_finished = bool(state.finished)

            state.track_id = None
            state.registered = False
            state.track_box_ready = False
            state.last_bbox = None
            state.tracking_roi = None
            state.display_bbox = None
            state.initial_center_x = None
            state.identity_side = None
            state.pose_bbox = None
            state.recovery_pending = False
            state.recovery_cooldown = 0
            state.cycle_phase = "DONE" if was_finished else "IDLE"
            state.exercise_context_ttl = 0
            state.exercise_start_pose_ready = False
            state.reset_guidebox()
            state.reset_classification()
            state.reset_pose_gate()

            if was_finished:
                state.finished = True
                #print(f"[RESUME_SKIP_GUIDEBOX] {user_key} already finished")
            else:
                state.finished = False

        try:
            self.overlay.reset_colors()
            self.overlay.show_all(self.tracking_mode)
            self.overlay.hide_track_boxes()
            self.overlay.hide_skeleton("user1")
            self.overlay.hide_skeleton("user2")
            self._hide_finished_user_position_overlays()
            self._defer_overlay_relayout()
        except Exception as e:
            print("[OVERLAY_POSITION_RESET_WARN]", e)

        self.workout_controller.enter_position_check_phase()

        """print(
            "[POSITION_CHECK_READY]",
            "index=", getattr(self.session, "current_index", None),
            "label=", self._current_exercise_label(),
            "mode=", self.tracking_mode,
        )"""

    def stop_processing(self):
        if self.performance_logger.running:
            self.performance_logger.pause()

        self.yolo_active = False
        self._tracking_started = False
        self._processing_frame = False
        self._processor_busy = False
        self._pose_reset_pending = True

        for user_key, state in self.user_states.items():
            state.track_box_ready = False
            state.reset_classification()
            state.reset_pose_gate()

            try:
                self.overlay.hide_skeleton(user_key)
            except Exception:
                pass

    def reset_runtime_for_exercise(self):
        for user_key, state in self.user_states.items():
            state.reset_for_exercise()

            try:
                self.overlay.hide_skeleton(user_key)
            except Exception:
                pass

        self.rep_engine.reset_all()
        self.pose_bbox = None
        self.overlay.hide_track_boxes()

    def rep_engine_reset_current_exercise(self, current_label: str):
        for user_key in self._active_user_keys():
            self.rep_engine.reset_exercise(user_key, current_label)

    def setup_overlay(self):
        user1 = self.session.user1 or {}
        self.overlay.name1.setPlainText(
            user1.get("name", "User")
        )

        if self.tracking_mode == "multi":
            user2 = self.session.user2 or {}
            self.overlay.name2.setPlainText(
                user2.get("name", "Person 2")
            )

        self.overlay.reset_colors()
        self.overlay.show_all(self.tracking_mode)
        self._defer_overlay_relayout()

    def setup_labels(self):
        user1 = self.session.user1 or {}

        self.user1_label.setText(
            self._format_rep_label(
                user1.get("name", "User"), 
                self.user_states["user1"]
            )
        )
        self.user1_label.show()
        self.user1_slot.show()

        if self.tracking_mode == "multi":
            user2 = self.session.user2 or {}

            self.user2_label.setText(
                self._format_rep_label(
                    user2.get("name", "Person 2"), 
                    self.user_states["user2"]
                )
            )

            self.user2_label.show()
            self.user2_slot.show()
        else:
            self.user2_label.hide()
            self.user2_slot.hide()

    def update_reps(self, reps1, reps2=None):
        name1 = (self.session.user1 or {}).get("name", "User")
        self.user1_label.setText(f"{name1}: {reps1} reps")

        if reps2 is not None and self.tracking_mode == "multi":
            name2 = (self.session.user2 or {}).get("name", "Person 2")
            self.user2_label.setText(f"{name2}: {reps2} reps")

    def _format_rep_label(self, name: str, state: UserRuntimeState) -> str:
        if self.SHOW_TOTAL_REPS_IN_UI:
            return f"{name}: {state.valid_reps}/{state.total_reps} reps"
        return f"{name}: {state.valid_reps} reps"

    def _update_rep_labels(self):
        name1 = (self.session.user1 or {}).get("name", "User")
        s1 = self.user_states["user1"]
        self.user1_label.setText(self._format_rep_label(name1, s1))

        if self.tracking_mode == "multi":
            name2 = (self.session.user2 or {}).get("name", "Person 2")
            s2 = self.user_states["user2"]
            self.user2_label.setText(self._format_rep_label(name2, s2))

    def finish_current_workout(self):
        self._stop_duration_ui_timer()
        self.stop_processing()
        self.workout_done.emit()

    def process_position_phase(self, persons, frame):
        if not self._needs_position_check():
            return

        if not persons:
            for state in self.user_states.values():
                if not state.registered and not state.finished:
                    state.reset_guidebox()
            return

        if self.tracking_mode == "single":
            self.check_single_position(persons, frame)
        else:
            self.check_multi_position(persons, frame)

    def check_single_position(self, persons, frame):
        state = self.user_states["user1"]

        if state.registered or state.finished:
            state.reset_guidebox()
            return

        candidate = self._best_person_in_guidebox(
            persons,
            self.overlay.box1,
            frame,
        )

        self._handle_guidebox_candidate(
            user_key="user1",
            candidate=candidate,
        )

    def check_multi_position(self, persons, frame):
        """
        Visual mapping final:
        box1 = user1
        box2 = user2
        """
        candidate_user1 = None
        candidate_user2 = None

        if (
            not self.user_states["user1"].registered
            and not self.user_states["user1"].finished
        ):
            candidate_user1 = self._best_person_in_guidebox(
                persons,
                self.overlay.box1,
                frame,
            )

        if (
            not self.user_states["user2"].registered
            and not self.user_states["user2"].finished
        ):
            candidate_user2 = self._best_person_in_guidebox(
                persons,
                self.overlay.box2,
                frame,
            )

        if candidate_user1 and candidate_user2:
            if candidate_user1["track_id"] == candidate_user2["track_id"]:
                if candidate_user1["confidence"] >= candidate_user2["confidence"]:
                    candidate_user2 = None
                else:
                    candidate_user1 = None

        self._handle_guidebox_candidate(
            user_key="user1",
            candidate=candidate_user1,
        )

        self._handle_guidebox_candidate(
            user_key="user2",
            candidate=candidate_user2,
        )

    def _best_person_in_guidebox(self, persons, guidebox, frame):
        candidates = []

        for person in persons:
            if self.is_inside_guidebox(person["bbox"], guidebox, frame):
                candidates.append(person)

        if not candidates:
            return None

        """print(
            "[GUIDEBOX_CANDIDATES]",
            [
                {
                    "id": p.get("track_id"),
                    "conf": round(p.get("confidence", 0), 3),
                    "bbox": p.get("bbox"),
                    "area": (
                        p["bbox"][2] - p["bbox"][0]
                    ) * (
                        p["bbox"][3] - p["bbox"][1]
                    ),
                }
                for p in candidates
            ]
        )"""

        selected = max(
            candidates,
            key=lambda person: person["confidence"],
        )

        """print(
            "[GUIDEBOX_SELECTED]",
            {
                "id": selected.get("track_id"),
                "conf": selected.get("confidence"),
                "bbox": selected.get("bbox"),
            }
        )"""

        return selected

    def _handle_guidebox_candidate(self, user_key, candidate):
        state = self.user_states[user_key]

        if state.registered or state.finished:
            state.reset_guidebox()
            return

        if candidate is None:
            state.reset_guidebox()
            return

        track_id = candidate["track_id"]

        if self.DEBUG_VERBOSE:
            """print(
                f"[GUIDEBOX_CANDIDATE] {user_key} "
                f"track_id={track_id} "
                f"counter={state.guidebox_counter}"
            )"""

        existing_user = self.workout_controller.get_user_key(track_id)

        if existing_user is not None and existing_user != user_key:
            state.reset_guidebox()
            return

        if state.guidebox_candidate_track_id != track_id:
            state.guidebox_candidate_track_id = track_id
            state.guidebox_counter = 1
        else:
            state.guidebox_counter += 1

        if state.guidebox_counter >= self.GUIDEBOX_STABLE_FRAMES:
            self.confirm_user_detected(
                user_key,
                track_id,
                bbox=candidate.get("bbox"),
            )
            state.reset_guidebox()

    def confirm_user_detected(self, user_key, track_id, bbox=None):
        state = self.user_states[user_key]

        if state.registered or state.finished:
            return

        registered = self.workout_controller.try_register_user(
            user_key,
            track_id,
        )

        if not registered:
            return

        state.track_id = track_id
        state.registered = True
        state.last_bbox = bbox
        state.display_bbox = bbox
        state.initial_center_x = (
            self._bbox_center(bbox)[0]
            if bbox is not None
            else None
        )
        state.recovery_pending = False
        state.recovery_cooldown = 0

        #print(f"[DETECTED] {user_key} -> track_id={track_id}")

        self.overlay.detected(user_key)

        QTimer.singleShot(
            800,
            lambda uk=user_key: self._activate_user_tracking(uk)
        )
    
    def _activate_user_tracking(self, user_key):
        """
        Activate tracking for one registered user only.

        Multi mode concept:
        - user detected can immediately do the workout
        - the not detected user stays in guidebox/position check
        - if other unregistered user registered later, they'd be active later too
        """
        state = self.user_states.get(user_key)

        if state is None:
            return

        if not state.registered:
            return

        if state.finished:
            return

        self._tracking_started = True
        self.workout_controller.enter_tracking_phase()

        if self.tracking_mode == "single":
            self.overlay.hide_all()

        else:
            self.overlay.hide_detected_box(user_key)

        QTimer.singleShot(
            50,
            lambda uk=user_key: self._enable_track_box(uk),
        )

        #print(f"[USER_TRACKING] {user_key}")

    def enter_tracking_phase(self):
        self._tracking_started = True
        self.workout_controller.enter_tracking_phase()

        if self.tracking_mode == "single":
            self.overlay.hide_all()
            QTimer.singleShot(
                50,
                lambda: self._enable_track_box("user1"),
            )

        else:
            if self.user_states["user1"].finished:
                self._hide_user_position_overlay("user1")
            elif self.user_states["user1"].registered:
                self.overlay.hide_detected_box("user1")
                QTimer.singleShot(
                    50,
                    lambda: self._enable_track_box("user1"),
                )

            if self.user_states["user2"].finished:
                self._hide_user_position_overlay("user2")
            elif self.user_states["user2"].registered:
                self.overlay.hide_detected_box("user2")
                QTimer.singleShot(
                    50,
                    lambda: self._enable_track_box("user2"),
                )

        #print("[PHASE] TRACKING")

    def _enable_track_box(self, user_key):
        self.user_states[user_key].track_box_ready = True

        if self.DEBUG_VERBOSE:
            print(f"[TRACK_BOX_READY] {user_key}")

    def _select_person_for_user(self, user_key, persons):
        """
        Choose YOLO person for certain user.

        Priorities:
        1. Old Track ID still there, it can be used immediately
        2. Old Track ID gone, find bbox to the most similar or the closest last_bbox
        3. For single mode, do fallback to person area/biggest confidence
        """
        state = self.user_states.get(user_key)

        if state is None:
            return None

        if not state.registered or state.finished:
            return None

        if state.track_id is not None:
            for person in persons:
                if person.get("track_id") == state.track_id:
                    return person

        if state.last_bbox is not None:
            best_person = None
            best_score = -999999.0

            old_cx, old_cy = self._bbox_center(state.last_bbox)
            old_area = self._bbox_area(state.last_bbox)

            for person in persons:
                new_bbox = person.get("bbox")
                if not new_bbox:
                    continue

                existing_user = self.workout_controller.get_user_key(
                    person.get("track_id")
                )

                if existing_user is not None and existing_user != user_key:
                    continue

                new_cx, new_cy = self._bbox_center(new_bbox)
                new_area = self._bbox_area(new_bbox)

                center_dist = ((new_cx - old_cx) ** 2 + (new_cy - old_cy) ** 2) ** 0.5
                iou = calculate_iou(state.last_bbox, new_bbox)
                conf = float(person.get("confidence", 0.0) or 0.0)

                area_ratio = min(old_area, new_area) / max(1.0, max(old_area, new_area))

                score = (
                    (iou * 3.0)
                    + (area_ratio * 1.2)
                    + (conf * 1.0)
                    - (center_dist / 900.0)
                )

                if score > best_score:
                    best_score = score
                    best_person = person

            if best_person is not None and best_score >= 0.15:
                return best_person

        if self.tracking_mode == "single":
            valid = [
                p for p in persons
                if float(p.get("confidence", 0.0) or 0.0) >= 0.25
            ]

            if not valid:
                return None

            return max(
                valid,
                key=lambda p: self._bbox_area(p["bbox"]) * float(p.get("confidence", 0.0) or 0.0)
            )

        return None

    def _bbox_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return (
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0,
        )

    def _bbox_area(self, bbox):
        x1, y1, x2, y2 = bbox
        return max(1.0, float((x2 - x1) * (y2 - y1)))
    
    def _smooth_bbox(self, old_bbox, new_bbox, alpha=0.60):
        """
        Exponential smoothing for bbox YOLO.

        high alpha = smoother, but more delay.
        low alpha  = more responsive, but more jittering.
        """
        if old_bbox is None:
            return new_bbox

        ox1, oy1, ox2, oy2 = old_bbox
        nx1, ny1, nx2, ny2 = new_bbox

        return (
            int((ox1 * alpha) + (nx1 * (1.0 - alpha))),
            int((oy1 * alpha) + (ny1 * (1.0 - alpha))),
            int((ox2 * alpha) + (nx2 * (1.0 - alpha))),
            int((oy2 * alpha) + (ny2 * (1.0 - alpha))),
        )

    def _bbox_sanity_ok(self, old_bbox, new_bbox, frame, exercise):
        if old_bbox is None:
            return True

        h, w = frame.shape[:2]

        old_area = self._bbox_area(old_bbox)
        new_area = self._bbox_area(new_bbox)

        area_ratio = new_area / max(1.0, old_area)

        old_cx, old_cy = self._bbox_center(old_bbox)
        new_cx, new_cy = self._bbox_center(new_bbox)

        center_dist = ((new_cx - old_cx) ** 2 + (new_cy - old_cy) ** 2) ** 0.5

        if exercise == "sit_up":
            max_area_ratio = 2.4
            min_area_ratio = 0.35
            max_center_dist = w * 0.35
        else:
            max_area_ratio = 2.0
            min_area_ratio = 0.45
            max_center_dist = w * 0.25

        if area_ratio > max_area_ratio:
            return False

        if area_ratio < min_area_ratio:
            return False

        if center_dist > max_center_dist:
            return False

        return True

    def _bbox_smooth_alpha(self, exercise):
        if exercise == "sit_up":
            return 0.45

        if exercise in ("knee_push_up", "mountain_climber"):
            return 0.50

        return 0.40

    def _bbox_union(self, bbox_a, bbox_b):
        if bbox_a is None:
            return bbox_b

        if bbox_b is None:
            return bbox_a

        ax1, ay1, ax2, ay2 = bbox_a
        bx1, by1, bx2, by2 = bbox_b

        return (
            min(ax1, bx1),
            min(ay1, by1),
            max(ax2, bx2),
            max(ay2, by2),
        )


    def _bbox_touches_frame_edge(self, bbox, frame, margin=2):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox

        return (
            x1 <= margin
            or y1 <= margin
            or x2 >= w - margin
            or y2 >= h - margin
        )


    def _pose_roi_candidate_ok(self, old_bbox, new_bbox, frame, exercise):
        if old_bbox is None:
            return True

        old_area = self._bbox_area(old_bbox)
        new_area = self._bbox_area(new_bbox)

        area_ratio = new_area / max(1.0, old_area)

        old_cx, old_cy = self._bbox_center(old_bbox)
        new_cx, new_cy = self._bbox_center(new_bbox)

        h, w = frame.shape[:2]

        center_dist = (
            (new_cx - old_cx) ** 2
            + (new_cy - old_cy) ** 2
        ) ** 0.5

        if exercise == "sit_up":
            if area_ratio > 2.2:
                return False

            if area_ratio < 0.35:
                return False

            if center_dist > w * 0.40:
                return False

            if self._bbox_touches_frame_edge(new_bbox, frame):
                if area_ratio > 1.45:
                    return False

        else:
            if area_ratio > 1.8:
                return False

            if area_ratio < 0.45:
                return False

            if center_dist > w * 0.25:
                return False

        return True


    def _update_pose_bbox(self, state, person_bbox, frame, exercise, is_fallback):
        """
        Designated bbox for MediaPipe crop.
        So that ROI Mediapipe is more stable than raw YOLO bbox.
        """

        if is_fallback:
            return state.pose_bbox

        if person_bbox is None:
            return state.pose_bbox

        candidate = person_bbox

        if state.pose_bbox is None:
            if exercise == "sit_up":
                state.pose_bbox = self._expand_bbox(
                    candidate,
                    frame,
                    scale_x=1.15,
                    scale_y=1.10,
                )
            else:
                state.pose_bbox = self._expand_bbox(
                    candidate,
                    frame,
                    scale_x=1.10,
                    scale_y=1.10,
                )

            return state.pose_bbox

        if not self._pose_roi_candidate_ok(
            old_bbox=state.pose_bbox,
            new_bbox=candidate,
            frame=frame,
            exercise=exercise,
        ):
            return state.pose_bbox

        if exercise == "sit_up":
            target = self._bbox_union(state.pose_bbox, candidate)

            target = self._expand_bbox(
                target,
                frame,
                scale_x=1.03,
                scale_y=1.03,
            )

            state.pose_bbox = self._smooth_bbox(
                old_bbox=state.pose_bbox,
                new_bbox=target,
                alpha=0.82,
            )

        else:
            target = self._expand_bbox(
                candidate,
                frame,
                scale_x=1.08,
                scale_y=1.08,
            )

            state.pose_bbox = self._smooth_bbox(
                old_bbox=state.pose_bbox,
                new_bbox=target,
                alpha=0.65,
            )

        return state.pose_bbox

    def _ensure_tracking_rois(self, frame, force=False):
        """
        Build stable per-user MediaPipe workspaces after YOLO placement.

        Single mode uses the full frame. Multi mode uses a left and a right
        full-height zone with a small overlap. This is the key that
        removes the per-frame YOLO crop dependency while keeping each
        num_poses=1 MediaPipe instance isolated.
        """
        if frame is None:
            return

        h, w = frame.shape[:2]
        if h <= 0 or w <= 0:
            return

        active = [
            user_key
            for user_key in self._active_user_keys()
            if self.user_states[user_key].registered
            and not self.user_states[user_key].finished
        ]

        if not active:
            return

        if self.tracking_mode == "single":
            state = self.user_states["user1"]
            if force or state.tracking_roi is None:
                state.tracking_roi = (0, 0, w, h)
                state.pose_bbox = state.tracking_roi
                state.identity_side = "full"
            return

        centers = {}
        for user_key in active:
            state = self.user_states[user_key]
            center_x = state.initial_center_x
            if center_x is None and state.last_bbox is not None:
                center_x = self._bbox_center(state.last_bbox)[0]
            if center_x is not None:
                centers[user_key] = float(center_x)

        if not centers:
            return

        overlap = int(w * self.MULTI_ROI_OVERLAP_RATIO)

        if len(centers) >= 2:
            ordered = sorted(centers.items(), key=lambda item: item[1])
            left_user, left_x = ordered[0]
            right_user, right_x = ordered[-1]
            boundary = int((left_x + right_x) / 2.0)
            boundary = max(int(w * 0.30), min(int(w * 0.70), boundary))
            self._identity_boundary_x = boundary

            left_state = self.user_states[left_user]
            right_state = self.user_states[right_user]

            if force or left_state.tracking_roi is None:
                left_state.tracking_roi = (
                    0,
                    0,
                    min(w, boundary + overlap),
                    h,
                )
                left_state.pose_bbox = left_state.tracking_roi
            left_state.identity_side = "left"

            if force or right_state.tracking_roi is None:
                right_state.tracking_roi = (
                    max(0, boundary - overlap),
                    0,
                    w,
                    h,
                )
                right_state.pose_bbox = right_state.tracking_roi
            right_state.identity_side = "right"
            return

        user_key, center_x = next(iter(centers.items()))
        state = self.user_states[user_key]
        boundary = int(w * 0.50)
        self._identity_boundary_x = boundary

        if center_x <= boundary:
            state.identity_side = "left"
            roi = (0, 0, min(w, boundary + overlap), h)
        else:
            state.identity_side = "right"
            roi = (max(0, boundary - overlap), 0, w, h)

        if force or state.tracking_roi is None:
            state.tracking_roi = roi
            state.pose_bbox = roi

    def _crop_exact_roi(self, frame, bbox, user_key):
        if frame is None or bbox is None:
            return None

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(w, int(x1)))
        y1 = max(0, min(h, int(y1)))
        x2 = max(0, min(w, int(x2)))
        y2 = max(0, min(h, int(y2)))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        self._last_crop_size[user_key] = (crop.shape[1], crop.shape[0])
        return crop.copy(), (x1, y1, x2, y2)

    def _build_pose_jobs(self, frame):
        jobs = {}
        pose_stride = self._pose_frame_stride()

        for user_key in self._active_user_keys():
            state = self.user_states[user_key]
            if not state.registered or state.finished:
                continue

            user_offset = 0 if user_key == "user1" else 1
            if pose_stride > 1:
                if (self._frame_counter + user_offset) % pose_stride != 0:
                    continue

            roi = state.tracking_roi or state.pose_bbox
            crop_data = self._crop_exact_roi(frame, roi, user_key)
            if crop_data is None:
                state.recovery_pending = True
                continue

            crop_rgb, crop_bbox = crop_data
            jobs[user_key] = {
                "crop": crop_rgb,
                "crop_bbox": crop_bbox,
            }

        return jobs

    def _recovery_users_due(self):
        due = []
        for user_key in self._active_user_keys():
            state = self.user_states[user_key]
            if not state.registered or state.finished or not state.recovery_pending:
                continue

            if state.recovery_cooldown > 0:
                state.recovery_cooldown -= 1
                continue

            due.append(user_key)
        return due

    def _candidate_matches_identity_zone(self, user_key, bbox, frame):
        if self.tracking_mode != "multi":
            return True

        state = self.user_states[user_key]
        boundary = self._identity_boundary_x
        if boundary is None or state.identity_side not in ("left", "right"):
            return True

        _, w = frame.shape[:2]
        tolerance = w * self.IDENTITY_BOUNDARY_TOLERANCE_RATIO
        center_x = self._bbox_center(bbox)[0]

        if state.identity_side == "left":
            return center_x <= boundary + tolerance
        return center_x >= boundary - tolerance

    def _score_recovery_candidate(self, state, bbox, confidence):
        reference = state.display_bbox or state.last_bbox
        if reference is None:
            return float(confidence)

        old_cx, old_cy = self._bbox_center(reference)
        new_cx, new_cy = self._bbox_center(bbox)
        center_dist = ((new_cx - old_cx) ** 2 + (new_cy - old_cy) ** 2) ** 0.5

        old_area = self._bbox_area(reference)
        new_area = self._bbox_area(bbox)
        area_ratio = min(old_area, new_area) / max(old_area, new_area, 1.0)
        iou = calculate_iou(reference, bbox)

        return (
            (iou * 2.5)
            + (area_ratio * 1.0)
            + float(confidence)
            - (center_dist / 900.0)
        )

    def _apply_yolo_recovery(self, persons, frame, recovery_users):
        if not recovery_users:
            return

        used_track_ids = set()
        assignments = []

        for user_key in recovery_users:
            state = self.user_states[user_key]
            best = None
            best_score = -999999.0

            for person in persons:
                track_id = person.get("track_id")
                bbox = person.get("bbox")
                if track_id is None or bbox is None or track_id in used_track_ids:
                    continue

                owner = self.workout_controller.get_user_key(track_id)
                if owner is not None and owner != user_key:
                    continue

                if not self._candidate_matches_identity_zone(user_key, bbox, frame):
                    continue

                score = self._score_recovery_candidate(
                    state,
                    bbox,
                    person.get("confidence", 0.0),
                )
                if track_id == state.track_id:
                    score += 2.0

                if score > best_score:
                    best_score = score
                    best = person

            if best is not None and best_score >= 0.10:
                assignments.append((user_key, best, best_score))
                used_track_ids.add(best["track_id"])

        for user_key, person, score in assignments:
            state = self.user_states[user_key]
            new_track_id = person["track_id"]

            if state.track_id != new_track_id:
                if not self.workout_controller.update_user_track(user_key, new_track_id):
                    continue
                """print(
                    f"[YOLO_RECOVERY_ID] {user_key} "
                    f"old={state.track_id} new={new_track_id} score={score:.3f}"
                )"""
                state.track_id = new_track_id

            state.last_bbox = person["bbox"]
            if state.display_bbox is None:
                state.display_bbox = person["bbox"]
            state.recovery_pending = False
            state.recovery_cooldown = self.YOLO_RECOVERY_COOLDOWN_FRAMES
            state.pose_lost_counter = max(
                0,
                self.POSE_RECOVERY_TRIGGER_FRAMES - 2,
            )

        assigned_users = {item[0] for item in assignments}
        for user_key in recovery_users:
            if user_key not in assigned_users:
                state = self.user_states[user_key]
                state.recovery_cooldown = self.YOLO_RECOVERY_COOLDOWN_FRAMES

    def _pose_bbox_from_landmarks(self, pose_result, landmarks_frame_px, frame):
        landmarks = (pose_result or {}).get("landmarks") or []
        if not landmarks or not landmarks_frame_px:
            return None

        points = []
        for idx, point in enumerate(landmarks_frame_px):
            if idx >= len(landmarks):
                continue

            parsed = self._landmark_xyv(landmarks[idx])
            visibility = parsed[2] if parsed is not None else 0.0
            if visibility < self.POSE_DISPLAY_VISIBILITY_THRESHOLD:
                continue

            x, y = point
            points.append((float(x), float(y)))

        if len(points) < 4:
            return None

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)

        bw = max(1.0, x2 - x1)
        bh = max(1.0, y2 - y1)
        exercise = self._current_exercise_label()

        if self._is_floor_exercise(exercise):
            pad_x = bw * 0.15
            pad_y = bh * 0.20
        else:
            pad_x = bw * 0.10
            pad_y = bh * 0.10

        h, w = frame.shape[:2]
        return (
            int(max(0, x1 - pad_x)),
            int(max(0, y1 - pad_y)),
            int(min(w, x2 + pad_x)),
            int(min(h, y2 + pad_y)),
        )

    def _handle_pose_miss(self, user_key):
        state = self.user_states[user_key]
        state.pose_lost_counter += 1
        state.lost_detection_counter += 1
        self._decay_class_state(user_key)

        if state.lost_detection_counter >= self.POSE_RECOVERY_TRIGGER_FRAMES:
            state.recovery_pending = True

        if state.pose_lost_counter >= self.POSE_LOST_FRAMES:
            state.pose_ready = False
            state.pose_quality_counter = 0
            self.overlay.hide_skeleton(user_key)
            self.overlay.hide_track_box(user_key, hide_skeleton=True)

    def process_pose_results(self, pose_results, frame):
        if not self._tracking_started:
            return

        self._last_frame_shape = frame.shape
        self._frame_counter += 1
        current_label = self._current_exercise_label()

        for user_key in self._active_user_keys():
            state = self.user_states[user_key]
            if not state.registered or state.finished:
                continue
            if user_key not in pose_results:
                continue

            entry = pose_results.get(user_key) or {}
            pose_result = entry.get("pose_result")
            crop_bbox = entry.get("crop_bbox")
            if pose_result is None or crop_bbox is None:
                self._handle_pose_miss(user_key)
                continue

            landmarks_frame_px = self._landmarks_crop_to_frame(
                user_key=user_key,
                landmarks_px=pose_result["landmarks_px"],
                bbox=crop_bbox,
            )

            display_bbox = self._pose_bbox_from_landmarks(
                pose_result=pose_result,
                landmarks_frame_px=landmarks_frame_px,
                frame=frame,
            )
            if display_bbox is not None:
                if not self._candidate_matches_identity_zone(user_key, display_bbox, frame):
                    self._handle_pose_miss(user_key)
                    continue
                state.display_bbox = self._smooth_bbox(
                    state.display_bbox,
                    display_bbox,
                    alpha=0.55,
                )
                self.update_tracking_box(user_key, state.display_bbox)

            quality_ok = self._pose_quality_ok(
                pose_result=pose_result,
                exercise=current_label,
            )
            pose_ready = self._update_pose_gate(
                user_key=user_key,
                pose_result=pose_result,
                exercise=current_label,
            )

            if not quality_ok:
                state.lost_detection_counter += 1
                self._decay_class_state(user_key)
                state.last_feedback = "Pastikan tubuh terlihat jelas."
                if state.lost_detection_counter >= self.POSE_RECOVERY_TRIGGER_FRAMES:
                    state.recovery_pending = True
                if not pose_ready:
                    self.overlay.hide_skeleton(user_key)
                continue

            if not pose_ready:
                state.last_feedback = "Menstabilkan estimasi pose..."
                self._decay_class_state(user_key)
                continue

            state.recovery_pending = False
            state.recovery_cooldown = 0
            state.lost_detection_counter = 0

            landmarks_vp = self._landmarks_to_viewport(
                user_key=user_key,
                landmarks_px=pose_result["landmarks_px"],
                bbox=crop_bbox,
            )
            user_offset = 0 if user_key == "user1" else 1
            skeleton_stride = self._skeleton_frame_stride()
            if not self.PERF_DISABLE_SKELETON:
                if (self._frame_counter + user_offset) % skeleton_stride == 0:
                    self.overlay.update_skeleton(user_key, landmarks_vp)

            angles_for_engine = self._angles_for_engine(
                exercise=current_label,
                pose_result=pose_result,
            )

            if current_label == "knee_push_up" and not state.exercise_start_pose_ready:
                if self._knee_push_up_start_pose_ok(angles_for_engine):
                    state.exercise_start_pose_ready = True
                    state.cycle_phase = "IDLE"
                    self.rep_engine.reset_exercise(user_key, current_label)
                else:
                    state.last_feedback = "Ambil posisi knee push-up terlebih dahulu."
                    self._decay_class_state(user_key)
                    continue

            if self.PERF_DISABLE_LSTM:
                class_valid = True
                movement_context_status = "MATCH"
                state.current_class = current_label
                state.class_status = "MATCH"
                state.class_ttl = self.CLASS_GATE_TTL_FRAMES
            else:
                classifier = self.lstm.get(user_key)
                if (
                    self.CLASSIFICATION_TEST_LOG_ENABLED
                    and classifier is not None
                    and state.class_test_started_at is None
                ):
                    state.class_test_started_at = perf_counter()

                clf_result = (
                    classifier.push(pose_result["features"])
                    if classifier is not None
                    else None
                )
                if clf_result is not None:
                    self.performance_logger.record_model_inference(
                        user_key
                    )
                self._update_class_state(
                    user_key=user_key,
                    clf_result=clf_result,
                    current_label=current_label,
                )
                """self._print_first_stable_prediction(
                    user_key=user_key,
                    clf_result=clf_result,
                    ground_truth=current_label,
                )"""
                movement_context_status = self._movement_context_status(
                    user_key,
                    current_label,
                )
                class_valid = movement_context_status == "MATCH"

            if self.PERF_DISABLE_REP_ENGINE:
                continue

            # KinematicRepEngine always runs from geometry. LSTM never controls
            # phase transitions or posture rules; it only gates a completed
            # cycle in _handle_cycle_result.
            cycle_result = self.rep_engine.update(
                user_key=user_key,
                exercise=current_label,
                angles=angles_for_engine,
                landmarks=landmarks_frame_px,
                class_valid=class_valid,
            )

            self._handle_cycle_result(
                user_key=user_key,
                result=cycle_result,
                movement_context_status=movement_context_status,
            )

    def _handle_cycle_result(
        self,
        user_key: str,
        result: RepCycleResult,
        movement_context_status: str = "UNKNOWN",
    ):
        state = self.user_states[user_key]
        current_label = self._current_exercise_label()

        previous_phase = state.cycle_phase

        if result.phase != previous_phase:
            if self._is_rep_start_transition(
                exercise=current_label,
                previous_phase=previous_phase,
                current_phase=result.phase,
            ):
                self._start_rep_classification_capture(user_key)

            state.cycle_phase = result.phase

        if not result.rep_completed:
            return

        # Satu cycle selesai = satu percobaan klasifikasi.
        self._finish_rep_classification_capture(
            user_key=user_key,
            ground_truth=current_label,
        )

        geometry_strong = self._is_geometry_strong(
            exercise=current_label,
            debug=result.debug,
        )

        # Division of responsibility:
        # MATCH    -> LSTM confirms movement; accept the kinematic cycle.
        # UNKNOWN  -> LSTM has no stable answer; accept only strong geometry.
        # MISMATCH -> LSTM stably recognizes another movement; never override
        #             that contradiction with geometry fallback.
        if movement_context_status == "MATCH":
            countable_cycle = True
        elif movement_context_status == "UNKNOWN":
            countable_cycle = geometry_strong
        else:  # MISMATCH
            countable_cycle = False

        if not countable_cycle:
            if movement_context_status == "MISMATCH":
                state.last_feedback = "Gerakan tidak sesuai dengan workout yang diminta."
            else:
                state.last_feedback = "Gerakan belum dikenali dengan cukup yakin."
            self._update_rep_labels()
            return

        state.total_reps += 1
        if result.valid_rep:
            state.valid_reps += 1
            state.last_feedback = "OK"
            self._flash_rep_feedback(user_key, "valid")
        else:
            state.last_feedback = result.feedback or "Postur belum sesuai."
            self._flash_rep_feedback(user_key, "wrong")

        self._update_rep_labels()
        target = int(self.current_workout.get("reps_target", 0) or 0)
        if target > 0 and state.valid_reps >= target:
            self._on_user_finished(user_key)

    def update_tracking_box(self, user_key, bbox):
        state = self.user_states[user_key]

        if not state.track_box_ready:
            return

        fh, fw = self._last_frame_shape[:2]

        vw = self.camera_view.viewport().width()
        vh = self.camera_view.viewport().height()

        if fw == 0 or fh == 0:
            return

        sx = vw / fw
        sy = vh / fh

        x1, y1, x2, y2 = bbox

        x1_vp = vw - (x2 * sx)
        x2_vp = vw - (x1 * sx)
        y1_vp = y1 * sy
        y2_vp = y2 * sy

        bbox_vp = (
            x1_vp,
            y1_vp,
            x2_vp,
            y2_vp,
        )

        self.overlay.update_track_box(user_key, bbox_vp)

    def _update_class_state(self, user_key, clf_result, current_label):
        """Store one stable LSTM movement-context result.

        Majority voting belongs to AttnLSTMClassifier. A second majority vote in
        WorkoutSession previously made labels unnecessarily stale.
        """
        state = self.user_states[user_key]

        # No inference was scheduled on this frame: keep a short TTL bridge.
        if clf_result is None:
            self._decay_class_state(user_key)
            return

        voted_label = clf_result.get("voted")
        if voted_label is None:
            # The classifier's own vote window is already uncertain. Clear the
            # application context immediately instead of extending a stale label.
            state.current_class = None
            state.class_confidence = 0.0
            state.class_ttl = 0
            state.class_status = "UNKNOWN"
            return

        state.current_class = voted_label
        state.class_confidence = float(
            clf_result.get("voted_confidence", clf_result.get("confidence", 0.0))
            or 0.0
        )
        state.class_ttl = self.CLASS_GATE_TTL_FRAMES
        state.class_status = "MATCH" if voted_label == current_label else "MISMATCH"

        self._capture_rep_stable_prediction(
            user_key=user_key,
            prediction=voted_label,
            confidence=state.class_confidence,
        )

        if self.DEBUG_VERBOSE:
            print(
                f"[CLF] {user_key} "
                f"stable={voted_label} "
                f"current={current_label} "
                f"status={state.class_status} "
                f"confidence={state.class_confidence:.3f} "
                f"ttl={state.class_ttl}"
            )

    def _print_first_stable_prediction(
        self,
        user_key: str,
        clf_result: dict | None,
        ground_truth: str,
    ):
        if not self.CLASSIFICATION_TEST_LOG_ENABLED:
            return

        state = self.user_states[user_key]

        if state.first_stable_prediction_logged:
            return

        if clf_result is None:
            return

        predicted_label = clf_result.get("voted")
        if predicted_label is None:
            return

        if state.class_test_started_at is None:
            return

        elapsed_seconds = (
            perf_counter() - state.class_test_started_at
        )

        confidence = float(
            clf_result.get(
                "voted_confidence",
                clf_result.get("confidence", 0.0),
            )
            or 0.0
        )

        result = (
            "BENAR"
            if predicted_label == ground_truth
            else "SALAH"
        )

        print(
            "[LSTM_STABLE_RESULT]",
            f"mode={self.tracking_mode}",
            f"user={user_key}",
            f"ground_truth={ground_truth}",
            f"prediction={predicted_label}",
            f"confidence={confidence:.4f}",
            f"time_to_stable_s={elapsed_seconds:.3f}",
            f"result={result}",
        )

        state.first_stable_prediction_logged = True

    def _decay_class_state(self, user_key):
        state = self.user_states[user_key]
        if state.class_ttl > 0:
            state.class_ttl -= 1
        if state.class_ttl <= 0:
            state.class_ttl = 0
            state.current_class = None
            state.class_confidence = 0.0
            state.class_status = "UNKNOWN"

    def _movement_context_status(self, user_key, current_label) -> str:
        state = self.user_states[user_key]
        if state.class_ttl <= 0 or state.current_class is None:
            state.class_status = "UNKNOWN"
        elif state.current_class == current_label:
            state.class_status = "MATCH"
        else:
            state.class_status = "MISMATCH"
        return state.class_status

    def _is_current_class_valid(self, user_key, current_label):
        return self._movement_context_status(user_key, current_label) == "MATCH"

    def _on_user_finished(self, user_key: str):
        state = self.user_states[user_key]

        if state.finished:
            return

        #print(f"[DONE] {user_key} selesai")

        state.finished = True
        state.track_box_ready = False
        state.reset_classification()
        state.reset_pose_gate()

        self.overlay.hide_skeleton(user_key)

        if hasattr(self, "audio_feedback"):
            self.audio_feedback.play(
                status="finished",
                mode=self.tracking_mode or "single",
                user_key=user_key,
            )

        try:
            if hasattr(self.overlay, "flash_track_box"):
                self.overlay.flash_track_box(user_key, "finished", duration_ms=850)
        except Exception as e:
            print(f"[FINISHED_FLASH_WARN] {user_key}: {e}")

        QTimer.singleShot(
            850,
            lambda uk=user_key: self.overlay.hide_track_box(
                uk,
                hide_skeleton=True,
            )
        )

        if self._all_users_finished():
            QTimer.singleShot(1200, self._advance_exercise)

    def _all_users_finished(self) -> bool:
        if self.tracking_mode == "single":
            return self.user_states["user1"].finished

        return (
            self.user_states["user1"].finished
            and
            self.user_states["user2"].finished
        )

    def _advance_exercise(self):
        """
        Called after all required users finish the current exercise.

        Responsibility split:
        - WorkoutSession saves the result for the active workout.
        - WorkoutSession stops inference/camera processing.
        - WorkoutSession emits workout_done.
        - AppWindow handles session.next_workout() and page navigation.
        """
        if self._exercise_transitioning:
            #print("[ADVANCE_SKIPPED] already transitioning")
            return

        self._exercise_transitioning = True

        total_workouts = len(
            getattr(self.session, "workouts", []) or []
        )
        current_index = int(
            getattr(self.session, "current_index", 0) or 0
        )
        is_last_exercise = (
            total_workouts > 0
            and current_index >= total_workouts - 1
        )

        self._save_exercise_result()
        self._stop_duration_ui_timer()
        self.stop_processing()

        if (
            self.PERF_TEST_ENABLED
            and is_last_exercise
        ):
            output_path = self.performance_logger.finish_and_save()
            print(
                "[PERFORMANCE_RESULT_READY]",
                output_path,
            )

        try:
            self.overlay.hide_track_boxes()
            self.overlay.hide_skeleton("user1")
            self.overlay.hide_skeleton("user2")
        except Exception as e:
            print("[ADVANCE_OVERLAY_WARN]", e)

        if self.session is not None:
            try:
                self.session.current_page = "guide"
            except Exception:
                pass

        """print(
            "[EXERCISE_DONE_SIGNAL]",
            "index=", getattr(self.session, "current_index", None),
            "name=", self.current_workout.get("name") if self.current_workout else None,
        )"""

        self.workout_done.emit()

    def _try_open_next_workout_guide(self) -> bool:
        root = self.window()
        if root is None:
            return False

        guide_page = None

        for getter_name in (
            "find_page",
            "get_page",
            "page",
            "getPage",
            "findPage",
        ):
            getter = getattr(root, getter_name, None)
            if callable(getter):
                try:
                    guide_page = getter("workout_guide")
                    if guide_page is not None:
                        break
                except Exception as e:
                    print(f"[GUIDE_GETTER_WARN] {getter_name}: {e}")

        if guide_page is None:
            for attr_name in ("pages", "page_map", "pageMap"):
                pages = getattr(root, attr_name, None)
                if isinstance(pages, dict):
                    guide_page = pages.get("workout_guide")
                    if guide_page is not None:
                        break

        if guide_page is not None:
            try:
                if hasattr(guide_page, "set_session"):
                    guide_page.set_session(self.session)
            except Exception as e:
                print(f"[GUIDE_SET_SESSION_WARN] {e}")

        for nav_name in (
            "switch_page",
            "show_page",
            "go_to_page",
            "navigate_to",
            "set_current_page",
            "set_page",
            "change_page",
        ):
            nav = getattr(root, nav_name, None)
            if callable(nav):
                try:
                    nav("workout_guide")
                    #print("[NEXT_WORKOUT_GUIDE_NAV] method=", nav_name)
                    return True
                except Exception as e:
                    print(f"[GUIDE_NAV_WARN] {nav_name}: {e}")

        if guide_page is not None:
            for stack_name in ("stack", "stacked_widget", "stackedWidget", "pages_stack"):
                stack = getattr(root, stack_name, None)
                if stack is not None and hasattr(stack, "setCurrentWidget"):
                    try:
                        stack.setCurrentWidget(guide_page)
                        #print("[NEXT_WORKOUT_GUIDE_NAV] stack=", stack_name)
                        return True
                    except Exception as e:
                        print(f"[GUIDE_STACK_WARN] {stack_name}: {e}")

        return False

    def _save_exercise_result(self):
        s1 = self.user_states["user1"]

        result = {
            "exercise": self.current_workout.get("name"),
            "exercise_id": self.current_workout.get("id"),
            "user1": {
                "valid_reps": s1.valid_reps,
                "total_reps": s1.total_reps,
                "last_feedback": s1.last_feedback,
            },
        }

        if self.tracking_mode == "multi":
            s2 = self.user_states["user2"]

            result["user2"] = {
                "valid_reps": s2.valid_reps,
                "total_reps": s2.total_reps,
                "last_feedback": s2.last_feedback,
            }

        if hasattr(self.session, "add_workout_result"):
            self.session.add_workout_result(result)
        elif hasattr(self.session, "add_exercise_result"):
            self.session.add_exercise_result(result)
        else:
            if not hasattr(self.session, "results") or self.session.results is None:
                self.session.results = []
            self.session.results.append(result)

        #print(f"[RESULT] {result}")
        #print("[SESSION_RESULTS_AFTER_SAVE]", getattr(self.session, "results", []))

    def _hide_user_position_overlay(self, user_key: str):
        try:
            if hasattr(self.overlay, "hide_detected_box"):
                self.overlay.hide_detected_box(user_key)
        except Exception:
            pass

        item_names = (
            ("box1", "name1", "track_box1")
            if user_key == "user1"
            else ("box2", "name2", "track_box2")
        )

        for item_name in item_names:
            item = getattr(self.overlay, item_name, None)
            if item is not None and hasattr(item, "hide"):
                try:
                    item.hide()
                except Exception:
                    pass

        try:
            self.overlay.hide_skeleton(user_key)
        except Exception:
            pass

    def _hide_finished_user_position_overlays(self):
        for user_key, state in self.user_states.items():
            if state.finished:
                self._hide_user_position_overlay(user_key)

    def _active_user_keys(self) -> list[str]:
        if self.tracking_mode == "multi":
            return ["user1", "user2"]
        return ["user1"]

    def _needs_position_check(self) -> bool:
        if self.tracking_mode == "single":
            s1 = self.user_states["user1"]
            return not s1.finished and not s1.registered

        return any(
            (not state.finished and not state.registered)
            for state in (self.user_states["user1"], self.user_states["user2"])
        )

    def _current_exercise_label(self) -> str:
        if not self.current_workout:
            return ""
        return self._workout_name_to_label(self.current_workout["name"])

    def is_inside_guidebox(self, bbox, guidebox, frame):
        vw = self.camera_view.viewport().width()
        vh = self.camera_view.viewport().height()
        fh, fw = frame.shape[:2]

        return bbox_overlaps_guidebox(
            bbox,
            guidebox.rect(),
            frame_w=fw,
            frame_h=fh,
            viewport_w=vw,
            viewport_h=vh,
            mirrored=True,
        )
    
    def _is_floor_exercise(self, exercise: str) -> bool:
        return exercise in (
            "sit_up",
            "knee_push_up",
            "mountain_climber",
        )

    def _make_fallback_persons(self, frame, exercise):
        """
        Emergency fallback when YOLO isn't detecting 'Person'.

        Using expnded last_bbox so that MediaPipe can still 'see' body area
        that is relatively stable.
        """
        if not self._is_floor_exercise(exercise):
            return []

        fallback_persons = []

        for user_key in self._active_user_keys():
            state = self.user_states[user_key]

            if not state.registered:
                continue

            if state.finished:
                continue

            if state.track_id is None:
                continue

            if state.last_bbox is None:
                continue

            state.lost_detection_counter += 1

            max_hold_frames = 12 if self.tracking_mode == "single" else 8

            if state.lost_detection_counter > max_hold_frames:
                """print(
                    f"[YOLO_FALLBACK_STOP] "
                    f"user={user_key} "
                    f"lost={state.lost_detection_counter}"
                )"""
                continue

            scale_x, scale_y = self._fallback_bbox_scale(exercise)

            bbox = self._expand_bbox(
                state.last_bbox,
                frame,
                scale_x=scale_x,
                scale_y=scale_y,
            )

            fallback_persons.append(
                {
                    "bbox": bbox,
                    "confidence": 0.0,
                    "track_id": state.track_id,
                    "_source": "last_bbox_fallback",
                    "_fallback_user": user_key,
                }
            )

            """print(
                f"[YOLO_FALLBACK_LAST_BBOX] "
                f"user={user_key} "
                f"exercise={exercise} "
                f"lost={state.lost_detection_counter} "
                f"bbox={bbox}"
            )"""

        return fallback_persons

    def _expand_bbox(self, bbox, frame, scale_x=1.5, scale_y=1.4):
        h, w = frame.shape[:2]

        x1, y1, x2, y2 = bbox

        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        bw = max(1.0, x2 - x1)
        bh = max(1.0, y2 - y1)

        new_w = bw * scale_x
        new_h = bh * scale_y

        nx1 = int(max(0, cx - new_w / 2.0))
        ny1 = int(max(0, cy - new_h / 2.0))
        nx2 = int(min(w, cx + new_w / 2.0))
        ny2 = int(min(h, cy + new_h / 2.0))

        return (nx1, ny1, nx2, ny2)

    def _fallback_bbox_scale(self, exercise):
        """
        Scale fallback bbox based on exercise.
        For floor-based exercise like sit up, knee push up, mountain climber.
        """
        if exercise == "sit_up":
            return 1.55, 1.25

        if exercise == "knee_push_up":
            return 1.45, 1.12

        if exercise == "mountain_climber":
            return 1.7, 1.35

        return 1.4, 1.25

    def _handle_tracking_lost(self, user_key):
        state = self.user_states[user_key]

        state.pose_lost_counter += 1
        self._decay_class_state(user_key)

        if state.pose_lost_counter >= self.POSE_LOST_FRAMES:
            self.overlay.hide_skeleton(user_key)
            self.overlay.hide_track_box(user_key, hide_skeleton=True)
            state.reset_pose_gate()

    def _landmarks_to_viewport(self, user_key, landmarks_px, bbox):
        fh, fw = self._last_frame_shape[:2]

        vw = self.camera_view.viewport().width()
        vh = self.camera_view.viewport().height()

        if fw == 0 or fh == 0:
            return []

        sx = vw / fw
        sy = vh / fh

        x1_bbox, y1_bbox, x2_bbox, y2_bbox = bbox
        bbox_w = x2_bbox - x1_bbox
        bbox_h = y2_bbox - y1_bbox

        crop_w, crop_h = self._last_crop_size.get(user_key, (1, 1))

        result = []

        for lx, ly in landmarks_px:
            fx = x1_bbox + (lx / max(1, crop_w)) * bbox_w
            fy = y1_bbox + (ly / max(1, crop_h)) * bbox_h

            vx = vw - (fx * sx)
            vy = fy * sy

            result.append((vx, vy))

        return result

    def _landmarks_crop_to_frame(self, user_key, landmarks_px, bbox):
        """
        Convert landmark pixel from crop YOLO to full frame coordinates.
        Cuz Kinematic engine more stable using full frame landmarks,
        not crop-local landmarks.
        """
        x1, y1, x2, y2 = bbox
        bbox_w = max(1, x2 - x1)
        bbox_h = max(1, y2 - y1)

        crop_w, crop_h = self._last_crop_size.get(user_key, (1, 1))

        result = []

        for lx, ly in landmarks_px:
            fx = x1 + (float(lx) / max(1, crop_w)) * bbox_w
            fy = y1 + (float(ly) / max(1, crop_h)) * bbox_h
            result.append((fx, fy))

        return result

    def _crop_frame(self, frame, bbox, user_key) -> tuple | None:
        h, w = frame.shape[:2]

        x1, y1, x2, y2 = bbox

        current_label = self._current_exercise_label()

        if current_label == "sit_up":
            pad_x = int((x2 - x1) * 0.20)
            pad_y = int((y2 - y1) * 0.20)

        elif current_label == "knee_push_up":
            pad_x = int((x2 - x1) * 0.16)
            pad_y = int((y2 - y1) * 0.08)

        elif current_label == "mountain_climber":
            pad_x = int((x2 - x1) * 0.20)
            pad_y = int((y2 - y1) * 0.20)

        else:
            pad_x = int((x2 - x1) * 0.05)
            pad_y = int((y2 - y1) * 0.05)

        x1 = max(0, int(x1 - pad_x))
        y1 = max(0, int(y1 - pad_y))
        x2 = min(w, int(x2 + pad_x))
        y2 = min(h, int(y2 + pad_y))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            return None

        crop_bbox = (x1, y1, x2, y2)

        self._last_crop_size[user_key] = (crop.shape[1], crop.shape[0])

        return crop.copy(), crop_bbox

    def _is_geometry_strong(self, exercise: str, debug: dict) -> bool:
        """Strict fallback used only when LSTM status is UNKNOWN."""
        if not self.ENABLE_STRONG_GEOMETRY_FALLBACK:
            return False

        if exercise == "squat":
            return (
                float(debug.get("max_hip_drop_ratio", 0.0) or 0.0) >= 0.14
                and int(debug.get("cycle_frames", 0) or 0) >= 10
                and bool(debug.get("knee_depth_ok", False))
                and bool(debug.get("enough_samples", False))
            )

        if exercise == "jumping_jacks":
            return (
                float(debug.get("max_shoulder", 0.0) or 0.0) >= 145.0
                and float(debug.get("max_leg_ratio", 0.0) or 0.0) >= 1.20
                and int(debug.get("cycle_frames", 0) or 0) >= 6
            )

        if exercise == "knee_push_up":
            return (
                float(debug.get("min_elbow", 999.0) or 999.0) <= 110.0
                and int(debug.get("cycle_frames", 0) or 0) >= 8
                and int(debug.get("down_frames", 0) or 0) >= 2
                and bool(debug.get("elbow_depth_ok", False))
                and bool(debug.get("hip_alignment_ok", False))
            )

        if exercise == "sit_up":
            return (
                float(debug.get("max_torso_angle", 0.0) or 0.0) >= 55.0
                and int(debug.get("up_frames", 0) or 0) >= 2
                and bool(debug.get("torso_height_ok", False))
                and bool(debug.get("hip_flexion_ok", True))
            )

        if exercise == "mountain_climber":
            return (
                bool(debug.get("hip_drive_ok", False))
                and bool(debug.get("knee_drive_ok", False))
                and bool(debug.get("arm_support_ok", False))
                and int(debug.get("cycle_frames", 0) or 0) >= 10
                and int(debug.get("extend_frames", 0) or 0) >= 4
            )

        return False

    def _required_landmarks_for_exercise(self, exercise: str) -> list[int]:
        """
        Required landmarks for pose gate.
        Cannot be too strict since Mediapipe visibility is often flicker.
        """
        requirements = {
            "squat": [
                11, 12,  # shoulders
                23, 24,  # hips
                25, 26,  # knees
            ],
            "jumping_jacks": [
                11, 12,  # shoulders
                15, 16,  # wrists
                23, 24,  # hips
                25, 26,  # knees
                27, 28,  # ankles
            ],
            "knee_push_up": [
                11, 12,  # shoulders
                13, 14,  # elbows
                15, 16,  # wrists
                23, 24,  # hips
            ],
            "sit_up": [
                11, 12,  # shoulders
                23, 24,  # hips
            ],
            "mountain_climber": [
                11, 12,  # shoulders
                13, 14,  # elbows
                15, 16,  # wrists
                23, 24,  # hips
                25, 26,  # knees
            ],
        }

        return requirements.get(exercise, [])


    def _landmark_xyv(self, lm):
        """
        Get x, y, visibility from landmark.
        Support dict, object MediaPipe, or tuple/list sederhana.
        """
        if lm is None:
            return None

        if isinstance(lm, dict):
            try:
                x = float(lm.get("x", -999.0))
                y = float(lm.get("y", -999.0))
                visibility = float(lm.get("visibility", 0.0))
                return x, y, visibility
            except Exception:
                return None

        # Object format: lm.x, lm.y, lm.visibility
        try:
            x = float(getattr(lm, "x"))
            y = float(getattr(lm, "y"))
            visibility = float(getattr(lm, "visibility", 0.0))
            return x, y, visibility
        except Exception:
            pass

        # Tuple/list fallback
        try:
            x = float(lm[0])
            y = float(lm[1])
            visibility = float(lm[2]) if len(lm) > 2 else 1.0
            return x, y, visibility
        except Exception:
            return None

    def _landmark_is_visible(self, lm) -> bool:
        """
        Landmark is considered usable if:
        - coordinates still make sense in normalized crop
        - enough visibility
        """
        parsed = self._landmark_xyv(lm)

        if parsed is None:
            return False

        x, y, visibility = parsed
        margin = self.POSE_IN_FRAME_MARGIN

        in_frame = (
            -margin <= x <= 1.0 + margin
            and -margin <= y <= 1.0 + margin
        )

        if not in_frame:
            return False

        return visibility >= self.POSE_VISIBILITY_THRESHOLD

    def _landmark_chain_visible(self, landmarks, indices: list[int]) -> bool:
        if not landmarks:
            return False
        return all(
            idx < len(landmarks) and self._landmark_is_visible(landmarks[idx])
            for idx in indices
        )

    def _side_visibility_stats(self, landmarks, indices: list[int]) -> dict:
        """
        Calculate how great one side of the body is seen.
        Used for side-view movement like knee push up.
        """
        if not landmarks:
            return {
                "visible_count": 0,
                "total": len(indices),
                "ratio": 0.0,
                "avg_visibility": 0.0,
            }

        visible_count = 0
        visibility_sum = 0.0
        total = len(indices)

        for idx in indices:
            if idx >= len(landmarks):
                continue

            lm = landmarks[idx]
            parsed = self._landmark_xyv(lm)

            if parsed is not None:
                _, _, visibility = parsed
                visibility_sum += max(0.0, min(1.0, visibility))

            if self._landmark_is_visible(lm):
                visible_count += 1

        return {
            "visible_count": visible_count,
            "total": total,
            "ratio": visible_count / max(1, total),
            "avg_visibility": visibility_sum / max(1, total),
        }

    def _select_knee_push_up_visible_side(self, pose_result: dict):
        """
        For knee push up side-view.
        Choose body side that is most often seen.
        """
        if not pose_result:
            return None, {}

        landmarks = pose_result.get("landmarks") or []

        if not landmarks:
            return None, {}

        left_core = [11, 13, 15, 23]   # left shoulder, elbow, wrist, hip
        right_core = [12, 14, 16, 24]  # right shoulder, elbow, wrist, hip

        left_full = [11, 13, 15, 23, 25]    # + left knee
        right_full = [12, 14, 16, 24, 26]   # + right knee

        left_core_stats = self._side_visibility_stats(landmarks, left_core)
        right_core_stats = self._side_visibility_stats(landmarks, right_core)

        left_full_stats = self._side_visibility_stats(landmarks, left_full)
        right_full_stats = self._side_visibility_stats(landmarks, right_full)

        left_score = (
            left_core_stats["visible_count"] * 10
            + left_full_stats["visible_count"] * 2
            + left_core_stats["avg_visibility"]
        )

        right_score = (
            right_core_stats["visible_count"] * 10
            + right_full_stats["visible_count"] * 2
            + right_core_stats["avg_visibility"]
        )

        if left_score >= right_score:
            return "left", {
                "core": left_core_stats,
                "full": left_full_stats,
                "score": left_score,
            }

        return "right", {
            "core": right_core_stats,
            "full": right_full_stats,
            "score": right_score,
        }

    def _knee_push_up_pose_quality_ok(self, pose_result: dict) -> bool:
        """Require one reliable side for both elbow and hip angle chains."""
        side, _ = self._select_knee_push_up_visible_side(pose_result)
        if side not in ("left", "right"):
            return False
        landmarks = pose_result.get("landmarks") or []
        index = {
            "left": {"shoulder": 11, "elbow": 13, "wrist": 15, "hip": 23, "knee": 25},
            "right": {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24, "knee": 26},
        }[side]
        elbow_chain = [index["shoulder"], index["elbow"], index["wrist"]]
        hip_chain = [index["shoulder"], index["hip"], index["knee"]]
        return (
            self._landmark_chain_visible(landmarks, elbow_chain)
            and self._landmark_chain_visible(landmarks, hip_chain)
        )
    
    def _sit_up_pose_quality_ok(self, pose_result: dict) -> bool:
        if not pose_result:
            return False
        landmarks = pose_result.get("landmarks") or []
        if not landmarks:
            return False

        torso_visible = all(
            idx < len(landmarks) and self._landmark_is_visible(landmarks[idx])
            for idx in (11, 12, 23, 24)
        )
        left_hip_chain = self._landmark_chain_visible(landmarks, [11, 23, 25])
        right_hip_chain = self._landmark_chain_visible(landmarks, [12, 24, 26])
        return torso_visible and (left_hip_chain or right_hip_chain)

    def _mountain_climber_pose_quality_ok(self, pose_result: dict) -> bool:
        """Require at least one usable upper-body and leg chain."""
        if not pose_result:
            return False
        landmarks = pose_result.get("landmarks") or []
        if not landmarks:
            return False

        sides = {
            "left": {
                "upper": [11, 13, 15],
                "hip": [11, 23, 25],
                "knee": [23, 25, 27],
            },
            "right": {
                "upper": [12, 14, 16],
                "hip": [12, 24, 26],
                "knee": [24, 26, 28],
            },
        }
        return any(
            self._landmark_chain_visible(landmarks, spec["upper"])
            and self._landmark_chain_visible(landmarks, spec["hip"])
            and self._landmark_chain_visible(landmarks, spec["knee"])
            for spec in sides.values()
        )

    def _angles_for_engine(self, exercise: str, pose_result: dict) -> dict:
        """Return only joint angles whose complete landmark chain is visible."""
        angles = dict((pose_result or {}).get("angles") or {})
        landmarks = (pose_result or {}).get("landmarks") or []

        if exercise == "knee_push_up":
            side, stats = self._select_knee_push_up_visible_side(pose_result)
            if side not in ("left", "right"):
                return angles

            idx = {
                "left": {"shoulder": 11, "elbow": 13, "wrist": 15, "hip": 23, "knee": 25},
                "right": {"shoulder": 12, "elbow": 14, "wrist": 16, "hip": 24, "knee": 26},
            }[side]
            elbow_ok = self._landmark_chain_visible(
                landmarks,
                [idx["shoulder"], idx["elbow"], idx["wrist"]],
            )
            hip_ok = self._landmark_chain_visible(
                landmarks,
                [idx["shoulder"], idx["hip"], idx["knee"]],
            )
            if not (elbow_ok and hip_ok):
                for joint in ("elbow", "hip", "knee"):
                    angles[f"left_{joint}"] = None
                    angles[f"right_{joint}"] = None
                return angles

            for joint in ("shoulder", "elbow", "hip", "knee"):
                src_key = f"{side}_{joint}"
                if src_key in angles and angles[src_key] is not None:
                    angles[f"left_{joint}"] = angles[src_key]
                    angles[f"right_{joint}"] = angles[src_key]
            angles["_selected_side"] = side
            angles["_selected_side_score"] = stats.get("score", 0.0)
            return angles

        if exercise == "sit_up":
            left_ok = self._landmark_chain_visible(landmarks, [11, 23, 25])
            right_ok = self._landmark_chain_visible(landmarks, [12, 24, 26])
            if not left_ok:
                angles["left_hip"] = None
            if not right_ok:
                angles["right_hip"] = None
            return angles

        if exercise == "mountain_climber":
            sides = {
                "left": {
                    "elbow": [11, 13, 15],
                    "hip": [11, 23, 25],
                    "knee": [23, 25, 27],
                },
                "right": {
                    "elbow": [12, 14, 16],
                    "hip": [12, 24, 26],
                    "knee": [24, 26, 28],
                },
            }
            for side, chains in sides.items():
                for joint, chain in chains.items():
                    if not self._landmark_chain_visible(landmarks, chain):
                        angles[f"{side}_{joint}"] = None
                visible_joints = sum(
                    1 for chain in chains.values()
                    if self._landmark_chain_visible(landmarks, chain)
                )
                angles[f"_{side}_side_visibility_ratio"] = visible_joints / len(chains)
            return angles

        return angles
    
    def _knee_push_up_start_pose_ok(self, angles: dict) -> bool:
        if not angles:
            return False

        elbow = self._avg_angle_from_dict(
            angles,
            "left_elbow",
            "right_elbow",
        )

        hip = self._avg_angle_from_dict(
            angles,
            "left_hip",
            "right_hip",
        )

        if elbow is None or hip is None:
            return False

        elbow_ok = elbow >= 135.0
        hip_ok = hip >= 125.0

        return elbow_ok and hip_ok


    def _avg_angle_from_dict(self, angles: dict, left_key: str, right_key: str):
        values = []

        for key in (left_key, right_key):
            value = angles.get(key)

            if value is None:
                continue

            try:
                values.append(float(value))
            except Exception:
                pass

        if not values:
            return None

        return sum(values) / len(values)
    
    def _pose_quality_ok(self, pose_result: dict, exercise: str) -> bool:
        """
        True if relevant landmark is seen enough.
        """
        if not pose_result:
            return False

        if exercise == "knee_push_up":
            return self._knee_push_up_pose_quality_ok(pose_result)
        
        if exercise == "mountain_climber":
            return self._mountain_climber_pose_quality_ok(pose_result)
        if exercise == "sit_up":
            return self._sit_up_pose_quality_ok(pose_result)

        landmarks = pose_result.get("landmarks") or []
        required = self._required_landmarks_for_exercise(exercise)

        if not required or not landmarks:
            return False

        visible_count = 0

        for idx in required:
            if idx >= len(landmarks):
                continue

            if self._landmark_is_visible(landmarks[idx]):
                visible_count += 1

        ratio = visible_count / max(1, len(required))

        if self.POSE_REQUIRE_ALL_LANDMARKS:
            return visible_count == len(required)

        return ratio >= self.POSE_QUALITY_MIN_RATIO


    def _update_pose_gate(self, user_key: str, pose_result: dict, exercise: str) -> bool:
        """
        Stabilizer for full-body / pose visibility.

        - need multiple good frames to be ON.
        - need multiple bad frames to be OFF.
        """
        state = self.user_states[user_key]

        quality_ok = self._pose_quality_ok(
            pose_result=pose_result,
            exercise=exercise,
        )

        if quality_ok:
            state.pose_quality_counter += 1
            state.pose_lost_counter = 0

            if state.pose_quality_counter >= self.POSE_READY_STABLE_FRAMES:
                state.pose_ready = True

        else:
            state.pose_quality_counter = 0

            if state.pose_ready:
                state.pose_lost_counter += 1

                if state.pose_lost_counter >= self.POSE_LOST_FRAMES:
                    state.pose_ready = False
            else:
                state.pose_lost_counter = 0

        return state.pose_ready

    def _workout_name_to_label(self, name: str) -> str:
        return {
            "Jumping Jacks": "jumping_jacks",
            "Mountain Climber": "mountain_climber",
            "Squat": "squat",
            "Knee Push Up": "knee_push_up",
            "Sit Up": "sit_up",
        }.get(name, "")

    def _save_runtime_reps_to_session(self):
        """
        Persist current exercise counters inside the session object.
        This makes pause/resume robust even if labels/runtime state are reset.
        """
        if self.session is None:
            return

        if not hasattr(self.session, "runtime_reps"):
            self.session.runtime_reps = {}

        exercise_index = int(getattr(self.session, "current_index", 0) or 0)

        self.session.runtime_reps[exercise_index] = {
            "user1": {
                "valid_reps": int(self.user_states["user1"].valid_reps),
                "total_reps": int(self.user_states["user1"].total_reps),
                "last_feedback": self.user_states["user1"].last_feedback,
                "finished": bool(self.user_states["user1"].finished),
            },
            "user2": {
                "valid_reps": int(self.user_states["user2"].valid_reps),
                "total_reps": int(self.user_states["user2"].total_reps),
                "last_feedback": self.user_states["user2"].last_feedback,
                "finished": bool(self.user_states["user2"].finished),
            },
        }

        """print(
            f"[PAUSE_SAVE] exercise_index={exercise_index} "
            f"data={self.session.runtime_reps[exercise_index]}"
        )"""

    def _restore_runtime_reps_from_session(self):
        """
        Restore current exercise counters after resume.
        Must be called after load_session(), because setup_labels() resets UI text.
        """
        if self.session is None:
            return

        if not hasattr(self.session, "runtime_reps"):
            return

        exercise_index = int(getattr(self.session, "current_index", 0) or 0)
        saved = self.session.runtime_reps.get(exercise_index)

        if not saved:
            return

        for user_key in self._active_user_keys():
            if user_key not in saved:
                continue

            state = self.user_states[user_key]
            state.valid_reps = int(saved[user_key].get("valid_reps", 0) or 0)
            state.total_reps = int(saved[user_key].get("total_reps", 0) or 0)
            state.last_feedback = saved[user_key].get("last_feedback", "") or ""
            state.finished = bool(saved[user_key].get("finished", False))

        """print(
            f"[RESUME_RESTORE] exercise_index={exercise_index} "
            f"data={saved}"
        )"""

    def reset_runtime_for_resume(self):
        """
        Reset tracking/inference state after pause-resume,
        but preserve completed repetition counters.
        """
        for user_key, state in self.user_states.items():
            valid_reps = state.valid_reps
            total_reps = state.total_reps
            last_feedback = state.last_feedback
            finished = state.finished

            state.track_id = None
            state.registered = False
            state.track_box_ready = False
            state.guidebox_candidate_track_id = None
            state.guidebox_counter = 0
            state.last_bbox = None
            state.tracking_roi = None
            state.display_bbox = None
            state.initial_center_x = None
            state.identity_side = None
            state.pose_bbox = None
            state.lost_detection_counter = 0
            state.recovery_pending = False
            state.recovery_cooldown = 0
            state.exercise_start_pose_ready = False

            state.current_class = None
            state.class_confidence = 0.0
            state.class_history.clear()
            state.class_ttl = 0
            state.class_status = "UNKNOWN"

            state.reset_pose_gate()

            state.cycle_phase = "IDLE"

            state.valid_reps = valid_reps
            state.total_reps = total_reps
            state.last_feedback = last_feedback
            state.finished = finished

            try:
                self.overlay.hide_skeleton(user_key)
            except Exception:
                pass

        self.rep_engine.reset_all()
        self.overlay.hide_track_boxes()
        self._identity_boundary_x = None
        self._pose_reset_pending = True
    
    def _flash_rep_feedback(self, user_key: str, status: str):
        """
        Trigger visual + audio feedback.
        status: valid / wrong / finished
        """
        try:
            if self.DEBUG_VERBOSE:
                print(f"[VISUAL_FLASH] {user_key} status={status}")

            if hasattr(self, "audio_feedback"):
                self.audio_feedback.play(
                    status=status,
                    mode=self.tracking_mode or "single",
                    user_key=user_key,
                )

            if hasattr(self.overlay, "flash_track_box"):
                self.overlay.flash_track_box(user_key, status)
                #print(f"[FLASH_FEEDBACK] user={user_key} status={status}")

        except Exception as e:
            print(f"[FEEDBACK_WARN] {user_key} {status}: {e}")

    # performance test helpers
    def _schedule_performance_test(self):
        if not self.PERF_TEST_ENABLED:
            return

        if self.performance_logger.running:
            return

        if self._perf_warmup_scheduled:
            return

        if getattr(self.session, "current_index", 0) != 0:
            return

        self._perf_warmup_scheduled = True

        print(
            "[PERF_WARMUP]",
            f"Logging started in {self.PERF_WARMUP_SECONDS} seconds.",
            "Stand still until beep sound is heard.",
        )

        QTimer.singleShot(
            self.PERF_WARMUP_SECONDS * 1000,
            self._start_performance_test,
        )


    def _start_performance_test(self):
        self._perf_warmup_scheduled = False

        if not self.PERF_TEST_ENABLED:
            return

        if self.session is None or not self.yolo_active:
            return

        if getattr(self.session, "current_index", 0) != 0:
            return

        self.performance_logger.start(
            mode=self.tracking_mode,
            metadata={
                "exercise_count": len(
                    getattr(self.session, "workouts", []) or []
                ),
                "camera_resolution": self.current_cam_resolution,
                "warmup_seconds": self.PERF_WARMUP_SECONDS,
            },
        )
        self.performance_logger.resume()

        # QApplication is created only once in main.py. instance() retrieves
        # that existing application; no second QApplication is constructed.
        app = QApplication.instance()
        if app is not None:
            app.beep()

        print(
            "[PERF_LOGGING_ACTIVE]",
            "Performance test has begun. You can start the workout.",
        )

    def _is_rep_start_transition(
        self,
        exercise: str,
        previous_phase: str,
        current_phase: str,
    ) -> bool:
        transitions = {
            "squat": ("STAND", "DESCEND"),
            "jumping_jacks": ("CLOSED", "OPEN"),
            "knee_push_up": ("UP", "DESCEND"),
            "sit_up": ("DOWN", "ASCEND"),
            "mountain_climber": ("EXTENDED", "DRIVE"),
        }

        expected = transitions.get(exercise)
        return expected == (previous_phase, current_phase)
    
    def _start_rep_classification_capture(self, user_key: str):
        if not self.CLASSIFICATION_TEST_LOG_ENABLED:
            return

        state = self.user_states[user_key]

        state.rep_class_active = True
        state.rep_class_started_at = perf_counter()
        state.rep_stable_prediction = None
        state.rep_stable_confidence = 0.0
        state.rep_stable_elapsed_s = None
    
    def _capture_rep_stable_prediction(
        self,
        user_key: str,
        prediction: str | None,
        confidence: float,
    ):
        state = self.user_states[user_key]

        if not self.CLASSIFICATION_TEST_LOG_ENABLED:
            return

        if not state.rep_class_active:
            return

        if state.rep_stable_prediction is not None:
            return

        if prediction is None:
            return

        state.rep_stable_prediction = prediction
        state.rep_stable_confidence = float(confidence)

        if state.rep_class_started_at is not None:
            state.rep_stable_elapsed_s = (
                perf_counter() - state.rep_class_started_at
            )

    def _finish_rep_classification_capture(
        self,
        user_key: str,
        ground_truth: str,
    ):
        state = self.user_states[user_key]

        if not self.CLASSIFICATION_TEST_LOG_ENABLED:
            return

        state.classification_trial_no += 1

        prediction = state.rep_stable_prediction
        confidence = state.rep_stable_confidence
        elapsed = state.rep_stable_elapsed_s

        # Fallback apabila transisi awal repetisi tidak sempat tertangkap.
        if prediction is None and state.current_class is not None:
            prediction = state.current_class
            confidence = state.class_confidence

        result_text = (
            "BENAR"
            if prediction == ground_truth
            else "SALAH"
        )

        prediction_text = prediction or "UNKNOWN"
        elapsed_text = (
            f"{elapsed:.3f}"
            if elapsed is not None
            else "NA"
        )

        print(
            "[LSTM_REP_RESULT]",
            f"mode={self.tracking_mode}",
            f"trial={state.classification_trial_no}",
            f"user={user_key}",
            f"ground_truth={ground_truth}",
            f"prediction={prediction_text}",
            f"confidence={confidence:.4f}",
            f"time_to_stable_s={elapsed_text}",
            f"result={result_text}",
        )

        state.rep_class_active = False
        state.rep_class_started_at = None
        state.rep_stable_prediction = None
        state.rep_stable_confidence = 0.0
        state.rep_stable_elapsed_s = None

def bbox_overlaps_guidebox(
    bbox,
    guidebox,
    frame_w,
    frame_h,
    viewport_w,
    viewport_h,
    threshold=0.5,
    mirrored=True,
):
    if frame_w == 0 or frame_h == 0:
        return False

    if viewport_w == 0 or viewport_h == 0:
        return False

    x1, y1, x2, y2 = bbox

    sx = viewport_w / frame_w
    sy = viewport_h / frame_h

    if mirrored:
        x1_vp = viewport_w - (x2 * sx)
        x2_vp = viewport_w - (x1 * sx)
    else:
        x1_vp = x1 * sx
        x2_vp = x2 * sx

    y1_vp = y1 * sy
    y2_vp = y2 * sy

    gx1 = guidebox.x()
    gy1 = guidebox.y()
    gx2 = gx1 + guidebox.width()
    gy2 = gy1 + guidebox.height()

    ix1 = max(x1_vp, gx1)
    iy1 = max(y1_vp, gy1)
    ix2 = min(x2_vp, gx2)
    iy2 = min(y2_vp, gy2)

    if ix2 <= ix1 or iy2 <= iy1:
        return False

    inter = (ix2 - ix1) * (iy2 - iy1)
    area = max(1, (x2_vp - x1_vp) * (y2_vp - y1_vp))

    ratio = inter / area

    return ratio >= threshold


def find_matching_track_id(detect_bbox, tracks, threshold=0.4):
    best = None
    best_iou = 0

    for person in tracks:
        iou = calculate_iou(detect_bbox, person["bbox"])

        if iou > best_iou:
            best_iou = iou
            best = person["track_id"]

    return best if best_iou >= threshold else None


def calculate_iou(box1, box2):
    x1, y1, x2, y2 = box1
    xx1, yy1, xx2, yy2 = box2

    ix1 = max(x1, xx1)
    iy1 = max(y1, yy1)
    ix2 = min(x2, xx2)
    iy2 = min(y2, yy2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0

    inter = (ix2 - ix1) * (iy2 - iy1)

    area1 = (x2 - x1) * (y2 - y1)
    area2 = (xx2 - xx1) * (yy2 - yy1)

    denom = area1 + area2 - inter

    if denom <= 0:
        return 0

    return inter / denom
