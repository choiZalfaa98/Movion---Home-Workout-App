import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from pathlib import Path

"""
Mediapipe Pose (BlazePose) Relevant Landmark Keypoints
"""
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28


BASE_DIR = Path(__file__).resolve().parent.parent.parent

class PoseExtractor:
    """
    Synchronous MediaPipe PoseLandmarker wrapper.

    Running mode:
        VIDEO

        Reason(s):
        This app processes one stable workspace ROI per user.
        Synchronous detect_for_video() preserves per-user temporal state and
        avoids cross-user result mismatch.

    Output per frame:
        {
            "landmarks":    list[dict]    --> 33 normalized landmarks
            "landmarks_px": list[tuple]   --> 33 pixel landmarks in crop
            "features":     np.ndarray    --> (217,) Attention LSTM input
            "angles":       dict          --> degree angles for rule-based engine
        }

    Feature breakdown (217):
        norm xyz          : 33 Ã— 3 = 99
        joint angles      : 6
        velocity xyz      : 33 Ã— 3 = 99
        foot asymmetry    : 3
        hip vertical vel  : 1
        torso orientation : 9
    """

    def __init__(
        self,
        model_path: str = None,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        if model_path is None:
            model_path = str(BASE_DIR / "models" / "pose_landmarker_full.task")

        self._frame_ts = 0

        self._prev_landmarks = None
        self._prev_hip_center_y = None

        options = vision.PoseLandmarkerOptions(
            base_options=python.BaseOptions(
                model_asset_path=model_path,
                delegate=python.BaseOptions.Delegate.CPU,
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )

        self.landmarker = vision.PoseLandmarker.create_from_options(options)

        #print("[PoseExtractor] Initialized (VIDEO, CPU)")

    def process(
        self,
        frame_rgb: np.ndarray,
        timestamp_ms: int | None = None,
    ) -> dict | None:
        """
        Process one RGB person-crop.
        """
        if frame_rgb is None:
            return None

        if frame_rgb.size == 0:
            return None

        if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return None

        frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)

        if timestamp_ms is None:
            next_ts = self._frame_ts + 33
        else:
            next_ts = max(self._frame_ts + 1, int(timestamp_ms))

        self._frame_ts = next_ts

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame_rgb,
        )

        result = self.landmarker.detect_for_video(
            mp_image,
            self._frame_ts,
        )

        if result is None:
            return None

        if not result.pose_landmarks:
            return None

        landmarks = result.pose_landmarks[0]

        return self._parse(
            landmarks=landmarks,
            frame_shape=frame_rgb.shape,
        )

    def reset(self):
        """
        Reset temporal feature state.
        """
        self._prev_landmarks = None
        self._prev_hip_center_y = None

    def close(self):
        self.landmarker.close()
        #print("[PoseExtractor] Closed")

    def _parse(self, landmarks, frame_shape: tuple) -> dict:
        h, w = frame_shape[:2]

        lm_list = []
        lm_px = []

        for lm in landmarks:
            lm_list.append(
                {
                    "x": float(lm.x),
                    "y": float(lm.y),
                    "z": float(lm.z),
                    "visibility": float(lm.visibility),
                }
            )

            lm_px.append(
                (
                    int(lm.x * w),
                    int(lm.y * h),
                )
            )

        raw = np.array(
            [
                [lm["x"], lm["y"], lm["z"]]
                for lm in lm_list
            ],
            dtype=np.float32,
        )

        features, angles_dict = self._extract_features(raw)

        return {
            "landmarks": lm_list,
            "landmarks_px": lm_px,
            "features": features,
            "angles": angles_dict,
        }

    def _extract_features(self, raw: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Feature order matching Attention LSTM training preprocessing:
        [norm.flatten | angles_rad | vel.flatten | foot_asym | hip_vel_y | torso]
        """

        # Pose normalization
        norm = self._normalize_pose(raw)

        # Velocity
        if self._prev_landmarks is None:
            vel = np.zeros_like(norm)
        else:
            vel = norm - self._prev_landmarks

        self._prev_landmarks = norm.copy()

        # Joint angles for LSTM features, in radians
        left_elbow = self._angle(norm[LEFT_SHOULDER], norm[LEFT_ELBOW], norm[LEFT_WRIST])
        right_elbow = self._angle(norm[RIGHT_SHOULDER], norm[RIGHT_ELBOW], norm[RIGHT_WRIST])

        left_knee = self._angle(norm[LEFT_HIP], norm[LEFT_KNEE], norm[LEFT_ANKLE])
        right_knee = self._angle(norm[RIGHT_HIP], norm[RIGHT_KNEE], norm[RIGHT_ANKLE])

        left_hip = self._angle(norm[LEFT_SHOULDER], norm[LEFT_HIP], norm[LEFT_KNEE])
        right_hip = self._angle(norm[RIGHT_SHOULDER], norm[RIGHT_HIP], norm[RIGHT_KNEE])

        angles_rad = np.array(
            [
                left_elbow,
                right_elbow,
                left_knee,
                right_knee,
                left_hip,
                right_hip,
            ],
            dtype=np.float32,
        )

        # Foot asymmetry
        foot_asym = vel[LEFT_ANKLE] - vel[RIGHT_ANKLE]

        # Hip vertical velocity
        hip_center_y = float((norm[LEFT_HIP, 1] + norm[RIGHT_HIP, 1]) / 2.0)

        if self._prev_hip_center_y is None:
            hip_vel_y = 0.0
        else:
            hip_vel_y = hip_center_y - self._prev_hip_center_y

        self._prev_hip_center_y = hip_center_y

        # Torso orientation
        shoulder_vec = norm[RIGHT_SHOULDER] - norm[LEFT_SHOULDER]
        hip_vec = norm[RIGHT_HIP] - norm[LEFT_HIP]

        shoulder_mid = (norm[LEFT_SHOULDER] + norm[RIGHT_SHOULDER]) / 2.0
        hip_mid = (norm[LEFT_HIP] + norm[RIGHT_HIP]) / 2.0

        torso_vec = shoulder_mid - hip_mid

        torso = np.concatenate(
            [
                shoulder_vec,
                hip_vec,
                torso_vec,
            ]
        )

        # Final 217 features
        features = np.concatenate(
            [
                norm.flatten(),
                angles_rad,
                vel.flatten(),
                foot_asym,
                [hip_vel_y],
                torso,
            ]
        ).astype(np.float32)

        if len(features) != 217:
            raise ValueError(f"Feature mismatch: expected 217, got {len(features)}")

        # Angles for posture/rule-based layer in degrees.
        left_shoulder = self._angle(
            norm[LEFT_ELBOW],
            norm[LEFT_SHOULDER],
            norm[LEFT_HIP],
        )
        right_shoulder = self._angle(
            norm[RIGHT_ELBOW],
            norm[RIGHT_SHOULDER],
            norm[RIGHT_HIP],
        )

        back_angle = self._calculate_back_angle(torso_vec)

        angles_dict = {
            "left_elbow": float(np.degrees(left_elbow)),
            "right_elbow": float(np.degrees(right_elbow)),
            "left_knee": float(np.degrees(left_knee)),
            "right_knee": float(np.degrees(right_knee)),
            "left_hip": float(np.degrees(left_hip)),
            "right_hip": float(np.degrees(right_hip)),
            "left_shoulder": float(np.degrees(left_shoulder)),
            "right_shoulder": float(np.degrees(right_shoulder)),
            "back": float(back_angle),
        }

        return features, angles_dict

    @staticmethod
    def _normalize_pose(landmarks: np.ndarray) -> np.ndarray:
        """
        Normalize pose using left hip as origin and shoulder width as scale.
        Matching with LSTM jupyter notebook preprocessing.
        """
        norm = landmarks.copy()

        center = norm[LEFT_HIP:LEFT_HIP + 1, :]
        norm = norm - center

        shoulder_dist = np.linalg.norm(
            norm[LEFT_SHOULDER] - norm[RIGHT_SHOULDER]
        )

        if shoulder_dist <= 1e-6:
            shoulder_dist = 1.0

        norm = norm / shoulder_dist

        return norm.astype(np.float32)

    @staticmethod
    def _angle(A: np.ndarray, B: np.ndarray, C: np.ndarray) -> float:
        """
        Calculate angle at point B between BA and BC.
        Returns radians.
        """
        ba = A - B
        bc = C - B

        denom = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6

        cosine = np.dot(ba, bc) / denom

        return float(np.arccos(np.clip(cosine, -1.0, 1.0)))

    @staticmethod
    def _calculate_back_angle(torso_vec: np.ndarray) -> float:
        """
        Torso angle against vertical axis.
        """
        vertical = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        denom = (
            np.linalg.norm(torso_vec) *
            np.linalg.norm(vertical) +
            1e-6
        )

        cosine = np.dot(torso_vec, vertical) / denom

        return float(
            np.degrees(
                np.arccos(
                    np.clip(cosine, -1.0, 1.0)
                )
            )
        )
