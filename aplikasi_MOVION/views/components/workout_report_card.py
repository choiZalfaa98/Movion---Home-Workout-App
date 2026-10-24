from PyQt6.QtWidgets import QFrame, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

pdf_icon_path = BASE_DIR / "assets" / "icons" / "pdf.svg"

class WorkoutReportCard(QFrame):
    EXERCISE_ORDER = [
        "Jumping Jacks",
        "Mountain Climber",
        "Squat",
        "Knee Push Up",
        "Sit Up",
    ]

    def __init__(self, report_data=None, on_download=None, parent=None):
        super().__init__(parent)

        self.report_data = report_data or {}
        self.on_download = on_download

        self.setProperty("role", "workoutResultCard")

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self._build_ui()
    
    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 20)
        main_layout.setSpacing(0)

        mode = self.report_data.get("mode", "single")
        users = self.report_data.get("users", []) or []

        # --- EMPTY STATE ---
        if not users:
            empty_label = QLabel("No workout report data available.")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(empty_label)
            return

        # --- SINGLE USER LAYOUT ---
        if mode == "single" or len(users) == 1:
            section = self._create_user_report_section(
                user_data=users[0],
                date=self.report_data.get("date"),
                show_download=True,
            )

            main_layout.addWidget(section, 1)
            return

        # --- MULTI USER LAYOUT ---
        left_section = self._create_user_report_section(
            user_data=users[0],
            date=self.report_data.get("date"),
            show_download=False,
        )

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setObjectName("reportDivider")
        divider.setContentsMargins(0, 0, 0, 0)

        right_section = self._create_user_report_section(
            user_data=users[1],
            date=None,
            show_download=True,
        )

        main_layout.addWidget(left_section, 1)
        main_layout.addSpacing(28)
        main_layout.addWidget(divider)
        main_layout.addSpacing(28)
        main_layout.addWidget(right_section, 1)

    def _create_user_report_section(self, user_data, date=None, show_download=False):
        section = QWidget()
        section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        username = QLabel(user_data.get("name", "User"))
        username.setObjectName("reportUsername")
        username.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        username_line = QFrame()
        username_line.setObjectName("reportUsernameLine")
        username_line.setFrameShape(QFrame.Shape.HLine)
        username_line.setFrameShadow(QFrame.Shadow.Plain)
        username_line.setFixedHeight(1)
        username_line.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        posture_heading = QLabel("Correct Posture")
        posture_heading.setObjectName("reportSubheading")

        layout.addWidget(username)
        layout.addSpacing(6)
        layout.addWidget(username_line)
        layout.addSpacing(10)
        layout.addWidget(posture_heading)

        exercises = user_data.get("exercises", {}) or {}

        for exercise in self.EXERCISE_ORDER:
            stats = exercises.get(exercise)

            if not stats:
                continue

            correct = int(stats.get("correct", 0) or 0)
            total = int(stats.get("total", 0) or 0)
            percentage = correct / total * 100 if total > 0 else 0

            row = QWidget()
            row.setProperty("role", "correctPosture")
            row.setContentsMargins(0, 0, 0, 0)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            exercise_label = QLabel(str(exercise))
            result_label = QLabel(f"{percentage:.1f}% ({correct}/{total})")
            result_label.setAlignment(Qt.AlignmentFlag.AlignRight)

            row_layout.addWidget(exercise_label)
            row_layout.addStretch()
            row_layout.addWidget(result_label)

            layout.addWidget(row)

        duration_widget = self._create_extra_info_row(
            label_text="Total Workout Duration:",
            value_text=str(user_data.get("duration", "00:00:00")),
        )

        calorie_widget = self._create_extra_info_row(
            label_text="Calorie burnt estimated:",
            value_text=f"{user_data.get('calories', 0)} kcal",
        )

        layout.addSpacing(40)
        layout.addWidget(duration_widget)
        layout.addWidget(calorie_widget)
        layout.addStretch()

        if date:
            date_label = QLabel(f"Date: {date}")
            date_label.setObjectName("reportDate")
            layout.addWidget(date_label, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addStretch()

        if show_download:
            download_btn = self._create_download_button()
            layout.addWidget(download_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return section

    def _create_extra_info_row(self, label_text, value_text):
        row = QWidget()
        row.setProperty("role", "extraResultInfo")

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        label = QLabel(label_text)
        value = QLabel(value_text)
        value.setAlignment(Qt.AlignmentFlag.AlignRight)

        row_layout.addWidget(label)
        row_layout.addStretch()
        row_layout.addWidget(value)

        return row

    def _create_download_button(self):
        download_btn = QToolButton()
        download_btn.setText("Download Report")
        download_btn.setIcon(QIcon(str(pdf_icon_path)))
        download_btn.setIconSize(QSize(32, 32))
        download_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

        download_btn.clicked.connect(
            lambda _checked=False: self._handle_download_clicked()
        )

        return download_btn

    def _handle_download_clicked(self):
        if callable(self.on_download):
            self.on_download()