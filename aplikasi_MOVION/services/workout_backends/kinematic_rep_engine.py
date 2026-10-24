from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math

@dataclass
class RepCycleResult:
    phase: str
    rep_completed: bool = False
    valid_rep: bool = False
    feedback: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UserExerciseState:
    exercise: Optional[str] = None
    phase: str = "IDLE"
    frame_index: int = 0
    cooldown: int = 0
    invalid_current_rep: bool = False
    feedback_current_rep: str = ""

    prev_main_value: Optional[float] = None

    # Squat
    min_knee_angle: float = 999.0
    min_hip_angle: float = 999.0
    reached_bottom: bool = False
    squat_knee_samples: List[float] = field(default_factory=list)
    squat_hip_samples: List[float] = field(default_factory=list)
    squat_cycle_frames: int = 0
    squat_bottom_frames: int = 0
    squat_descent_candidate_frames: int = 0
    squat_entry_knee: float = 999.0
    squat_stand_reference_knee: float = 999.0
    squat_stand_stable_frames: int = 0
    squat_descent_candidate_low_entry: bool = False
    squat_started_from_low_entry: bool = False
    movement_context_seen: bool = False

    # Squat vertical-motion guard
    squat_stand_hip_y: Optional[float] = None
    squat_hip_y_samples: List[float] = field(default_factory=list)
    squat_body_scale_samples: List[float] = field(default_factory=list)

    # Knee push-up
    min_elbow_angle: float = 999.0
    reached_down: bool = False

    # Knee push-up stability and posture validation
    pushup_cycle_frames: int = 0
    pushup_down_frames: int = 0
    pushup_descent_candidate_frames: int = 0
    min_pushup_hip_angle: float = 999.0
    max_pushup_hip_angle: float = 0.0
    pushup_hip_samples: List[float] = field(default_factory=list)

    # Jumping jack
    reached_open: bool = False
    max_shoulder_angle: float = 0.0
    max_leg_ratio: float = 0.0
    jack_cycle_frames: int = 0
    jack_open_candidate_frames: int = 0
    jack_close_candidate_frames: int = 0

    # Sit-up
    reached_up: bool = False
    max_torso_angle: float = 0.0

    # Sit-up stability and posture validation
    situp_cycle_frames: int = 0
    situp_up_frames: int = 0
    situp_down_frames: int = 0
    situp_ascend_candidate_frames: int = 0
    min_situp_hip_angle: float = 999.0
    situp_hip_samples: List[float] = field(default_factory=list)

    # Mountain climber: side-locked phase state and calibrated plank baseline
    last_mountain_side: Optional[str] = None
    mountain_candidate_side: Optional[str] = None
    mountain_active_side: Optional[str] = None
    mountain_start_frames: int = 0
    mountain_cycle_frames: int = 0
    mountain_drive_frames: int = 0
    mountain_extend_frames: int = 0
    mountain_missing_active_side_frames: int = 0
    min_mountain_hip_angle: float = 999.0
    min_mountain_knee_angle: float = 999.0
    min_mountain_elbow_angle: float = 999.0
    mountain_active_baseline_hip: Optional[float] = None
    mountain_active_baseline_knee: Optional[float] = None
    mountain_left_baseline_hip: Optional[float] = None
    mountain_left_baseline_knee: Optional[float] = None
    mountain_right_baseline_hip: Optional[float] = None
    mountain_right_baseline_knee: Optional[float] = None


