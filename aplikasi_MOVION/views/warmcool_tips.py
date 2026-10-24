from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolButton
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtSvgWidgets import QSvgWidget

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

back_icon_path = BASE_DIR / "assets" / "icons" / "back_or_pause.svg"
stretching_path = BASE_DIR / "assets" / "icons" / "stretching.svg"

class WarmCoolPage(QWidget):
    back_to_preview = pyqtSignal()
    go_to_session = pyqtSignal()

    def __init__(self):
      super().__init__()

      root_layout = QVBoxLayout()
        
      header = QWidget()
      header_layout = QHBoxLayout(header)

      back_btn = QToolButton()
      back_btn.setText("Back")
      back_btn.setProperty("role", "backPauseButton")
      back_icon = QIcon(str(back_icon_path))
      back_btn.setIcon(back_icon)
      back_btn.setIconSize(QSize(18, 18))
      back_btn.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextBesideIcon 
      )
      back_btn.clicked.connect(lambda: self.back_to_preview.emit())

      page_title = QLabel("Workout Session")
      page_title.setProperty("role", "pageTitle")
      page_title.setContentsMargins(0, 0, 80, 0)

      header_layout.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
      header_layout.addStretch()
      header_layout.addWidget(page_title, alignment=Qt.AlignmentFlag.AlignHCenter)
      header_layout.addStretch()

      content = QWidget()
      content_layout = QVBoxLayout(content)
      content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

      stretching_img = QSvgWidget(str(stretching_path))
      stretching_img.setFixedSize(250, 250)

      subheading = QLabel("Warm-up before you begin, cool-off after you finish")
      subheading.setObjectName("warmcoolSubheading")

      text = QLabel("Dynamic stretches first, statics stretches after")
      text.setObjectName("warmcoolText")

      cta_btn = QPushButton("Start Workout")
      cta_btn.setProperty("role", "button1")
      cta_btn.setFixedSize(275, 40)
      cta_btn.clicked.connect(lambda: self.go_to_session.emit())

      content_layout.addWidget(stretching_img, alignment=Qt.AlignmentFlag.AlignHCenter)
      content_layout.addSpacing(40)
      content_layout.addWidget(subheading, alignment=Qt.AlignmentFlag.AlignHCenter)
      content_layout.addSpacing(10)
      content_layout.addWidget(text, alignment=Qt.AlignmentFlag.AlignHCenter)
      content_layout.addSpacing(60)
      content_layout.addWidget(cta_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

      root_layout.addWidget(header, 0)
      root_layout.addWidget(content, 1)
      root_layout.setContentsMargins(0, 0, 0, 0)

      self.setLayout(root_layout)