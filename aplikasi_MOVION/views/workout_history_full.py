from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QMessageBox,
    QSizePolicy,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon

from views.components.sidebar import Sidebar
from views.page_constants import Page
from views.components.workout_report_card import WorkoutReportCard
from views.components.workout_rec_card import (
    WorkoutRecommendationCard,
)

from services.pdf_report_service import generate_workout_report_pdf

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
back_icon_path = BASE_DIR / "assets" / "icons" / "back_or_pause.svg"


class WorkoutHistoryFull(QWidget):
    back_to_history = pyqtSignal()

    def __init__(self, navigate_func):
        super().__init__()

        self.navigate = navigate_func
        self.report_data = None
        self.status_value = "completed"
        self.report_card = None
        self.recommendation_card = None

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar(active_page=Page.WORKOUT_HISTORY)
        self.sidebar.navigate_requested.connect(self.navigate)

        content_page = QWidget()
        page_layout = QVBoxLayout(content_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 6, 4, 6)

        back_btn = QToolButton()
        back_btn.setText("Back")
        back_btn.setProperty("role", "backPauseButton")
        back_btn.setIcon(QIcon(str(back_icon_path)))
        back_btn.setIconSize(QSize(18, 18))
        back_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        back_btn.clicked.connect(self.back_to_history.emit)

        page_title = QLabel("History")
        page_title.setProperty("role", "pageTitle")
        page_title.setContentsMargins(0, 0, 80, 0)

        header_layout.addWidget(
            back_btn,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        header_layout.addStretch()
        header_layout.addWidget(
            page_title,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        header_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        scroll_content = QWidget()
        scroll_content.setProperty("role", "scrollContent")

        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
        )
        self.content_layout.setContentsMargins(46, 20, 46, 60)
        self.content_layout.setSpacing(0)

        heading = QLabel("Workout Summary")
        heading.setProperty("role", "heading2")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.status_label = QLabel("-")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
        )

        self.report_slot = QWidget()
        self.report_slot.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        self.report_slot_layout = QVBoxLayout(self.report_slot)
        self.report_slot_layout.setContentsMargins(0, 0, 0, 0)
        self.report_slot_layout.setSpacing(0)
        self.report_slot_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
        )

        self.content_layout.addWidget(
            heading,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.content_layout.addSpacing(8)
        self.content_layout.addWidget(
            self.status_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.content_layout.addSpacing(30)
        self.content_layout.addWidget(
            self.report_slot,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        scroll_area.setWidget(scroll_content)

        page_layout.addWidget(header, 0)
        page_layout.addWidget(scroll_area, 1)

        root_layout.addWidget(self.sidebar, 0)
        root_layout.addWidget(content_page, 1)

        self.setLayout(root_layout)

    def set_report_data(self, report_data, status="completed"):
        self.report_data = report_data or {}
        self.status_value = str(status or "-").lower()

        self._update_status_label()
        self._refresh_report(self.report_data)

    def _update_status_label(self):
        self.status_label.setText(self.status_value.title())

        if self.status_value == "completed":
            object_name = "statusCompletedFull"
        elif self.status_value == "failed":
            object_name = "statusFailedFull"
        elif self.status_value == "cancelled":
            object_name = "statusCancelledFull"
        else:
            object_name = "statusDefaultFull"

        self.status_label.setObjectName(object_name)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.update()

    def _refresh_report(self, report_data):
        self._clear_report_slot()

        card_width = self._get_report_card_width(report_data)

        self.report_card = WorkoutReportCard(
            report_data=report_data,
            on_download=self.download_report_pdf,
        )
        self.report_card.setFixedWidth(card_width)
        self.report_card.setMinimumHeight(650)
        self.report_card.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self.recommendation_card = WorkoutRecommendationCard(
            report_data=report_data,
        )
        self.recommendation_card.setFixedWidth(card_width)
        self.recommendation_card.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Minimum,
        )

        self.report_slot_layout.addWidget(
            self.report_card,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.report_slot_layout.addSpacing(60)

        self.report_slot_layout.addWidget(
            self.recommendation_card,
            0,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

    def _clear_report_slot(self):
        while self.report_slot_layout.count():
            item = self.report_slot_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.report_card = None
        self.recommendation_card = None

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