class KinematicRepEngine:
    """
    Rule-based kinematic repetition engine.
    For movement phase detection, cycle completion, and valid reps logic

    Single source of truth:
    The phase thresholds and valid-posture thresholds must not contradict each other.
    For real-time webcam testing, estimation is noisy under laptop-camera perspective and cropped-person ROI.
    """

    # Squat thresholds cycle rep
    SQUAT_STAND_ANGLE = 145.0
    SQUAT_DESCEND_START_ANGLE = 142.0
    SQUAT_VALID_DEPTH_ANGLE = 125.0
    SQUAT_BOTTOM_PHASE_ANGLE = 125.0
    SQUAT_TOO_DEEP_ANGLE = 45.0

    # Anti-false-positive constraints for webcam real-time use
    SQUAT_DESCEND_CONFIRM_FRAMES = 4
    SQUAT_MIN_CYCLE_FRAMES = 10
    SQUAT_MIN_KNEE_SAMPLES = 8
    SQUAT_MIN_DEPTH_DROP = 25.0
    SQUAT_DESCEND_ENTRY_MIN_ANGLE = 95.0
    SQUAT_LOW_ENTRY_MIN_BOTTOM_FRAMES = 3
    SQUAT_MIN_HIP_DROP_RATIO = 0.12

    # Squat posture validation
    SQUAT_VALID_HIP_FLEXION_ANGLE = 145.0
    SQUAT_KNEE_DOMINANT_KNEE_ANGLE = 115.0
    SQUAT_KNEE_DOMINANT_HIP_ANGLE = 145.0
    SQUAT_STRONG_HIP_DROP_RATIO = 0.16

    # count a squat when the user has clearly started ascending after a valid hip drop
    SQUAT_ASCEND_COUNT_RATIO = 0.72
    SQUAT_RECOVER_RETURN_RATIO = 0.10

    # Jumping-jack phase thresholds are intentionally looser than posture
    # thresholds, so a partial cycle can complete as an invalid repetition.
    JACK_PHASE_OPEN_SHOULDER = 115.0
    JACK_PHASE_OPEN_LEG_RATIO = 1.02
    JACK_VALID_OPEN_SHOULDER = 135.0
    JACK_VALID_OPEN_LEG_RATIO = 1.15
    JACK_CLOSED_SHOULDER = 95.0
    JACK_CLOSED_LEG_RATIO = 0.95
    JACK_OPEN_CONFIRM_FRAMES = 2
    JACK_CLOSE_CONFIRM_FRAMES = 2
    JACK_MIN_CYCLE_FRAMES = 6

    # Knee push-up thresholds
    PUSHUP_UP_ELBOW_ANGLE = 140.0
    PUSHUP_DESCEND_START_ELBOW = 125.0
    PUSHUP_DOWN_ELBOW_ANGLE = 115.0
    PUSHUP_ASCEND_START_ELBOW = 122.0
    PUSHUP_COMPLETE_ELBOW_ANGLE = 138.0
    PUSHUP_READY_HIP_ANGLE = 125.0
    PUSHUP_MIN_HIP_ALIGNMENT_ANGLE = 125.0
    PUSHUP_MAX_CYCLE_FRAMES = 55
    PUSHUP_DESCEND_CONFIRM_FRAMES = 2
    PUSHUP_MIN_CYCLE_FRAMES = 7
    PUSHUP_MIN_DOWN_FRAMES = 2
    PUSHUP_MIN_HIP_SAMPLES = 3

    # Sit-up thresholds
    SITUP_DOWN_TORSO_ANGLE = 30.0
    SITUP_ASCEND_START_TORSO_ANGLE = 35.0
    SITUP_UP_TORSO_ANGLE = 50.0
    SITUP_DESCEND_START_TORSO_ANGLE = 40.0
    SITUP_VALID_HIP_FLEXION_ANGLE = 150.0
    SITUP_ASCEND_CONFIRM_FRAMES = 2
    SITUP_MIN_CYCLE_FRAMES = 8
    SITUP_MIN_UP_FRAMES = 2
    SITUP_MIN_DOWN_FRAMES = 2
    SITUP_MIN_HIP_SAMPLES = 3

    # Mountain climber. Phase entry is looser than validity, and all phase
    # transitions are locked to the same leg to survive occlusion/jitter.
    MOUNTAIN_READY_HIP_ANGLE = 115.0
    MOUNTAIN_READY_KNEE_ANGLE = 135.0
    MOUNTAIN_PHASE_DRIVE_HIP_ANGLE = 135.0
    MOUNTAIN_PHASE_DRIVE_KNEE_ANGLE = 155.0
    MOUNTAIN_VALID_DRIVE_HIP_ANGLE = 125.0
    MOUNTAIN_VALID_DRIVE_KNEE_ANGLE = 145.0
    MOUNTAIN_EXTENDED_HIP_ANGLE = 130.0
    MOUNTAIN_EXTENDED_KNEE_ANGLE = 150.0
    MOUNTAIN_ARM_SUPPORT_ELBOW = 105.0
    MOUNTAIN_MIN_HIP_DROP = 12.0
    MOUNTAIN_MIN_KNEE_DROP = 18.0
    MOUNTAIN_VALID_HIP_DROP = 18.0
    MOUNTAIN_VALID_KNEE_DROP = 25.0
    MOUNTAIN_START_CONFIRM_FRAMES = 4
    MOUNTAIN_DRIVE_CONFIRM_FRAMES = 4
    MOUNTAIN_EXTEND_CONFIRM_FRAMES = 4
    MOUNTAIN_MIN_CYCLE_FRAMES = 10
    MOUNTAIN_MAX_MISSING_ACTIVE_SIDE_FRAMES = 5

    def __init__(self, cooldown_frames: int = 8):
        self.states: Dict[str, UserExerciseState] = {}
        self.cooldown_frames = cooldown_frames

        # False is when every knee drive counts as 1 mountain climber rep.
        # True is reserved if later wants LEFT+RIGHT to become 1 rep.
        self.mountain_climber_pair_as_one = False

    def reset_user(self, user_key: str):
        self.states[user_key] = UserExerciseState()

    def reset_all(self):
        self.states.clear()

    def reset_exercise(self, user_key: str, exercise: str):
        self.states[user_key] = UserExerciseState(exercise=exercise, phase="IDLE")

    def update(
        self,
        user_key: str,
        exercise: str,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]] = None,
        class_valid: bool = True,
    ) -> RepCycleResult:
        if user_key not in self.states:
            self.states[user_key] = UserExerciseState(exercise=exercise)

        state = self.states[user_key]

        if state.exercise != exercise:
            self.reset_exercise(user_key, exercise)
            state = self.states[user_key]

        state.frame_index += 1

        if state.cooldown > 0:
            state.cooldown -= 1

        # ``class_valid`` is intentionally not used for phase/posture logic.
        # LSTM context gating belongs to WorkoutSession; this engine remains a
        # deterministic geometry-only phase detector and posture validator.

        if exercise == "squat":
            return self._update_squat(state, angles, landmarks)

        if exercise == "jumping_jacks":
            return self._update_jumping_jack(state, angles, landmarks)

        if exercise == "knee_push_up":
            return self._update_knee_push_up(state, angles, landmarks)

        if exercise == "sit_up":
            return self._update_sit_up(state, angles, landmarks)

        if exercise == "mountain_climber":
            return self._update_mountain_climber(state, angles, landmarks)

        return RepCycleResult(
            phase="UNKNOWN",
            feedback=f"Exercise isn't supported: {exercise}",
            debug={"exercise": exercise},
        )

    def _update_squat(
        self,
        state: UserExerciseState,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]],
    ) -> RepCycleResult:
        """
        SQUAT Phase: STAND -> DESCEND -> BOTTOM -> ASCEND -> STAND

        Main logic:
        - IDLE -> STAND as soon as knee + hip landmarks are readable.
        - STAND baseline = current hip_y and knee angle.
        - DESCEND starts when hip_y drops enough relative to torso scale.
        - Rep completes only when hip returns near baseline after a real hip drop.
        """
        knee = self._avg_angle(angles, "left_knee", "right_knee")
        hip = self._avg_angle(angles, "left_hip", "right_hip")
        hip_y = self._hip_mid_y(landmarks)
        body_scale = self._torso_scale(landmarks)

        if knee is None:
            return RepCycleResult(
                phase=state.phase,
                feedback="Knees angle isn't read",
                debug={"reason": "missing_knee_angle"},
            )

        delta = 0.0 if state.prev_main_value is None else knee - state.prev_main_value
        state.prev_main_value = knee

        has_motion_reference = (
            hip_y is not None
            and body_scale is not None
            and body_scale > 1e-6
        )

        if not has_motion_reference:
            return self._result(
                state,
                knee=knee,
                hip=hip,
                hip_y=hip_y,
                body_scale=body_scale,
                delta=delta,
                reason="missing_hip_motion_reference",
            )

        hip_y = float(hip_y)
        body_scale = float(body_scale)

        stand_hip_y = state.squat_stand_hip_y
        if stand_hip_y is None:
            stand_hip_y = hip_y
            state.squat_stand_hip_y = hip_y

        hip_drop_ratio = max(0.0, (hip_y - float(stand_hip_y)) / body_scale)

        if state.squat_stand_reference_knee == 999.0:
            state.squat_stand_reference_knee = knee
        knee_bend_drop = max(0.0, float(state.squat_stand_reference_knee) - float(knee))

        if state.phase == "IDLE":
            state.phase = "STAND"
            state.squat_stand_hip_y = hip_y
            state.squat_stand_reference_knee = knee
            state.squat_stand_stable_frames = 1
            state.squat_descent_candidate_frames = 0
            return self._result(
                state,
                knee=knee,
                hip=hip,
                hip_y=hip_y,
                body_scale=body_scale,
                baseline_hip_y=state.squat_stand_hip_y,
                baseline_knee=state.squat_stand_reference_knee,
                hip_drop_ratio=0.0,
                knee_bend_drop=0.0,
                ready=True,
            )

        if state.phase == "RECOVER":
            recovery_drop_ratio = max(0.0, (hip_y - float(state.squat_stand_hip_y)) / body_scale)
            if recovery_drop_ratio <= self.SQUAT_RECOVER_RETURN_RATIO:
                state.phase = "STAND"
                state.cooldown = 0
                state.squat_stand_stable_frames = 1
                state.squat_descent_candidate_frames = 0

                state.squat_stand_hip_y = (0.80 * float(state.squat_stand_hip_y)) + (0.20 * hip_y)
                state.squat_stand_reference_knee = max(float(state.squat_stand_reference_knee), float(knee))

            return self._result(
                state,
                knee=knee,
                hip=hip,
                hip_y=hip_y,
                body_scale=body_scale,
                baseline_hip_y=state.squat_stand_hip_y,
                baseline_knee=state.squat_stand_reference_knee,
                recovery_drop_ratio=recovery_drop_ratio,
                cooldown=state.cooldown,
                mode="relative_hip_calibrated_v6_recover",
            )

        if state.phase == "STAND":
            near_baseline = hip_drop_ratio <= 0.025
            if near_baseline:
                state.squat_stand_stable_frames += 1
                state.squat_stand_hip_y = (0.90 * float(state.squat_stand_hip_y)) + (0.10 * hip_y)
                state.squat_stand_reference_knee = max(
                    float(state.squat_stand_reference_knee),
                    float(knee),
                )
                stand_hip_y = state.squat_stand_hip_y
                hip_drop_ratio = max(0.0, (hip_y - float(stand_hip_y)) / body_scale)
                knee_bend_drop = max(0.0, float(state.squat_stand_reference_knee) - float(knee))

            descent_signal = (
                hip_drop_ratio >= 0.055
                and (
                    knee_bend_drop >= 6.0
                    or knee <= self.SQUAT_VALID_DEPTH_ANGLE
                    or delta < -0.5
                )
            )

            if descent_signal:
                state.squat_descent_candidate_frames += 1
            else:
                state.squat_descent_candidate_frames = 0

            if state.squat_descent_candidate_frames >= self.SQUAT_DESCEND_CONFIRM_FRAMES:
                state.phase = "DESCEND"
                state.invalid_current_rep = False
                state.feedback_current_rep = ""
                state.reached_bottom = False
                state.min_knee_angle = knee
                state.min_hip_angle = hip if hip is not None else 999.0
                state.squat_knee_samples = [float(knee)] if self._is_plausible_angle(knee, low=20.0, high=180.0) else []
                state.squat_hip_samples = [float(hip)] if hip is not None and self._is_plausible_angle(hip, low=20.0, high=180.0) else []
                state.squat_hip_y_samples = [hip_y]
                state.squat_body_scale_samples = [body_scale]
                state.squat_cycle_frames = 1
                state.squat_bottom_frames = 0
                state.squat_entry_knee = knee
                state.squat_started_from_low_entry = False

        elif state.phase in ("DESCEND", "BOTTOM", "ASCEND"):
            state.squat_cycle_frames += 1
            state.min_knee_angle = min(state.min_knee_angle, knee)
            if hip is not None:
                state.min_hip_angle = min(state.min_hip_angle, hip)

            if self._is_plausible_angle(knee, low=20.0, high=180.0):
                state.squat_knee_samples.append(float(knee))
            if hip is not None and self._is_plausible_angle(hip, low=20.0, high=180.0):
                state.squat_hip_samples.append(float(hip))
            state.squat_hip_y_samples.append(hip_y)
            state.squat_body_scale_samples.append(body_scale)

            max_hip_y = max(state.squat_hip_y_samples) if state.squat_hip_y_samples else hip_y
            median_body_scale = self._median(state.squat_body_scale_samples) or body_scale
            max_hip_drop_ratio = max(0.0, (float(max_hip_y) - float(state.squat_stand_hip_y)) / float(median_body_scale))
            current_hip_drop_ratio = max(0.0, (hip_y - float(state.squat_stand_hip_y)) / float(median_body_scale))

            if max_hip_drop_ratio >= self.SQUAT_MIN_HIP_DROP_RATIO:
                state.reached_bottom = True
                state.squat_bottom_frames += 1
                if state.phase == "DESCEND":
                    state.phase = "BOTTOM"

            if state.phase == "BOTTOM" and current_hip_drop_ratio <= max_hip_drop_ratio * 0.65:
                state.phase = "ASCEND"

            # A squat repetition is complete only after the hip returns to the
            # calibrated standing region. The previous implementation counted
            # immediately after ascent began, so feedback could arrive before
            # the physical cycle was complete.
            returned_to_stand = current_hip_drop_ratio <= 0.040
            count_on_ascend = False
            enough_duration = state.squat_cycle_frames >= self.SQUAT_MIN_CYCLE_FRAMES
            enough_samples = len(state.squat_hip_y_samples) >= self.SQUAT_MIN_KNEE_SAMPLES
            enough_hip_drop = max_hip_drop_ratio >= self.SQUAT_MIN_HIP_DROP_RATIO

            if (
                returned_to_stand
                and enough_duration
                and enough_samples
                and state.phase in ("BOTTOM", "ASCEND")
                and state.cooldown == 0
            ):
                robust_min_knee = self._robust_min(
                    state.squat_knee_samples,
                    fallback=state.min_knee_angle,
                    low=20.0,
                    high=180.0,
                )

                robust_min_hip = self._robust_min(
                    state.squat_hip_samples,
                    fallback=state.min_hip_angle,
                    low=20.0,
                    high=180.0,
                )

                # POSTURE VALIDATION
                hip_depth_ok = (
                    max_hip_drop_ratio >= self.SQUAT_MIN_HIP_DROP_RATIO
                )

                knee_depth_ok = (
                    robust_min_knee <= self.SQUAT_VALID_DEPTH_ANGLE
                )

                too_deep_sustained = (
                    len(state.squat_knee_samples) >= self.SQUAT_MIN_KNEE_SAMPLES
                    and robust_min_knee < 25.0
                )

                knee_dominant_squat = (
                    robust_min_knee <= self.SQUAT_KNEE_DOMINANT_KNEE_ANGLE
                    and robust_min_hip >= self.SQUAT_KNEE_DOMINANT_HIP_ANGLE
                    and max_hip_drop_ratio < self.SQUAT_STRONG_HIP_DROP_RATIO
                )

                valid = (
                    enough_duration
                    and enough_samples
                    and hip_depth_ok
                    and knee_depth_ok
                    and not knee_dominant_squat
                    and not too_deep_sustained
                    and not state.invalid_current_rep
                )

                if knee_dominant_squat:
                    feedback = (
                        "Use your hips as support, not your knees"
                    )
                elif not hip_depth_ok:
                    feedback = "Go down with your hips more"
                elif not knee_depth_ok:
                    feedback = "Buckle hips/knees more stable"
                elif too_deep_sustained:
                    feedback = "Knees pose is too extreme (read by estimator). fix legs framing"
                elif state.invalid_current_rep:
                    feedback = state.feedback_current_rep or "Squat posture isn't correct yet"
                else:
                    feedback = "Squat posture is valid."

                debug = {
                    "knee": knee,
                    "hip": hip,
                    "hip_y": hip_y,
                    "body_scale": body_scale,
                    "baseline_hip_y": state.squat_stand_hip_y,
                    "baseline_knee": state.squat_stand_reference_knee,
                    "entry_knee": state.squat_entry_knee,
                    "robust_min_knee": robust_min_knee,
                    "robust_min_hip": robust_min_hip,
                    "cycle_frames": state.squat_cycle_frames,
                    "hip_samples": len(state.squat_hip_y_samples),
                    "knee_samples": len(state.squat_knee_samples),
                    "max_hip_y": max_hip_y,
                    "max_hip_drop_ratio": max_hip_drop_ratio,
                    "current_hip_drop_ratio": current_hip_drop_ratio,
                    "min_hip_drop_ratio": self.SQUAT_MIN_HIP_DROP_RATIO,
                    "strong_hip_drop_ratio": self.SQUAT_STRONG_HIP_DROP_RATIO,
                    "returned_to_stand": returned_to_stand,
                    "count_on_ascend": count_on_ascend,
                    "ascend_count_ratio": self.SQUAT_ASCEND_COUNT_RATIO,
                    "completion_mode": "returned_to_stand",
                    "enough_duration": enough_duration,
                    "enough_samples": enough_samples,
                    "enough_hip_drop": enough_hip_drop,
                    "hip_depth_ok": hip_depth_ok,
                    "knee_depth_ok": knee_depth_ok,
                    "too_deep_sustained": too_deep_sustained,
                    "knee_dominant_squat": knee_dominant_squat,
                    "valid": valid,
                    "mode": "relative_hip_calibrated_v7_hip_dominant",
                }

                self._finish_cycle(state)
                state.squat_stand_hip_y = hip_y
                state.squat_stand_reference_knee = knee
                state.squat_stand_stable_frames = 1

                return RepCycleResult(
                    phase="STAND",
                    rep_completed=True,
                    valid_rep=valid,
                    feedback=feedback,
                    debug=debug,
                )

            return self._result(
                state,
                knee=knee,
                hip=hip,
                hip_y=hip_y,
                body_scale=body_scale,
                baseline_hip_y=state.squat_stand_hip_y,
                baseline_knee=state.squat_stand_reference_knee,
                hip_drop_ratio=current_hip_drop_ratio,
                max_hip_drop_ratio=max_hip_drop_ratio,
                cycle_frames=state.squat_cycle_frames,
                reached_bottom=state.reached_bottom,
                delta=delta,
                mode="relative_hip_calibrated_v6",
            )

        return self._result(
            state,
            knee=knee,
            hip=hip,
            hip_y=hip_y,
            body_scale=body_scale,
            baseline_hip_y=state.squat_stand_hip_y,
            baseline_knee=state.squat_stand_reference_knee,
            hip_drop_ratio=hip_drop_ratio,
            knee_bend_drop=knee_bend_drop,
            delta=delta,
            mode="relative_hip_calibrated_v6",
        )

    def _update_jumping_jack(
        self,
        state: UserExerciseState,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]],
    ) -> RepCycleResult:
        """JUMPING JACK: CLOSED -> OPEN -> CLOSED.

        Phase thresholds are deliberately easier than posture thresholds. This
        lets the engine register a partial cycle as an invalid repetition and
        provide useful feedback instead of silently ignoring it.
        """
        shoulder = self._avg_angle(angles, "left_shoulder", "right_shoulder")
        leg_ratio = self._leg_open_ratio(landmarks)

        if shoulder is None or leg_ratio is None:
            return self._result(
                state,
                shoulder=shoulder,
                leg_ratio=leg_ratio,
                reason="missing_arm_or_leg_reference",
            )

        arms_closed = shoulder <= self.JACK_CLOSED_SHOULDER
        legs_closed = leg_ratio <= self.JACK_CLOSED_LEG_RATIO
        phase_open = (
            shoulder >= self.JACK_PHASE_OPEN_SHOULDER
            and leg_ratio >= self.JACK_PHASE_OPEN_LEG_RATIO
        )

        if state.phase == "IDLE":
            if arms_closed and legs_closed:
                state.phase = "CLOSED"
            return self._result(state, shoulder=shoulder, leg_ratio=leg_ratio)

        if state.phase == "CLOSED":
            if phase_open:
                state.jack_open_candidate_frames += 1
            else:
                state.jack_open_candidate_frames = 0

            if state.jack_open_candidate_frames >= self.JACK_OPEN_CONFIRM_FRAMES:
                state.phase = "OPEN"
                state.reached_open = True
                state.invalid_current_rep = False
                state.feedback_current_rep = ""
                state.max_shoulder_angle = shoulder
                state.max_leg_ratio = leg_ratio
                state.jack_cycle_frames = 1
                state.jack_close_candidate_frames = 0

            return self._result(
                state,
                shoulder=shoulder,
                leg_ratio=leg_ratio,
                open_candidate_frames=state.jack_open_candidate_frames,
            )

        if state.phase == "OPEN":
            state.jack_cycle_frames += 1
            state.max_shoulder_angle = max(state.max_shoulder_angle, shoulder)
            state.max_leg_ratio = max(state.max_leg_ratio, leg_ratio)

            if arms_closed and legs_closed:
                state.jack_close_candidate_frames += 1
            else:
                state.jack_close_candidate_frames = 0

            if (
                state.jack_close_candidate_frames >= self.JACK_CLOSE_CONFIRM_FRAMES
                and state.cooldown == 0
            ):
                enough_duration = state.jack_cycle_frames >= self.JACK_MIN_CYCLE_FRAMES
                arm_height_ok = state.max_shoulder_angle >= self.JACK_VALID_OPEN_SHOULDER
                leg_opening_ok = state.max_leg_ratio >= self.JACK_VALID_OPEN_LEG_RATIO
                valid = enough_duration and arm_height_ok and leg_opening_ok

                if not enough_duration:
                    feedback = "Lakukan jumping jack lebih stabil."
                elif not arm_height_ok and not leg_opening_ok:
                    feedback = "Angkat tangan lebih tinggi dan buka kaki lebih lebar."
                elif not arm_height_ok:
                    feedback = "Angkat tangan lebih tinggi."
                elif not leg_opening_ok:
                    feedback = "Buka kaki lebih lebar."
                else:
                    feedback = "Jumping jack valid."

                debug = {
                    "shoulder": shoulder,
                    "leg_ratio": leg_ratio,
                    "max_shoulder": state.max_shoulder_angle,
                    "max_leg_ratio": state.max_leg_ratio,
                    "cycle_frames": state.jack_cycle_frames,
                    "enough_duration": enough_duration,
                    "arm_height_ok": arm_height_ok,
                    "leg_opening_ok": leg_opening_ok,
                    "valid": valid,
                    "mode": "jumping_jack_v2_phase_vs_posture",
                }
                self._finish_cycle(state)
                return RepCycleResult(
                    phase="CLOSED",
                    rep_completed=True,
                    valid_rep=valid,
                    feedback=feedback,
                    debug=debug,
                )

        return self._result(
            state,
            shoulder=shoulder,
            leg_ratio=leg_ratio,
            max_shoulder=state.max_shoulder_angle,
            max_leg_ratio=state.max_leg_ratio,
            cycle_frames=state.jack_cycle_frames,
        )

    def _update_knee_push_up(
        self,
        state: UserExerciseState,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]],
    ) -> RepCycleResult:
        """KNEE PUSH-UP: UP -> DESCEND -> DOWN -> ASCEND -> UP.

        Elbow motion determines the phase. Hip angle is evaluated separately as
        posture alignment, so phase detection and posture validation do not
        collapse into the same rule.
        """
        elbow = self._avg_angle(angles, "left_elbow", "right_elbow")
        hip = self._avg_angle(angles, "left_hip", "right_hip")

        if elbow is None:
            return RepCycleResult(
                state.phase,
                feedback="Elbow angle isn't read",
                debug={"reason": "missing_elbow_angle"},
            )

        delta = 0.0 if state.prev_main_value is None else elbow - state.prev_main_value
        state.prev_main_value = elbow

        if state.phase == "IDLE":
            hip_ready = hip is not None and hip >= self.PUSHUP_READY_HIP_ANGLE
            start_pose_ready = elbow >= self.PUSHUP_UP_ELBOW_ANGLE and hip_ready
            if start_pose_ready:
                state.phase = "UP"
                state.invalid_current_rep = False
                state.feedback_current_rep = ""
                state.prev_main_value = elbow
            return self._result(
                state,
                elbow=elbow,
                hip=hip,
                delta=delta,
                hip_ready=hip_ready,
                start_pose_ready=start_pose_ready,
                mode="knee_push_up_v4_posture_alignment",
            )

        if state.phase == "UP":
            descent_signal = elbow <= self.PUSHUP_DESCEND_START_ELBOW and delta < -0.3
            if descent_signal:
                state.pushup_descent_candidate_frames += 1
            else:
                state.pushup_descent_candidate_frames = 0

            if state.pushup_descent_candidate_frames >= self.PUSHUP_DESCEND_CONFIRM_FRAMES:
                state.phase = "DESCEND"
                state.invalid_current_rep = False
                state.feedback_current_rep = ""
                state.min_elbow_angle = elbow
                state.reached_down = False
                state.pushup_cycle_frames = 1
                state.pushup_down_frames = 0
                state.pushup_descent_candidate_frames = 0
                state.min_pushup_hip_angle = hip if hip is not None else 999.0
                state.max_pushup_hip_angle = hip if hip is not None else 0.0
                state.pushup_hip_samples = []
                if hip is not None and self._is_plausible_angle(hip, low=45.0, high=180.0):
                    state.pushup_hip_samples.append(float(hip))

            return self._result(
                state,
                elbow=elbow,
                hip=hip,
                delta=delta,
                descent_candidate_frames=state.pushup_descent_candidate_frames,
                mode="knee_push_up_v4_posture_alignment",
            )

        if state.phase in ("DESCEND", "DOWN", "ASCEND"):
            state.pushup_cycle_frames += 1
            state.min_elbow_angle = min(state.min_elbow_angle, elbow)
            if hip is not None:
                state.min_pushup_hip_angle = min(state.min_pushup_hip_angle, hip)
                state.max_pushup_hip_angle = max(state.max_pushup_hip_angle, hip)
                if self._is_plausible_angle(hip, low=45.0, high=180.0):
                    state.pushup_hip_samples.append(float(hip))

            if state.pushup_cycle_frames > self.PUSHUP_MAX_CYCLE_FRAMES:
                self._reset_pushup_cycle(state, phase="IDLE")
                return self._result(
                    state,
                    elbow=elbow,
                    hip=hip,
                    delta=delta,
                    reason="pushup_cycle_timeout",
                    max_cycle_frames=self.PUSHUP_MAX_CYCLE_FRAMES,
                    mode="knee_push_up_v4_posture_alignment",
                )

        if state.phase == "DESCEND":
            if elbow <= self.PUSHUP_DOWN_ELBOW_ANGLE:
                state.phase = "DOWN"
                state.reached_down = True
                state.pushup_down_frames = 1
            elif elbow >= self.PUSHUP_DESCEND_START_ELBOW and delta > 0.7:
                state.phase = "ASCEND"
                state.invalid_current_rep = True
                state.feedback_current_rep = "Turunkan tubuh lebih dalam."

        elif state.phase == "DOWN":
            if elbow <= self.PUSHUP_DOWN_ELBOW_ANGLE:
                state.pushup_down_frames += 1
            if elbow >= self.PUSHUP_ASCEND_START_ELBOW and delta > 0.3:
                state.phase = "ASCEND"

        elif state.phase == "ASCEND":
            if elbow >= self.PUSHUP_COMPLETE_ELBOW_ANGLE and state.cooldown == 0:
                enough_duration = state.pushup_cycle_frames >= self.PUSHUP_MIN_CYCLE_FRAMES
                enough_down_hold = (
                    state.reached_down
                    and state.pushup_down_frames >= self.PUSHUP_MIN_DOWN_FRAMES
                )
                elbow_depth_ok = state.min_elbow_angle <= self.PUSHUP_DOWN_ELBOW_ANGLE
                enough_hip_samples = len(state.pushup_hip_samples) >= self.PUSHUP_MIN_HIP_SAMPLES
                robust_min_hip = self._robust_min(
                    state.pushup_hip_samples,
                    fallback=state.min_pushup_hip_angle,
                    low=45.0,
                    high=180.0,
                )
                hip_alignment_ok = (
                    enough_hip_samples
                    and robust_min_hip >= self.PUSHUP_MIN_HIP_ALIGNMENT_ANGLE
                )

                valid = (
                    enough_duration
                    and enough_down_hold
                    and elbow_depth_ok
                    and hip_alignment_ok
                    and not state.invalid_current_rep
                )

                if not enough_duration:
                    feedback = "Lakukan knee push-up lebih stabil."
                elif not elbow_depth_ok:
                    feedback = "Turunkan tubuh lebih dalam."
                elif not enough_down_hold:
                    feedback = "Tahan posisi bawah sedikit lebih lama."
                elif not enough_hip_samples:
                    feedback = "Pastikan bahu, pinggul, dan lutut terlihat jelas."
                elif not hip_alignment_ok:
                    feedback = "Jaga bahu, pinggul, dan lutut tetap sejajar."
                elif state.invalid_current_rep:
                    feedback = state.feedback_current_rep or "Postur knee push-up belum benar."
                else:
                    feedback = "Knee push-up valid."

                debug = {
                    "elbow": elbow,
                    "hip": hip,
                    "delta": delta,
                    "min_elbow": state.min_elbow_angle,
                    "robust_min_hip": robust_min_hip,
                    "cycle_frames": state.pushup_cycle_frames,
                    "down_frames": state.pushup_down_frames,
                    "hip_samples": len(state.pushup_hip_samples),
                    "enough_duration": enough_duration,
                    "enough_down_hold": enough_down_hold,
                    "elbow_depth_ok": elbow_depth_ok,
                    "hip_alignment_ok": hip_alignment_ok,
                    "invalid_current_rep": state.invalid_current_rep,
                    "valid": valid,
                    "mode": "knee_push_up_v4_posture_alignment",
                }
                self._finish_cycle(state)
                return RepCycleResult(
                    phase="UP",
                    rep_completed=True,
                    valid_rep=valid,
                    feedback=feedback,
                    debug=debug,
                )

        return self._result(
            state,
            elbow=elbow,
            hip=hip,
            delta=delta,
            min_elbow=state.min_elbow_angle,
            min_pushup_hip=state.min_pushup_hip_angle,
            cycle_frames=state.pushup_cycle_frames,
            down_frames=state.pushup_down_frames,
            reached_down=state.reached_down,
            invalid_current_rep=state.invalid_current_rep,
            mode="knee_push_up_v4_posture_alignment",
        )

    def _update_sit_up(
        self,
        state: UserExerciseState,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]],
    ) -> RepCycleResult:
        """SIT-UP: DOWN -> ASCEND -> UP -> DESCEND -> DOWN."""
        torso_angle = self._torso_angle_from_horizontal(landmarks)
        hip = self._avg_angle(angles, "left_hip", "right_hip")

        if torso_angle is None:
            if hip is None:
                return RepCycleResult(
                    state.phase,
                    feedback="torso/hips angle isn't read",
                    debug={"reason": "missing_torso_and_hip"},
                )
            torso_angle = max(0.0, min(90.0, 170.0 - hip))

        down = torso_angle <= self.SITUP_DOWN_TORSO_ANGLE
        up = torso_angle >= self.SITUP_UP_TORSO_ANGLE

        if state.phase == "IDLE":
            if down:
                state.phase = "DOWN"
                state.situp_down_frames = 1
            return self._result(
                state,
                torso_angle=torso_angle,
                hip=hip,
                down=down,
                up=up,
                mode="sit_up_v3_phase_posture",
            )

        if state.phase == "DOWN":
            if down:
                state.situp_down_frames += 1

            ascend_signal = torso_angle >= self.SITUP_ASCEND_START_TORSO_ANGLE
            if ascend_signal:
                state.situp_ascend_candidate_frames += 1
            else:
                state.situp_ascend_candidate_frames = 0

            if state.situp_ascend_candidate_frames >= self.SITUP_ASCEND_CONFIRM_FRAMES:
                state.phase = "ASCEND"
                state.invalid_current_rep = False
                state.feedback_current_rep = ""
                state.reached_up = False
                state.max_torso_angle = torso_angle
                state.situp_cycle_frames = 1
                state.situp_up_frames = 0
                state.situp_down_frames = 0
                state.situp_ascend_candidate_frames = 0
                state.min_situp_hip_angle = hip if hip is not None else 999.0
                state.situp_hip_samples = []
                if hip is not None and self._is_plausible_angle(hip, low=35.0, high=180.0):
                    state.situp_hip_samples.append(float(hip))

            return self._result(
                state,
                torso_angle=torso_angle,
                hip=hip,
                down=down,
                up=up,
                ascend_candidate_frames=state.situp_ascend_candidate_frames,
                mode="sit_up_v3_phase_posture",
            )

        if state.phase in ("ASCEND", "UP", "DESCEND"):
            state.situp_cycle_frames += 1
            state.max_torso_angle = max(state.max_torso_angle, torso_angle)
            if hip is not None:
                state.min_situp_hip_angle = min(state.min_situp_hip_angle, hip)
                if self._is_plausible_angle(hip, low=35.0, high=180.0):
                    state.situp_hip_samples.append(float(hip))

        if state.phase == "ASCEND":
            if up:
                state.phase = "UP"
                state.reached_up = True
                state.situp_up_frames = 1
            elif down:
                state.phase = "DESCEND"
                state.invalid_current_rep = True
                state.feedback_current_rep = "Angkat tubuh lebih tinggi."

        elif state.phase == "UP":
            if up:
                state.situp_up_frames += 1
            if torso_angle <= self.SITUP_DESCEND_START_TORSO_ANGLE:
                state.phase = "DESCEND"
                state.situp_down_frames = 0

        elif state.phase == "DESCEND":
            if down:
                state.situp_down_frames += 1
            else:
                state.situp_down_frames = 0

            if (
                down
                and state.situp_down_frames >= self.SITUP_MIN_DOWN_FRAMES
                and state.cooldown == 0
            ):
                enough_duration = state.situp_cycle_frames >= self.SITUP_MIN_CYCLE_FRAMES
                enough_up_hold = (
                    state.reached_up
                    and state.situp_up_frames >= self.SITUP_MIN_UP_FRAMES
                )
                torso_height_ok = state.max_torso_angle >= self.SITUP_UP_TORSO_ANGLE
                returned_down_ok = state.situp_down_frames >= self.SITUP_MIN_DOWN_FRAMES
                enough_hip_samples = len(state.situp_hip_samples) >= self.SITUP_MIN_HIP_SAMPLES
                robust_min_hip = self._robust_min(
                    state.situp_hip_samples,
                    fallback=state.min_situp_hip_angle,
                    low=35.0,
                    high=180.0,
                )
                hip_flexion_ok = (
                    not enough_hip_samples
                    or robust_min_hip <= self.SITUP_VALID_HIP_FLEXION_ANGLE
                )

                valid = (
                    enough_duration
                    and enough_up_hold
                    and torso_height_ok
                    and returned_down_ok
                    and hip_flexion_ok
                    and not state.invalid_current_rep
                )

                if not enough_duration:
                    feedback = "Lakukan sit-up lebih stabil."
                elif not torso_height_ok:
                    feedback = "Angkat tubuh lebih tinggi."
                elif not enough_up_hold:
                    feedback = "Tahan posisi atas sedikit lebih lama."
                elif not returned_down_ok:
                    feedback = "Kembali ke posisi bawah sepenuhnya."
                elif not hip_flexion_ok:
                    feedback = "Tekuk tubuh dari area pinggul saat naik."
                elif state.invalid_current_rep:
                    feedback = state.feedback_current_rep or "Postur sit-up belum benar."
                else:
                    feedback = "Sit-up valid."

                debug = {
                    "torso_angle": torso_angle,
                    "hip": hip,
                    "max_torso_angle": state.max_torso_angle,
                    "robust_min_hip": robust_min_hip,
                    "cycle_frames": state.situp_cycle_frames,
                    "up_frames": state.situp_up_frames,
                    "down_frames": state.situp_down_frames,
                    "hip_samples": len(state.situp_hip_samples),
                    "enough_duration": enough_duration,
                    "enough_up_hold": enough_up_hold,
                    "torso_height_ok": torso_height_ok,
                    "returned_down_ok": returned_down_ok,
                    "hip_flexion_ok": hip_flexion_ok,
                    "invalid_current_rep": state.invalid_current_rep,
                    "valid": valid,
                    "mode": "sit_up_v3_phase_posture",
                }
                self._finish_cycle(state)
                return RepCycleResult(
                    phase="DOWN",
                    rep_completed=True,
                    valid_rep=valid,
                    feedback=feedback,
                    debug=debug,
                )

        return self._result(
            state,
            torso_angle=torso_angle,
            hip=hip,
            down=down,
            up=up,
            max_torso_angle=state.max_torso_angle,
            cycle_frames=state.situp_cycle_frames,
            up_frames=state.situp_up_frames,
            down_frames=state.situp_down_frames,
            reached_up=state.reached_up,
            invalid_current_rep=state.invalid_current_rep,
            mode="sit_up_v3_phase_posture",
        )

    def _update_mountain_climber(
        self,
        state: UserExerciseState,
        angles: Dict[str, float],
        landmarks: Optional[List[Any]],
    ) -> RepCycleResult:
        """MOUNTAIN CLIMBER: EXTENDED -> DRIVE -> EXTENDED.

        The driven side is locked when DRIVE begins. A missing driven leg never
        counts as a return to EXTENDED. Side-specific plank baselines also make
        the detector depend on real angular change, not only absolute angles
        that may be biased by MediaPipe occlusion.
        """
        values = {
            "LEFT": {
                "hip": self._angle(angles, "left_hip"),
                "knee": self._angle(angles, "left_knee"),
                "elbow": self._angle(angles, "left_elbow"),
            },
            "RIGHT": {
                "hip": self._angle(angles, "right_hip"),
                "knee": self._angle(angles, "right_knee"),
                "elbow": self._angle(angles, "right_elbow"),
            },
        }

        def usable(side: str) -> bool:
            return (
                self._is_plausible_angle(values[side]["hip"], low=35.0, high=180.0)
                and self._is_plausible_angle(values[side]["knee"], low=35.0, high=180.0)
            )

        elbow_values = [
            values[side]["elbow"]
            for side in ("LEFT", "RIGHT")
            if self._is_plausible_angle(values[side]["elbow"], low=35.0, high=190.0)
        ]
        support_elbow = max(elbow_values) if elbow_values else None
        arms_supported = (
            support_elbow is not None
            and support_elbow >= self.MOUNTAIN_ARM_SUPPORT_ELBOW
        )

        def baseline(side: str) -> tuple[Optional[float], Optional[float]]:
            prefix = side.lower()
            return (
                getattr(state, f"mountain_{prefix}_baseline_hip"),
                getattr(state, f"mountain_{prefix}_baseline_knee"),
            )

        def update_baseline(side: str):
            if not usable(side):
                return
            hip = float(values[side]["hip"])
            knee = float(values[side]["knee"])
            prefix = side.lower()
            hip_name = f"mountain_{prefix}_baseline_hip"
            knee_name = f"mountain_{prefix}_baseline_knee"
            old_hip = getattr(state, hip_name)
            old_knee = getattr(state, knee_name)
            setattr(state, hip_name, hip if old_hip is None else (0.85 * old_hip + 0.15 * hip))
            setattr(state, knee_name, knee if old_knee is None else (0.85 * old_knee + 0.15 * knee))

        def ready(side: str) -> bool:
            return (
                usable(side)
                and values[side]["hip"] >= self.MOUNTAIN_READY_HIP_ANGLE
                and values[side]["knee"] >= self.MOUNTAIN_READY_KNEE_ANGLE
            )

        def extended(side: str) -> bool:
            return (
                usable(side)
                and values[side]["hip"] >= self.MOUNTAIN_EXTENDED_HIP_ANGLE
                and values[side]["knee"] >= self.MOUNTAIN_EXTENDED_KNEE_ANGLE
            )

        def drive_metrics(side: str) -> dict:
            base_hip, base_knee = baseline(side)
            if not usable(side) or base_hip is None or base_knee is None:
                return {
                    "signal": False,
                    "hip_drop": 0.0,
                    "knee_drop": 0.0,
                    "score": -1.0,
                }
            hip = float(values[side]["hip"])
            knee = float(values[side]["knee"])
            hip_drop = max(0.0, float(base_hip) - hip)
            knee_drop = max(0.0, float(base_knee) - knee)
            signal = (
                hip <= self.MOUNTAIN_PHASE_DRIVE_HIP_ANGLE
                and knee <= self.MOUNTAIN_PHASE_DRIVE_KNEE_ANGLE
                and (
                    hip_drop >= self.MOUNTAIN_MIN_HIP_DROP
                    or knee_drop >= self.MOUNTAIN_MIN_KNEE_DROP
                )
            )
            return {
                "signal": signal,
                "hip_drop": hip_drop,
                "knee_drop": knee_drop,
                "score": hip_drop + knee_drop,
            }

        if state.phase == "IDLE":
            ready_sides = [side for side in ("LEFT", "RIGHT") if ready(side)]
            if ready_sides and arms_supported:
                state.mountain_start_frames += 1
                for side in ready_sides:
                    update_baseline(side)
            else:
                state.mountain_start_frames = 0

            if state.mountain_start_frames >= self.MOUNTAIN_START_CONFIRM_FRAMES:
                state.phase = "EXTENDED"
                state.mountain_start_frames = 0

            return self._result(
                state,
                left_hip=values["LEFT"]["hip"],
                right_hip=values["RIGHT"]["hip"],
                left_knee=values["LEFT"]["knee"],
                right_knee=values["RIGHT"]["knee"],
                support_elbow=support_elbow,
                arms_supported=arms_supported,
                ready_sides=ready_sides,
                start_frames=state.mountain_start_frames,
                mode="mountain_climber_v3_side_locked",
            )

        if state.phase == "EXTENDED":
            for side in ("LEFT", "RIGHT"):
                if extended(side):
                    update_baseline(side)

            metrics = {side: drive_metrics(side) for side in ("LEFT", "RIGHT")}
            candidates = [side for side in ("LEFT", "RIGHT") if metrics[side]["signal"]]
            candidate = max(candidates, key=lambda side: metrics[side]["score"]) if candidates else None

            if candidate is None:
                state.mountain_candidate_side = None
                state.mountain_drive_frames = 0
            elif state.mountain_candidate_side == candidate:
                state.mountain_drive_frames += 1
            else:
                state.mountain_candidate_side = candidate
                state.mountain_drive_frames = 1

            if state.mountain_drive_frames >= self.MOUNTAIN_DRIVE_CONFIRM_FRAMES:
                state.phase = "DRIVE"
                state.mountain_active_side = candidate
                state.last_mountain_side = candidate
                state.invalid_current_rep = not arms_supported
                state.feedback_current_rep = (
                    "Jaga lengan tetap kuat dan lurus."
                    if not arms_supported
                    else ""
                )
                state.mountain_cycle_frames = 1
                state.mountain_extend_frames = 0
                state.mountain_missing_active_side_frames = 0
                state.min_mountain_hip_angle = float(values[candidate]["hip"])
                state.min_mountain_knee_angle = float(values[candidate]["knee"])
                state.min_mountain_elbow_angle = (
                    float(support_elbow) if support_elbow is not None else 999.0
                )
                base_hip, base_knee = baseline(candidate)
                state.mountain_active_baseline_hip = base_hip
                state.mountain_active_baseline_knee = base_knee
                state.mountain_candidate_side = None
                state.mountain_drive_frames = 0

            return self._result(
                state,
                active_side=candidate,
                left_metrics=metrics["LEFT"],
                right_metrics=metrics["RIGHT"],
                drive_frames=state.mountain_drive_frames,
                support_elbow=support_elbow,
                arms_supported=arms_supported,
                mode="mountain_climber_v3_side_locked",
            )

        if state.phase == "DRIVE":
            side = state.mountain_active_side
            if side not in ("LEFT", "RIGHT"):
                self._reset_mountain_cycle(state, phase="IDLE")
                return self._result(state, reason="missing_active_side")

            state.mountain_cycle_frames += 1

            if not usable(side):
                state.mountain_missing_active_side_frames += 1
                state.mountain_extend_frames = 0
                if (
                    state.mountain_missing_active_side_frames
                    > self.MOUNTAIN_MAX_MISSING_ACTIVE_SIDE_FRAMES
                ):
                    self._reset_mountain_cycle(state, phase="IDLE")
                    return self._result(
                        state,
                        reason="active_side_lost",
                        active_side=side,
                        mode="mountain_climber_v3_side_locked",
                    )
                return self._result(
                    state,
                    active_side=side,
                    active_side_missing=True,
                    missing_frames=state.mountain_missing_active_side_frames,
                    cycle_frames=state.mountain_cycle_frames,
                    mode="mountain_climber_v3_side_locked",
                )

            state.mountain_missing_active_side_frames = 0
            active_hip = float(values[side]["hip"])
            active_knee = float(values[side]["knee"])
            state.min_mountain_hip_angle = min(state.min_mountain_hip_angle, active_hip)
            state.min_mountain_knee_angle = min(state.min_mountain_knee_angle, active_knee)

            if support_elbow is None or support_elbow < self.MOUNTAIN_ARM_SUPPORT_ELBOW:
                state.invalid_current_rep = True
                state.feedback_current_rep = "Jaga lengan tetap kuat dan lurus."
            else:
                state.min_mountain_elbow_angle = min(
                    state.min_mountain_elbow_angle,
                    float(support_elbow),
                )

            if extended(side):
                state.mountain_extend_frames += 1
            else:
                state.mountain_extend_frames = 0

            if (
                state.mountain_extend_frames >= self.MOUNTAIN_EXTEND_CONFIRM_FRAMES
                and state.cooldown == 0
            ):
                enough_duration = state.mountain_cycle_frames >= self.MOUNTAIN_MIN_CYCLE_FRAMES
                base_hip = state.mountain_active_baseline_hip
                base_knee = state.mountain_active_baseline_knee
                hip_drop = (
                    max(0.0, float(base_hip) - state.min_mountain_hip_angle)
                    if base_hip is not None else 0.0
                )
                knee_drop = (
                    max(0.0, float(base_knee) - state.min_mountain_knee_angle)
                    if base_knee is not None else 0.0
                )
                hip_drive_ok = (
                    state.min_mountain_hip_angle <= self.MOUNTAIN_VALID_DRIVE_HIP_ANGLE
                    or hip_drop >= self.MOUNTAIN_VALID_HIP_DROP
                )
                knee_drive_ok = (
                    state.min_mountain_knee_angle <= self.MOUNTAIN_VALID_DRIVE_KNEE_ANGLE
                    or knee_drop >= self.MOUNTAIN_VALID_KNEE_DROP
                )
                arm_support_ok = (
                    state.min_mountain_elbow_angle >= self.MOUNTAIN_ARM_SUPPORT_ELBOW
                    and not state.invalid_current_rep
                )
                valid = enough_duration and hip_drive_ok and knee_drive_ok and arm_support_ok

                if not enough_duration:
                    feedback = "Lakukan mountain climber lebih stabil."
                elif not hip_drive_ok or not knee_drive_ok:
                    feedback = "Tarik lutut lebih dekat ke arah dada."
                elif not arm_support_ok:
                    feedback = state.feedback_current_rep or "Jaga lengan tetap kuat dan lurus."
                else:
                    feedback = "Mountain climber valid."

                debug = {
                    "active_side": side,
                    "left_hip": values["LEFT"]["hip"],
                    "right_hip": values["RIGHT"]["hip"],
                    "left_knee": values["LEFT"]["knee"],
                    "right_knee": values["RIGHT"]["knee"],
                    "support_elbow": support_elbow,
                    "baseline_hip": base_hip,
                    "baseline_knee": base_knee,
                    "min_mountain_hip": state.min_mountain_hip_angle,
                    "min_mountain_knee": state.min_mountain_knee_angle,
                    "min_mountain_elbow": state.min_mountain_elbow_angle,
                    "hip_drop": hip_drop,
                    "knee_drop": knee_drop,
                    "cycle_frames": state.mountain_cycle_frames,
                    "extend_frames": state.mountain_extend_frames,
                    "enough_duration": enough_duration,
                    "hip_drive_ok": hip_drive_ok,
                    "knee_drive_ok": knee_drive_ok,
                    "arm_support_ok": arm_support_ok,
                    "valid": valid,
                    "mode": "mountain_climber_v3_side_locked",
                }
                self._finish_cycle(state)
                return RepCycleResult(
                    phase="EXTENDED",
                    rep_completed=True,
                    valid_rep=valid,
                    feedback=feedback,
                    debug=debug,
                )

            return self._result(
                state,
                active_side=side,
                active_hip=active_hip,
                active_knee=active_knee,
                support_elbow=support_elbow,
                extend_frames=state.mountain_extend_frames,
                cycle_frames=state.mountain_cycle_frames,
                mode="mountain_climber_v3_side_locked",
            )

        return self._result(state, reason="unexpected_phase", mode="mountain_climber_v3_side_locked")

    def _finish_cycle(self, state: UserExerciseState):
        state.phase = self._default_phase_after_rep(state.exercise)
        state.cooldown = self.cooldown_frames
        state.invalid_current_rep = False
        state.feedback_current_rep = ""
        state.prev_main_value = None

        state.min_knee_angle = 999.0
        state.min_hip_angle = 999.0
        state.reached_bottom = False
        state.squat_knee_samples.clear()
        state.squat_hip_samples.clear()
        state.squat_hip_y_samples.clear()
        state.squat_body_scale_samples.clear()
        state.squat_cycle_frames = 0
        state.squat_bottom_frames = 0
        state.squat_descent_candidate_frames = 0
        state.squat_entry_knee = 999.0
        state.squat_stand_reference_knee = 999.0
        state.squat_stand_stable_frames = 0
        state.squat_descent_candidate_low_entry = False
        state.squat_started_from_low_entry = False
        state.movement_context_seen = False

        state.min_elbow_angle = 999.0
        state.reached_down = False
        state.pushup_cycle_frames = 0
        state.pushup_down_frames = 0
        state.pushup_descent_candidate_frames = 0
        state.min_pushup_hip_angle = 999.0
        state.max_pushup_hip_angle = 0.0
        state.pushup_hip_samples.clear()

        state.reached_open = False
        state.max_shoulder_angle = 0.0
        state.max_leg_ratio = 0.0
        state.jack_cycle_frames = 0
        state.jack_open_candidate_frames = 0
        state.jack_close_candidate_frames = 0

        state.reached_up = False
        state.max_torso_angle = 0.0
        state.situp_cycle_frames = 0
        state.situp_up_frames = 0
        state.situp_down_frames = 0
        state.situp_ascend_candidate_frames = 0
        state.min_situp_hip_angle = 999.0
        state.situp_hip_samples.clear()

        # Keep calibrated mountain-climber baselines across repetitions, but
        # clear all per-cycle state.
        state.last_mountain_side = None
        state.mountain_candidate_side = None
        state.mountain_active_side = None
        state.mountain_start_frames = 0
        state.mountain_cycle_frames = 0
        state.mountain_drive_frames = 0
        state.mountain_extend_frames = 0
        state.mountain_missing_active_side_frames = 0
        state.min_mountain_hip_angle = 999.0
        state.min_mountain_knee_angle = 999.0
        state.min_mountain_elbow_angle = 999.0
        state.mountain_active_baseline_hip = None
        state.mountain_active_baseline_knee = None

    def _reset_pushup_cycle(self, state: UserExerciseState, phase: str = "IDLE"):
        state.phase = phase
        state.invalid_current_rep = False
        state.feedback_current_rep = ""
        state.prev_main_value = None
        state.min_elbow_angle = 999.0
        state.reached_down = False
        state.pushup_cycle_frames = 0
        state.pushup_down_frames = 0
        state.pushup_descent_candidate_frames = 0
        state.min_pushup_hip_angle = 999.0
        state.max_pushup_hip_angle = 0.0
        state.pushup_hip_samples.clear()

    def _reset_mountain_cycle(self, state: UserExerciseState, phase: str = "IDLE"):
        state.phase = phase
        state.invalid_current_rep = False
        state.feedback_current_rep = ""
        state.last_mountain_side = None
        state.mountain_candidate_side = None
        state.mountain_active_side = None
        state.mountain_start_frames = 0
        state.mountain_cycle_frames = 0
        state.mountain_drive_frames = 0
        state.mountain_extend_frames = 0
        state.mountain_missing_active_side_frames = 0
        state.min_mountain_hip_angle = 999.0
        state.min_mountain_knee_angle = 999.0
        state.min_mountain_elbow_angle = 999.0
        state.mountain_active_baseline_hip = None
        state.mountain_active_baseline_knee = None

    def _default_phase_after_rep(self, exercise: Optional[str]) -> str:
        if exercise == "squat":
            return "STAND"
        if exercise == "jumping_jacks":
            return "CLOSED"
        if exercise == "knee_push_up":
            return "UP"
        if exercise == "sit_up":
            return "DOWN"
        if exercise == "mountain_climber":
            return "EXTENDED"
        return "IDLE"

    def _result(self, state: UserExerciseState, **debug) -> RepCycleResult:
        return RepCycleResult(
            phase=state.phase,
            rep_completed=False,
            valid_rep=False,
            feedback="",
            debug=debug,
        )

    def _is_plausible_angle(self, value: Optional[float], low: float = 35.0, high: float = 180.0) -> bool:
        if value is None:
            return False
        try:
            value = float(value)
        except Exception:
            return False
        return low <= value <= high

    def _robust_min(
        self,
        values: List[float],
        fallback: float,
        low: float = 35.0,
        high: float = 180.0,
    ) -> float:
        filtered = [float(v) for v in values if self._is_plausible_angle(v, low=low, high=high)]
        if not filtered:
            return float(fallback)

        filtered.sort()

        idx = int(round(0.10 * (len(filtered) - 1)))
        return filtered[idx]

    def _median(self, values: List[float]) -> Optional[float]:
        if not values:
            return None
        values = sorted(float(v) for v in values)
        n = len(values)
        mid = n // 2
        if n % 2 == 1:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2.0

    def _midpoint(self, a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        if a is None or b is None:
            return None
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

    def _hip_mid_y(self, landmarks: Optional[List[Any]]) -> Optional[float]:
        lh = self._landmark_xy(landmarks, 23)
        rh = self._landmark_xy(landmarks, 24)
        hip_mid = self._midpoint(lh, rh)
        if hip_mid is None:
            return None
        return float(hip_mid[1])

    def _torso_scale(self, landmarks: Optional[List[Any]]) -> Optional[float]:
        ls = self._landmark_xy(landmarks, 11)
        rs = self._landmark_xy(landmarks, 12)
        lh = self._landmark_xy(landmarks, 23)
        rh = self._landmark_xy(landmarks, 24)
        shoulder_mid = self._midpoint(ls, rs)
        hip_mid = self._midpoint(lh, rh)
        scale = self._distance(shoulder_mid, hip_mid)
        if scale is None or scale <= 1e-6:
            scale = self._distance(ls, rs)
        return scale

    def _angle(self, angles: Dict[str, float], key: str) -> Optional[float]:
        value = angles.get(key)
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _avg_angle(self, angles: Dict[str, float], left_key: str, right_key: str) -> Optional[float]:
        left = self._angle(angles, left_key)
        right = self._angle(angles, right_key)
        values = [v for v in [left, right] if v is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def _landmark_xy(self, landmarks: Optional[List[Any]], index: int) -> Optional[Tuple[float, float]]:
        if landmarks is None or index >= len(landmarks):
            return None

        lm = landmarks[index]

        try:
            return float(lm.x), float(lm.y)
        except Exception:
            pass

        try:
            return float(lm["x"]), float(lm["y"])
        except Exception:
            pass

        try:
            return float(lm[0]), float(lm[1])
        except Exception:
            return None

    def _distance(self, a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> Optional[float]:
        if a is None or b is None:
            return None
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _leg_open_ratio(self, landmarks: Optional[List[Any]]) -> Optional[float]:
        left_shoulder = self._landmark_xy(landmarks, 11)
        right_shoulder = self._landmark_xy(landmarks, 12)
        left_ankle = self._landmark_xy(landmarks, 27)
        right_ankle = self._landmark_xy(landmarks, 28)

        shoulder_width = self._distance(left_shoulder, right_shoulder)
        ankle_width = self._distance(left_ankle, right_ankle)

        if shoulder_width is None or ankle_width is None or shoulder_width <= 1e-6:
            return None

        return ankle_width / shoulder_width

    def _torso_angle_from_horizontal(self, landmarks: Optional[List[Any]]) -> Optional[float]:
        ls = self._landmark_xy(landmarks, 11)
        rs = self._landmark_xy(landmarks, 12)
        lh = self._landmark_xy(landmarks, 23)
        rh = self._landmark_xy(landmarks, 24)

        if ls is None or rs is None or lh is None or rh is None:
            return None

        shoulder_mid = ((ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0)
        hip_mid = ((lh[0] + rh[0]) / 2.0, (lh[1] + rh[1]) / 2.0)

        dx = shoulder_mid[0] - hip_mid[0]
        dy = shoulder_mid[1] - hip_mid[1]

        angle_rad = math.atan2(abs(dy), abs(dx))
        return math.degrees(angle_rad)
