from PyQt6.QtWidgets import (
    QFrame,
    QScrollArea,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy
)
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtQuickWidgets import QQuickWidget
from PyQt6.QtSvgWidgets import QSvgWidget
from pathlib import Path

from views.components.sidebar import Sidebar
from views.page_constants import Page
from services.dashboard_calculator import fetch_dashboard_stats, fetch_monthly_workout_frequency

BASE_DIR = Path(__file__).resolve().parent.parent

class HomePage(QWidget):
    go_to_workout = pyqtSignal()

    def __init__(self, navigate_func):
        super().__init__()

        root_layout = QHBoxLayout()

        # --- SIDEBAR ---
        self.sidebar = Sidebar(active_page=Page.HOME)
        self.navigate = navigate_func

        self.sidebar.navigate_requested.connect(self.navigate)
        
        # --- MAIN CONTENT ---
        content = QWidget()

        content_layout = QVBoxLayout()

        page_title = QLabel("Home")
        page_title.setProperty("role","pageTitle")

        # Area Scrollable: hero section, dashboard, faq
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_content.setProperty("role", "scrollContent")

        scroll_layout = QVBoxLayout()

        hero_section = HeroSection()
        hero_section.go_to_workout.connect(self.go_to_workout.emit)

        self.dashboard_section = DashboardSection()

        scroll_layout.addWidget(hero_section)
        scroll_layout.addWidget(self.dashboard_section)
        scroll_layout.addWidget(FaqSection())
        scroll_layout.setContentsMargins(46, 46, 46, 50)


        scroll_content.setLayout(scroll_layout)

        scroll_area.setWidget(scroll_content)
        scroll_layout.setSpacing(24)

        content_layout.addWidget(page_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(scroll_area)

        content.setLayout(content_layout)

        root_layout.addWidget(self.sidebar, 0)
        root_layout.addWidget(content, 1)

        root_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(root_layout)
    
    def set_user_id(self, user_id):
        self.user_id = user_id

        if hasattr(self, "dashboard_section"):
            self.dashboard_section.set_user_id(user_id)

# Hero Section
class HeroSection(QWidget):
    go_to_workout = pyqtSignal()

    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 80)
        main_layout.setSpacing(80)

        texts_content = QVBoxLayout()
        texts_content.setContentsMargins(0, 0, 0, 0)
        texts_content.setSpacing(30)
        texts_content.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        hero_heading = QLabel("Ready to start your workout?")
        hero_heading.setObjectName("heroHeading")
        hero_heading.setWordWrap(True)
        hero_heading.setContentsMargins(0, 0, 0, 0)

        hero_subheading = QLabel(
            "Track your movement, improve your posture, and complete every session with AI-powered guidance."
        )
        hero_subheading.setObjectName("heroSubheading")
        hero_subheading.setWordWrap(True)

        hero_subheading.setFixedWidth(750)
        hero_subheading.setMinimumHeight(64)
        hero_subheading.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Minimum
        )
        hero_subheading.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        hero_subheading.setContentsMargins(0, 0, 0, 0)

        hero_button = QPushButton("Start Workout")
        hero_button.setObjectName("heroButton")
        hero_button.setFixedSize(275, 40)
        hero_button.clicked.connect(self.go_to_workout.emit)

        texts_content.addWidget(hero_heading)
        texts_content.addWidget(hero_subheading)
        texts_content.addWidget(
            hero_button,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        hero_img_path = BASE_DIR / "assets" / "icons" / "person_workout.svg"
        hero_image = QSvgWidget(str(hero_img_path))
        hero_image.setFixedSize(210, 230)

        main_layout.addLayout(texts_content, 1)
        main_layout.addWidget(
            hero_image,
            0,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

# Dashboard Section
class DashboardSection(QWidget):
    def __init__(self):
        super().__init__()

        self.user_id = None

        main_layout = QVBoxLayout()

        heading = QLabel("Statistics")
        heading.setProperty("role", "heading2")

        stats_layout = QHBoxLayout()

        self.total_correct_reps_card, self.total_correct_reps_value = self.create_stat_card(
            "0%",
            "Correct Reps Rate"
        )

        self.total_cals_burnt_card, self.total_cals_burnt_value = self.create_stat_card(
            "0 kcal",
            "Total Calories Burnt"
        )

        self.total_workout_dur_card, self.total_workout_dur_value = self.create_stat_card(
            "0 hours",
            "Total Workout Duration"
        )

        stats_layout.addWidget(self.total_correct_reps_card)
        stats_layout.addWidget(self.total_cals_burnt_card)
        stats_layout.addWidget(self.total_workout_dur_card)
        stats_layout.setSpacing(80)

        graph_frame = QFrame()
        graph_frame.setObjectName("graphCard")

        graph_layout = QVBoxLayout()

        self.graph_title = QLabel("Workout Monthly Frequency")
        self.graph_title.setObjectName("chartTitle")

        self.chart_view = QQuickWidget()
        self.chart_view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.chart_view.setClearColor(QColor("#292D5E"))

        qml_path = BASE_DIR / "views" / "components" / "MonthlyFreq.qml"
        self.chart_view.setSource(QUrl.fromLocalFile(str(qml_path)))

        graph_layout.addWidget(self.graph_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        graph_layout.addWidget(self.chart_view)
        graph_frame.setLayout(graph_layout)

        main_layout.addWidget(heading)
        main_layout.addLayout(stats_layout)
        main_layout.addWidget(graph_frame)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(0, 0, 0, 80)

        self.setLayout(main_layout)
    
    def set_user_id(self, user_id):
        self.user_id = user_id
        self.load_dashboard_stats()
    
    def showEvent(self, event):
        super().showEvent(event)

        if self.user_id:
            self.load_dashboard_stats()

    def load_dashboard_stats(self):
        if not self.user_id:
            self.set_empty_stats()
            return

        result = fetch_dashboard_stats(self.user_id)

        if not result.get("success"):
            #print("[DASHBOARD_LOAD_FAILED]", result.get("error"))
            self.set_empty_stats()
            return

        stats = result.get("data", {})

        self.total_correct_reps_value.setText(
            stats.get("correct_reps_display", "0%")
        )

        self.total_cals_burnt_value.setText(
            stats.get("calories_display", "0 kcal")
        )

        self.total_workout_dur_value.setText(
            stats.get("duration_display", "0 hours")
        )

        self.load_monthly_frequency_chart()
    
    def load_monthly_frequency_chart(self):
        if not self.user_id:
            self.set_empty_chart()
            return

        result = fetch_monthly_workout_frequency(self.user_id)

        if not result.get("success"):
            #print("[MONTHLY_FREQ_LOAD_FAILED]", result.get("error"))
            self.set_empty_chart()
            return

        data = result.get("data", {}) or {}

        month_label = data.get("month_label", "")
        values = data.get("values", [0, 0, 0, 0])
        y_axis_max = data.get("y_axis_max", 7)

        self.graph_title.setText(
            f"Workout Monthly Frequency - {month_label}"
        )

        self.update_monthly_chart(
            values=values,
            y_axis_max=y_axis_max,
            month_label=month_label
        )

    def update_monthly_chart(self, values, y_axis_max=7, month_label=None):
        if not hasattr(self, "chart_view"):
            return

        root_object = self.chart_view.rootObject()

        if root_object is None:
            #print("[MONTHLY_CHART_ERROR] QML root object is None")
            return

        safe_values = list(values or [0, 0, 0, 0])[:4]

        while len(safe_values) < 4:
            safe_values.append(0)

        safe_values = [int(v or 0) for v in safe_values]

        root_object.setProperty("weekValues", safe_values)
        root_object.setProperty("yAxisMax", int(y_axis_max or 7))

        if month_label:
            root_object.setProperty("monthLabel", str(month_label))

        #print("[MONTHLY_CHART_UPDATED]", safe_values)

    def set_empty_chart(self):
        if hasattr(self, "graph_title"):
            self.graph_title.setText("Workout Monthly Frequency")

        self.update_monthly_chart(
            values=[0, 0, 0, 0],
            y_axis_max=7,
            month_label="No Data"
        )

    def set_empty_stats(self):
        self.total_correct_reps_value.setText("0%")
        self.total_cals_burnt_value.setText("0 kcal")
        self.total_workout_dur_value.setText("0 hours")

    def create_stat_card(self, value, title):
        card = QFrame()
        card.setObjectName("dashboardCard")

        layout = QHBoxLayout()

        value_label = QLabel(value)
        value_label.setProperty("role", "statValue")
        value_label.setWordWrap(True)
        value_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(title)
        title_label.setProperty("role", "statTitle")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(value_label)
        layout.setSpacing(10)
        layout.addWidget(title_label)

        card.setLayout(layout)

        return card, value_label

# FAQ
class FaqSection(QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QVBoxLayout()

        heading = QLabel("Frequently Asked Questions (FAQ)")
        heading.setProperty("role", "heading2")
        main_layout.addWidget(heading)

        faq_list_layout = QVBoxLayout()
        faq_list_layout.setSpacing(10)
        faq_list_layout.setContentsMargins(0, 0, 0, 0)
            
        faqs = [
            (
                "How does the app detect my workout moves?",
                "The app uses your camera and deep learning model (Attention-LSTM) to classify movements such as jumping jacks, squat, mountain climber, knee push up, and sit up."
            ),
            (
                "Can I use an external camera or phone camera",
                "Yes, you can select your preferred camera source before starting the workout."
            ),
            (
                "Does the app support multiple users at once?",
                "Yes, it supports up to 2 people in the same frame."
            ),
            (
                "Are my workout results saved?",
                "Yes, your workout results are stored in your account history."
            ),
            (
                "Can I download my workout report?",
                "Yes, reports can be exported in PDF format."
            ),
            (
                "How do I reset my password?",
                "Click \"Forgot Password\" on the Login Page, and check your email for a reset link."
            )
        ] 

        for question, answer in faqs:
            faq_list_layout.addWidget(self.create_faq_item(question, answer))

        faq_list_widget = QWidget()
        faq_list_widget.setLayout(faq_list_layout)
        
        main_layout.addWidget(faq_list_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(0, 0, 0, 20)

        self.setLayout(main_layout)

    
    def create_faq_item(self, question, answer):
        arrow_down_path = BASE_DIR / "assets" / "icons" / "arrow_down.svg"
        arrow_up_path = BASE_DIR / "assets" / "icons" / "arrow_up.svg"


        card = QFrame()
        card.setProperty("role", "accordion")
        card.setProperty("expanded", False)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QWidget()
        header.setCursor(Qt.CursorShape.PointingHandCursor)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header.setLayout(header_layout)

        question_label = QLabel(question)
        question_label.setProperty("role", "faqQuestion")

        arrow_label = QLabel()

        def set_arrow(is_up):
            arrow_label.setPixmap(
                QPixmap(str(arrow_up_path if is_up else arrow_down_path)).scaled(
                    20, 12,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        
        set_arrow(False)

        header_layout.addWidget(question_label)
        header_layout.addStretch()
        header_layout.addWidget(arrow_label)

        answer_label = QLabel(answer)
        answer_label.setProperty("role", "faqAnswer")
        answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        answer_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        answer_label.setWordWrap(True)
        answer_label.setVisible(False)

        def toggle():
            checked = not answer_label.isVisible()

            answer_label.setVisible(checked)

            card.setProperty("expanded", checked)
            card.style().unpolish(card)
            card.style().polish(card)

            set_arrow(checked)

        header.mousePressEvent = lambda e: toggle()

        layout.addWidget(header)
        layout.addWidget(answer_label)

        return card