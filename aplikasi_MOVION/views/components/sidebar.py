from PyQt6.QtWidgets import QFrame, QVBoxLayout, QToolButton, QButtonGroup
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QSize, pyqtSignal

from views.page_constants import Page

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ICONS_DIR = BASE_DIR / "assets" / "icons"

logo_path = BASE_DIR / "assets" / "logo" / "logo_without_text2.svg"

class Sidebar(QFrame):
    navigate_requested = pyqtSignal(str)

    def __init__(self, active_page=None):
        super().__init__()

        self.setObjectName("sidebar")
        self.setFixedWidth(75)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        self.logo = QSvgWidget(str(logo_path))
        self.logo.setFixedSize(46, 46)

        # --- SIDEBAR MENU BUTTONS ---
        self.home_btn = self.create_nav_button(
            "Home",
            ICONS_DIR / "home.svg"
        )

        self.workout_btn = self.create_nav_button(
            "Workout",
            ICONS_DIR / "workout.svg"
        )

        self.history_btn = self.create_nav_button(
            "History",
            ICONS_DIR / "history.svg"
        )

        self.profile_btn = self.create_nav_button(
            "Profile",
            ICONS_DIR / "profile.svg"
        )

        self.nav_group = QButtonGroup()
        self.nav_group.setExclusive(True)

        self.nav_group.addButton(self.home_btn)
        self.nav_group.addButton(self.workout_btn)
        self.nav_group.addButton(self.history_btn)
        self.nav_group.addButton(self.profile_btn)

        self.button_pages = {
            self.home_btn: Page.HOME,
            self.workout_btn: Page.WORKOUT_PREVIEW,
            self.history_btn: Page.WORKOUT_HISTORY,
            self.profile_btn: Page.PROFILE,
        }

        self.nav_group.buttonClicked.connect(self.handle_navigation)

        # --- BUTTON CHECKED ON ACTIVE PAGE ---
        if active_page == Page.HOME:
            self.home_btn.setChecked(True)
        elif active_page == Page.WORKOUT_PREVIEW:
            self.workout_btn.setChecked(True)
        elif active_page == Page.TRACKING_MODE:
            self.workout_btn.setChecked(True)
        elif active_page == Page.WORKOUT_HISTORY:
            self.history_btn.setChecked(True)
        elif active_page == Page.WORKOUT_HISTORY_FULL:
            self.history_btn.setChecked(True)
        elif active_page == Page.PROFILE:
            self.profile_btn.setChecked(True)

        layout.addSpacing(2)
        layout.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        centerH_align = Qt.AlignmentFlag.AlignHCenter
        layout.addWidget(self.home_btn, alignment=centerH_align)
        layout.addWidget(self.workout_btn, alignment=centerH_align)
        layout.addWidget(self.history_btn, alignment=centerH_align)
        layout.addWidget(self.profile_btn, alignment=centerH_align)

        layout.addStretch()

        #print("SIDEBAR CREATED:", active_page)

        self.setLayout(layout)

    def create_nav_button(self, text, icon_path):
        btn = QToolButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn.setText(text)
        btn.setIcon(QIcon(str(icon_path)))

        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        btn.setIconSize(QSize(24, 24))
        btn.setFixedSize(60, 60)

        btn.setAutoRaise(True)
        btn.setCheckable(True)

        return btn

    def handle_navigation(self, button):
        page = self.button_pages[button]

        #print("SIDEBAR ->", page)

        button.setChecked(True)

        self.navigate_requested.emit(page)

    def set_active_page(self, page_name):
        for btn, page in self.button_pages.items():
            btn.setChecked(page == page_name)
