from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal

from views.components.workout_report_card import WorkoutReportCard

from services.pdf_report_service import generate_workout_report_pdf

from datetime import date as dt_date

class WorkoutResult(QWidget):
    back_to_home = pyqtSignal()

    def __init__(self, report_data=None):
        super().__init__()

        self.session = None
        self.report_data = report_data
        self.report_card = None

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        page_title = QLabel("Workout Session")
        page_title.setProperty("role", "pageTitle")

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        header_layout.addWidget(
            page_title,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.heading = QLabel("Your workout today has been completed!")
        self.heading.setObjectName("workoutResultHeading")

        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 28, 0, 30)
        self.content_layout.setSpacing(0)
        self.content_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )

        self.report_slot = QWidget()
        self.report_slot.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self.report_slot_layout = QVBoxLayout(self.report_slot)
        self.report_slot_layout.setContentsMargins(0, 0, 0, 0)
        self.report_slot_layout.setSpacing(0)
        self.report_slot_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.cta_btn = QPushButton("Back to Homepage")
        self.cta_btn.setProperty("role", "button1")
        self.cta_btn.setFixedSize(275, 40)
        self.cta_btn.clicked.connect(lambda: self.back_to_home.emit())

        self.content_layout.addWidget(
            self.heading,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.content_layout.addSpacing(42)
        self.content_layout.addWidget(
            self.report_slot,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.content_layout.addSpacing(58)
        self.content_layout.addWidget(
            self.cta_btn,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root_layout.addWidget(header, 0)
        root_layout.addWidget(self.content_container, 1)

        self.setLayout(root_layout)

        if self.report_data:
            self._refresh_report(self.report_data)

    def set_session(self, session):
        self.session = session
        self.report_data = self._build_report_data(session)
        self._refresh_report(self.report_data)

    def _build_report_data(self, session):
        today = dt_date.today().strftime("%d-%m-%Y")

        if not hasattr(session, "results") or session.results is None:
            session.results = []

        #print("[REPORT_SESSION_RESULTS]", session.results)

        def find_result(workout):
            workout_id = workout.get("id")
            workout_name = workout.get("name")

            if hasattr(session, "get_workout_result"):
                result = session.get_workout_result(
                    exercise_id=workout_id,
                    exercise_name=workout_name,
                )
                if result:
                    return result

            for result in session.results:
                if result.get("exercise_id") == workout_id:
                    return result

                if result.get("exercise") == workout_name:
                    return result

            return None

        def build_user_data(user_info, user_key):
            user_info = user_info or {}
            exercises = {}

            for workout in getattr(session, "workouts", []) or []:
                workout_name = workout.get("name", "Workout")
                result = find_result(workout)

                if result and user_key in result:
                    valid_reps = result[user_key].get("valid_reps", 0)
                    total_reps = result[user_key].get("total_reps", 0)
                else:
                    valid_reps = 0
                    total_reps = 0

                exercises[workout_name] = {
                    "correct": valid_reps,
                    "total": total_reps,
                }

            duration = "00:00:00"
            if hasattr(session, "get_duration_formatted"):
                duration = session.get_duration_formatted()

            calories = 0
            if hasattr(session, "calorie_calculator"):
                try:
                    calories = session.calorie_calculator.calculate_total_from_session(
                        session=session,
                        user_info=user_info,
                    )
                except Exception as e:
                    #print("[CALORIE_CALC_WARN]", e)
                    calories = 0

            return {
                "name": user_info.get("name", "User"),
                "duration": duration,
                "calories": calories,
                "exercises": exercises,
            }

        mode = getattr(session, "mode", "single")

        users = [
            build_user_data(
                getattr(session, "user1", {}) or {},
                "user1",
            )
        ]

        if mode == "multi":
            users.append(
                build_user_data(
                    getattr(session, "user2", {}) or {"name": "Person 2"},
                    "user2",
                )
            )

        return {
            "mode": mode,
            "date": today,
            "users": users,
        }

    def _refresh_report(self, report_data):
        self._clear_report_slot()

        self.report_card = WorkoutReportCard(
            report_data=report_data,
            on_download=self.download_report_pdf,
        )

        card_width = self._get_report_card_width(report_data)
        self.report_card.setFixedWidth(card_width)
        self.report_card.setMinimumHeight(360)
        self.report_card.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self.report_slot_layout.addWidget(
            self.report_card,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

    def _clear_report_slot(self):
        while self.report_slot_layout.count():
            item = self.report_slot_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.report_card = None

    def _get_report_card_width(self, report_data):
        users = report_data.get("users", []) or []
        mode = report_data.get("mode", "single")

        if mode == "multi" and len(users) > 1:
            return 760

        return 540

    def download_report_pdf(self):
        if not self.report_data:
            QMessageBox.warning(
                self,
                "Report Not Ready",
                "Workout report data is not available yet.",
            )
            return

        result = generate_workout_report_pdf(self.report_data)

        if result["success"]:
            QMessageBox.information(
                self,
                "Report Downloaded",
                f"PDF report has been saved to:\n{result['file_path']}",
            )
        else:
            QMessageBox.critical(
                self,
                "Download Failed",
                f"Failed to generate PDF report:\n{result['error']}",
            )