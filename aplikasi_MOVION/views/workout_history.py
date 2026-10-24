from PyQt6.QtWidgets import QFrame, QScrollArea, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtSvgWidgets import QSvgWidget

from views.components.sidebar import Sidebar
from views.page_constants import Page

from services.session_service import get_current_session
from services.workout_report_service import get_workout_history

from pathlib import Path
from datetime import datetime
import json
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent

clock_path = BASE_DIR / "assets" / "icons" / "clock.svg"

WIB = ZoneInfo("Asia/Jakarta")

class WorkoutHistory(QWidget):
    def __init__(self, navigate_func):
        super().__init__()

        self.navigate = navigate_func
        self.current_filter = None

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = Sidebar(active_page=Page.WORKOUT_HISTORY)
        self.sidebar.navigate_requested.connect(self.navigate)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        page_title = QLabel("History")
        page_title.setProperty("role", "pageTitle")

        filter_container = self.create_filter_section()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setProperty("role", "scrollContent")

        self.history_layout = QVBoxLayout(self.scroll_content)
        self.history_layout.setContentsMargins(46, 24, 46, 50)
        self.history_layout.setSpacing(24)

        self.scroll_area.setWidget(self.scroll_content)

        content_layout.addWidget(
            page_title,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        content_layout.addWidget(filter_container, 0)
        content_layout.addWidget(self.scroll_area, 1)

        root_layout.addWidget(self.sidebar, 0)
        root_layout.addWidget(content, 1)

        self.setLayout(root_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_history_from_supabase(self.current_filter)

    def create_filter_section(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(46, 24, 46, 24)
        layout.setSpacing(16)

        filter_header = QLabel("Workout History")
        filter_header.setProperty("role", "heading2")

        card_container = QWidget()
        card_layout = QHBoxLayout(card_container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(20)

        self.all_filter = QPushButton("All")
        self.all_filter.setProperty("role", "filterCard")
        self.all_filter.clicked.connect(
            lambda: self.apply_filter(None)
        )

        self.single_filter = QPushButton("Single Person")
        self.single_filter.setProperty("role", "filterCard")
        self.single_filter.clicked.connect(
            lambda: self.apply_filter("single")
        )

        self.multi_filter = QPushButton("Multi Person")
        self.multi_filter.setProperty("role", "filterCard")
        self.multi_filter.clicked.connect(
            lambda: self.apply_filter("multi")
        )

        card_layout.addWidget(self.all_filter)
        card_layout.addWidget(self.single_filter)
        card_layout.addWidget(self.multi_filter)
        card_layout.addStretch()

        layout.addWidget(filter_header)
        layout.addWidget(card_container)

        return container

    def apply_filter(self, mode):
        self.current_filter = mode
        #print("[HISTORY_FILTER]", mode)
        self.load_history_from_supabase(mode)

    def load_history_from_supabase(self, mode=None):
        self.clear_history()

        auth_session = get_current_session()

        if not auth_session or not auth_session.user:
            self._show_empty_message("User session not found.")
            return

        result = get_workout_history(
            user_id=auth_session.user.id,
            mode=mode,
        )

        if not result["success"]:
            self._show_empty_message(
                f"Failed to load workout history: {result['error']}"
            )
            return

        rows = result.get("data", []) or []

        if not rows:
            self._show_empty_message("No workout history yet.")
            return

        grouped = {}

        for row in rows:
            item = self._map_supabase_row_to_history_item(row)
            month = item["month"]

            if month not in grouped:
                grouped[month] = []

            grouped[month].append(item)

        for month, items in grouped.items():
            month_section = self.create_monthly_history(
                month=month,
                items=items,
            )
            self.history_layout.addWidget(month_section)

        self.history_layout.addStretch()

    def _map_supabase_row_to_history_item(self, row):
        started_at = row.get("started_at") or row.get("created_at")
        ended_at = row.get("ended_at")

        dt = self._parse_datetime(started_at)

        month = dt.strftime("%B %Y") if dt else "-"
        date_text = dt.strftime("%d %B %Y") if dt else "-"

        mode = row.get("mode", "single")
        status = str(row.get("status", "-") or "-").lower()

        report_data = self._extract_report_data(row)

        users_data = report_data.get("users", []) or []
        users = [
            user.get("name", "User")
            for user in users_data
            if user.get("name")
        ]

        if not users:
            participants = self._as_list(row.get("workout_participants"))
            users = [
                participant.get("name", "User")
                for participant in participants
                if participant.get("name")
            ]

        if not users:
            users = ["User"]

        duration = self._extract_duration(
            report_data=report_data,
            started_at=started_at,
            ended_at=ended_at,
        )

        return {
            "id": row.get("id"),
            "month": month,
            "date": date_text,
            "duration": duration,
            "mode": mode,
            "mode_label": "Multi Person" if mode == "multi" else "Single Person",
            "users": users,
            "status": status,
            "report_data": report_data,
        }

    def _extract_report_data(self, row):
        reports = self._as_list(row.get("workout_reports"))

        if not reports:
            return {}

        report_row = reports[0] or {}
        report_data = report_row.get("report_data") or {}

        if isinstance(report_data, dict):
            return report_data

        if isinstance(report_data, str):
            try:
                parsed = json.loads(report_data)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}

        return {}

    def _extract_duration(self, report_data, started_at=None, ended_at=None):
        users_data = report_data.get("users", []) or []

        if users_data:
            duration = users_data[0].get("duration")
            if duration:
                return str(duration)

        start_dt = self._parse_datetime(started_at)
        end_dt = self._parse_datetime(ended_at)

        if not start_dt or not end_dt:
            return "00:00:00"

        total_seconds = int((end_dt - start_dt).total_seconds())

        if total_seconds < 0:
            total_seconds = 0

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _parse_datetime(self, value):
        if not value:
            return None

        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=WIB)

            return dt.astimezone(WIB)
        except ValueError:
            return None

    def _as_list(self, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            return [value]

        return []

    def clear_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

    def _show_empty_message(self, message):
        label = QLabel(message)
        label.setObjectName("historyMessage")
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.history_layout.addWidget(label)
        self.history_layout.addStretch()

    def create_monthly_history(self, month, items):
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 40)
        section_layout.setSpacing(12)

        month_label = QLabel(month)
        month_label.setProperty("role", "heading3")

        section_layout.addWidget(month_label)

        for item in items:
            card = self.create_history_preview_card(item)
            section_layout.addWidget(card)

        return section

    def create_history_preview_card(self, item):
        preview_history = QFrame()
        preview_history.setObjectName("previewHistoryCard")
        preview_history.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        preview_hist_layout = QHBoxLayout(preview_history)
        preview_hist_layout.setContentsMargins(30, 20, 30, 22)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        date = QLabel(item.get("date", "-"))
        date.setObjectName("historyDate")

        duration_row = QWidget()
        duration_layout = QHBoxLayout(duration_row)
        duration_layout.setContentsMargins(0, 0, 0, 0)
        duration_layout.setSpacing(10)

        clock_icon = QSvgWidget(str(clock_path))
        clock_icon.setFixedSize(26, 26)

        duration_label = QLabel(item.get("duration", "00:00:00"))
        duration_label.setObjectName("historyDuration")

        duration_layout.addWidget(clock_icon)
        duration_layout.addWidget(duration_label)

        left_layout.addWidget(date)
        left_layout.addStretch()
        left_layout.addWidget(duration_row)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        mode = item.get("mode", "single")

        if mode == "multi":
            icon_path = BASE_DIR / "assets" / "icons" / "multi_icon.svg"
        else:
            icon_path = BASE_DIR / "assets" / "icons" / "single_icon.svg"

        icon = QSvgWidget(str(icon_path))
        icon.setFixedHeight(40)
        icon.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        tracking_title = QLabel(item.get("mode_label", "Single Person"))
        tracking_title.setObjectName("historyMode")

        users = QLabel(" • ".join(item.get("users", [])))
        users.setObjectName("historyUsers")

        alignment_items = Qt.AlignmentFlag.AlignHCenter

        center_layout.addWidget(icon, alignment=alignment_items)
        center_layout.addWidget(tracking_title, alignment=alignment_items)
        center_layout.addWidget(users, alignment=alignment_items)
        center_layout.setSpacing(14)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        status_value = str(item.get("status", "-") or "-").lower()
        status = QLabel(status_value.title())

        if status_value == "completed":
            status.setObjectName("statusCompleted")
        elif status_value == "failed":
            status.setObjectName("statusFailed")
        elif status_value == "cancelled":
            status.setObjectName("statusCancelled")
        else:
            status.setObjectName("statusDefault")

        if item.get("report_data"):
            full_report = QLabel(
                "<a href='#' style='color:#B8C6FF;'>Full Report</a>"
            )
            full_report.setObjectName("historyToFull")
            full_report.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            full_report.setOpenExternalLinks(False)
            full_report.linkActivated.connect(
                lambda _link, data=item: self.open_full_report(data)
            )
        else:
            full_report = QLabel("No Report")
            full_report.setObjectName("historyToFull")

        right_layout.addWidget(status, alignment=Qt.AlignmentFlag.AlignRight)
        right_layout.addStretch()
        right_layout.addWidget(full_report, alignment=Qt.AlignmentFlag.AlignRight)

        preview_hist_layout.addWidget(left_widget)
        preview_hist_layout.addStretch()
        preview_hist_layout.addWidget(center_widget)
        preview_hist_layout.addStretch()
        preview_hist_layout.addWidget(right_widget)

        return preview_history

    def open_full_report(self, item):
        full_page = self.window().pages[Page.WORKOUT_HISTORY_FULL]

        report_data = item.get("report_data", {})
        status = item.get("status", "-")

        full_page.set_report_data(
            report_data=report_data,
            status=status,
        )

        self.navigate(Page.WORKOUT_HISTORY_FULL)