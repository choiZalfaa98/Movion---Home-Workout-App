from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class BaseInfoPage(QWidget):
    def __init__(
          self, 
          pageType,
          icon_width,
          icon_height,
          icon_path, 
          heading,
          subheading=None, 
          buttons=None
    ):
      super().__init__()
      layout = QVBoxLayout(self)
      layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

      # --- ICON / VECTOR AVAILABILITY ---
      if icon_path:
        icon = QSvgWidget(str(icon_path))
        icon.setFixedSize(icon_width, icon_height)
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        if pageType == 1:
          layout.addSpacing(50)
        elif pageType == 2:
          layout.addSpacing(25)
        elif pageType == 3:
          layout.addSpacing(2)

      # --- HEADING TEXT AVAILABILITY ---
      if heading:
        title = QLabel(heading)
        title.setProperty("role","infoPageHeading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        if pageType == 1:
          layout.addSpacing(40)
        elif pageType == 2:
          layout.addSpacing(70)
        elif pageType == 3:
          layout.addSpacing(30)

      # --- SUBHEADING TEXT AVAILABILITY ---
      if subheading:
        subtitle = QLabel(subheading)
        subtitle.setObjectName("infoPageSubheading")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(35)

      # --- BUTTONS AVAILABILITY ---
      if buttons:
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.setSpacing(60)
        for btn in buttons:
          if pageType == 1:
            btn.setFixedWidth(80)
            btn.setProperty("role", "confirmButton")
          elif pageType == 2:
            btn.setFixedWidth(160)
            btn.setProperty("role", "confirmButton")
          elif pageType == 3:
            btn.setObjectName("confirmButtonReset")

          btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

class LogoutConfirmationPage(BaseInfoPage):
    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self):
      yes_btn = QPushButton("Yes")
      no_btn = QPushButton("No")
      super().__init__(
        1,
        466, 150,
        BASE_DIR / "assets" / "logo" / "logo_horizontal.svg",
        "Are you sure you want to log out?",
        buttons=[yes_btn, no_btn]
      )
      yes_btn.clicked.connect(self.confirmed.emit)
      no_btn.clicked.connect(self.cancelled.emit)

class EndWorkoutConfirmationPage(BaseInfoPage):
    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self):
      yes_btn = QPushButton("Yes")
      no_btn = QPushButton("No")
      super().__init__(
        1,
        466, 150,
        BASE_DIR / "assets" / "logo" / "logo_horizontal.svg",
        "Are you sure you want to end workout?",
        buttons=[yes_btn, no_btn]
      )
      yes_btn.clicked.connect(self.confirmed.emit)
      no_btn.clicked.connect(self.cancelled.emit)

class PauseWorkoutPage(BaseInfoPage):
    end_workout = pyqtSignal()
    continue_workout = pyqtSignal()

    def __init__(self):
      end_btn = QPushButton("End Workout")
      cont_btn = QPushButton("Continue Workout")
      super().__init__(
        2,
        150, 150,
        BASE_DIR / "assets" / "icons" / "pause.svg",
        "Pause",
        buttons=[end_btn, cont_btn]
      )
      end_btn.clicked.connect(self.end_workout.emit)
      cont_btn.clicked.connect(self.continue_workout.emit)

class ResetPasswordSentPage(BaseInfoPage):
    back_to_login = pyqtSignal()

    def __init__(self):
      back_to_login_btn = QPushButton("Back to Login Page")
      super().__init__(
        3,
        300, 300,
        BASE_DIR / "assets" / "icons" / "sent_mail.svg",
        "A password reset link has been sent to your email.",
        "Please check your inbox to reset your password",
        buttons=[back_to_login_btn]
      )
      back_to_login_btn.clicked.connect(self.back_to_login.emit)
