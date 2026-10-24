from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QSizePolicy, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget

from services.auth_service import reset_password

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

logo_path = BASE_DIR / "assets" / "logo" / "logo_horizontal.svg"

class ForgotPassword(QWidget):
    go_to_email_sent = pyqtSignal()
    back_to_login = pyqtSignal()

    def __init__(self):
        super().__init__()

        main_layout = QVBoxLayout()

        form_container = QWidget()
        form_container.setMaximumWidth(1000)
        
        form_layout = QVBoxLayout(form_container)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QSvgWidget(str(logo_path))
        logo.setMaximumSize(220, 74)

        heading = QLabel("Forgot Your Password?")
        heading.setObjectName("forgotPassHeading")

        subheading = QLabel("Enter your email to reset your password")
        subheading.setObjectName("forgotPassSubheading")

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@domain.com")
        self.email_input.setObjectName("emailForgotPass")
        self.email_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        reset_btn = QPushButton("Reset Password")
        reset_btn.setProperty("role", "authButton")
        reset_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        reset_btn.clicked.connect(self.handle_reset_password)

        to_login = QLabel("<a href='#' style='color:#B8C6FF;'>Back to Login Page</a>")
        to_login.setObjectName("backToLogin")
        to_login.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        to_login.setOpenExternalLinks(False)
        to_login.linkActivated.connect(lambda _: self.back_to_login.emit())

        rightL_alignment = Qt.AlignmentFlag.AlignHCenter

        form_layout.addWidget(logo, alignment=rightL_alignment)
        form_layout.addSpacing(30)
        form_layout.addWidget(heading, alignment=rightL_alignment)
        form_layout.addSpacing(8)
        form_layout.addWidget(subheading, alignment=rightL_alignment)
        form_layout.addSpacing(16)
        form_layout.addWidget(self.email_input)
        form_layout.addSpacing(8)
        form_layout.addWidget(reset_btn)
        form_layout.addSpacing(50)
        form_layout.addWidget(to_login, alignment=rightL_alignment)        

        main_layout.addWidget(form_container, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(main_layout)

    def handle_reset_password(self):
        email = self.email_input.text().strip()

        if not email:
            QMessageBox.warning(
                self, 
                "Reset Failed",
                "Email cannot be empty"
            )
            return
        
        if "@" not in email or "." not in email:
            QMessageBox.warning(
                self, 
                "Reset Failed",
                "Please enter a valid email address"
            )
            return
        
        result = reset_password(email)
        if result["success"]:
            self.go_to_email_sent.emit()
        else:
            QMessageBox.warning(
                self,
                "Reset Failed",
                f"Could not send reset email: {result['error']}"
            )