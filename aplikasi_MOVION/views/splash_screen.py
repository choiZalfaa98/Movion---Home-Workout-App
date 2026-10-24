from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import Qt

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

logo_path = BASE_DIR.parent / "assets" / "logo" / "logo_horizontal.svg"

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("splashScreen")
        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True
        )

        layout = QVBoxLayout()

        logo = QSvgWidget(str(logo_path))
        logo.setFixedSize(800, 258)

        self.loading_label = QLabel("Initializing...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setObjectName("loadingText")

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 100)
        self.loading_bar.setValue(0)
        self.loading_bar.setFixedWidth(600)
        self.loading_bar.setObjectName("loadingBar")
        self.loading_bar.setTextVisible(False)

        layout.addStretch()

        layout.addWidget(
            logo,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        layout.addSpacing(50)

        layout.addWidget(
            self.loading_label,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        layout.addSpacing(16)

        layout.addWidget(
            self.loading_bar,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        layout.addStretch()

        self.setLayout(layout)

    def set_loading_progress(self, value, text=None):
        safe_value = max(0, min(100, int(value)))
        self.loading_bar.setValue(safe_value)

        if text:
            self.loading_label.setText(text)