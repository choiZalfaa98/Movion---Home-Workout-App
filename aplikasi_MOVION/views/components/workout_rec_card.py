from PyQt6.QtWidgets import (
    QFrame,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
)
from PyQt6.QtCore import Qt


class WorkoutRecommendationCard(QFrame):
    """
    Shows recommendations only for exercises in the poor category.

    Poor category:
        correct_posture_rate <= 70%
    """

    POOR_THRESHOLD = 70.0

    EXERCISE_ORDER = [
        "Jumping Jacks",
        "Mountain Climber",
        "Squat",
        "Knee Push Up",
        "Sit Up",
    ]

    POOR_RECOMMENDATIONS = {
        "Jumping Jacks": (
            "Coordinate your arm and leg movement. Raise your arms fully, "
            "open your feet evenly, keep your knees slightly bent, and land "
            "with control."
        ),
        "Mountain Climber": (
            "Keep your shoulders above your hands, brace your core, maintain "
            "level hips, and drive each knee toward your chest with controlled "
            "movement."
        ),
        "Squat": (
            "Keep your knees aligned with your toes, push your hips backward, "
            "maintain a stable torso, and control your squat depth."
        ),
        "Knee Push Up": (
            "Keep your head, hips, and knees aligned. Brace your core, lower your chest with "
            "control, and avoid letting your hips drop."
        ),
        "Sit Up": (
            "Keep your feet stable, engage your core, and lift and lower your "
            "torso with control. Avoid pulling your neck forward."
        ),
    }

    def __init__(self, report_data=None, parent=None):
        super().__init__(parent)

        self.report_data = report_data or {}

        self.setObjectName("recommendationCard")
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.MinimumExpanding,
        )

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 22, 24, 24)
        main_layout.setSpacing(16)

        title = QLabel("Workout Recommendations")
        title.setObjectName("recommendationTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        subtitle = QLabel(
            "Focus on the exercises with a correct posture rate of 70% or below."
        )
        subtitle.setObjectName("recommendationSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(4)

        users = self.report_data.get("users", []) or []
        mode = str(self.report_data.get("mode", "single")).lower()
        is_multi = mode == "multi" and len(users) > 1

        rendered_user_count = 0

        for user_data in users:
            poor_exercises = self._get_poor_exercises(user_data)

            # Hide users without poor exercises.
            if not poor_exercises:
                continue

            if rendered_user_count > 0:
                main_layout.addSpacing(6)

                divider = QFrame()
                divider.setObjectName("recommendationUserDivider")
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setFixedHeight(1)
                main_layout.addWidget(divider)

                main_layout.addSpacing(6)

            main_layout.addWidget(
                self._create_user_section(
                    user_data=user_data,
                    poor_exercises=poor_exercises,
                    show_user_heading=is_multi,
                )
            )
            rendered_user_count += 1

        if rendered_user_count == 0:
            empty_label = QLabel(
                "No exercise needs a posture recommendation for this workout."
            )
            empty_label.setObjectName("recommendationEmpty")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            empty_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            main_layout.addWidget(empty_label)

        main_layout.addSpacing(8)

        reminder = QLabel("Review the workout guide to refine your technique and improve your next session!")
        reminder.setObjectName("recommendationReminder")
        reminder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reminder.setWordWrap(True)
        reminder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        main_layout.addWidget(reminder)

    def _create_user_section(
        self,
        user_data,
        poor_exercises,
        show_user_heading,
    ):
        section = QWidget()
        section.setObjectName("recommendationUserSection")
        section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )

        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(12)

        if show_user_heading:
            user_name = str(user_data.get("name", "User")).strip() or "User"

            username = QLabel(f"Recommendations for {user_name}")
            username.setObjectName("recommendationUserName")
            username.setAlignment(Qt.AlignmentFlag.AlignLeft)
            username.setWordWrap(True)

            section_layout.addWidget(username)
            section_layout.addSpacing(2)

        for exercise, correct, total, percentage in poor_exercises:
            section_layout.addWidget(
                self._create_exercise_card(
                    exercise=exercise,
                    correct=correct,
                    total=total,
                    percentage=percentage,
                )
            )

        return section

    def _create_exercise_card(
        self,
        exercise,
        correct,
        total,
        percentage,
    ):
        card = QFrame()
        card.setObjectName("recommendationExerciseCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )

        outer_layout = QHBoxLayout(card)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        accent_bar = QFrame()
        accent_bar.setObjectName("recommendationAccentBar")
        accent_bar.setFixedWidth(4)
        accent_bar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        content = QWidget()
        content.setObjectName("recommendationExerciseContent")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 15)
        content_layout.setSpacing(9)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        exercise_label = QLabel(exercise)
        exercise_label.setObjectName("recommendationExerciseName")
        exercise_label.setWordWrap(True)
        exercise_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        rate_label = QLabel(
            f"{percentage:.1f}% ({correct}/{total})"
        )
        rate_label.setObjectName("recommendationRate")
        rate_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        rate_label.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )

        header_layout.addWidget(exercise_label, 1)
        header_layout.addWidget(rate_label, 0)

        recommendation_label = QLabel(
            self.POOR_RECOMMENDATIONS.get(
                exercise,
                "Focus on controlled movement and review the exercise guide.",
            )
        )
        recommendation_label.setObjectName("recommendationText")
        recommendation_label.setWordWrap(True)
        recommendation_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )
        recommendation_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )
        recommendation_label.setMinimumHeight(52)

        content_layout.addLayout(header_layout)
        content_layout.addWidget(recommendation_label)

        outer_layout.addWidget(accent_bar)
        outer_layout.addWidget(content, 1)

        return card

    def _get_poor_exercises(self, user_data):
        exercises = user_data.get("exercises", {}) or {}
        poor_exercises = []

        for exercise in self.EXERCISE_ORDER:
            stats = exercises.get(exercise)
            if not stats:
                continue

            correct = self._safe_int(stats.get("correct", 0))
            total = self._safe_int(stats.get("total", 0))

            # A zero total has no valid posture rate.
            if total <= 0:
                continue

            percentage = correct / total * 100.0

            if percentage <= self.POOR_THRESHOLD:
                poor_exercises.append(
                    (exercise, correct, total, percentage)
                )

        return poor_exercises

    @staticmethod
    def _safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0