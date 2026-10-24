from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QFrame, QLabel, QSizePolicy, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QIcon, QAction

from services.auth_service import signup_user

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

logo_path = BASE_DIR / "assets" / "logo" / "logo_vertical.svg"

class SignUp(QWidget):
    go_to_setup = pyqtSignal(str)
    go_to_login = pyqtSignal()

    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout()

        right_side = QFrame()
        right_side.setProperty("role", "logoFrame")
        right_layout = QVBoxLayout(right_side)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QSvgWidget(str(logo_path))
        logo.setMaximumSize(346, 254)
        right_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        left_side = QWidget()
        left_layout = QVBoxLayout(left_side)

        signup_container = QWidget()
        signup_container.setMaximumWidth(550)
        
        signup_layout = QVBoxLayout(signup_container)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(64, 0, 64, 0)

        heading = QLabel("Create an account")
        heading.setObjectName("signupHeading")

        subheading = QLabel("Enter your email and password to save all of your data in one grip")
        subheading.setObjectName("signupSubheading")

        # --- INPUT FIELDS ---
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@domain.com")
        self.email_input.setProperty("role", "authForm")
        self.email_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setProperty("role", "authForm")
        self.password_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        # --- PASSWORD TOGGLE ACTION ---
        self.eye_closed_icon = QIcon(str(BASE_DIR / "assets" / "icons" / "eye_closed.svg"))
        self.eye_open_icon   = QIcon(str(BASE_DIR / "assets" / "icons" / "eye_opened.svg"))

        self.toggle_action = QAction(self.eye_closed_icon, "Show/Hide", self.password_input)
        self.password_input.addAction(self.toggle_action, QLineEdit.ActionPosition.TrailingPosition)

        self.toggle_action.triggered.connect(self.toggle_password)

        signup_btn = QPushButton("Sign up with email")
        signup_btn.setProperty("role", "authButton")
        signup_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        signup_btn.clicked.connect(self.handle_signup)

        to_login = QLabel("Already have an account? <a href='#' style='color:#B8C6FF;'>Log In</a>")
        to_login.setObjectName("authChangingPage")
        to_login.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        to_login.setOpenExternalLinks(False)
        to_login.linkActivated.connect(lambda _: self.go_to_login.emit())

        rightL_alignment = Qt.AlignmentFlag.AlignHCenter
        form_layout.addWidget(self.email_input)
        form_layout.addSpacing(6)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(8)
        form_layout.addWidget(signup_btn)

        signup_layout.addWidget(heading, alignment=rightL_alignment)
        signup_layout.addSpacing(10)
        signup_layout.addWidget(subheading, alignment=rightL_alignment)
        signup_layout.addSpacing(20)
        signup_layout.addWidget(form_container)
        signup_layout.addSpacing(70)
        signup_layout.addWidget(to_login, alignment=rightL_alignment)

        left_layout.addWidget(
            signup_container,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        main_layout.addWidget(left_side, 1)
        main_layout.addWidget(right_side, 1)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(main_layout)

    def toggle_password(self):
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_action.setIcon(self.eye_open_icon)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_action.setIcon(self.eye_closed_icon)
    
    def handle_signup(self):
        email = self.email_input.text()
        password = self.password_input.text()

        if not email or not password:
            QMessageBox.warning(
                self,
                "Error",
                "Email and password cannot be empty"
            )
            return

        result = signup_user(
            email,
            password
        )

        if result["success"]:
            user_id = result["user"].id

            QMessageBox.information(
                self,
                "Success",
                "Account created!"
            )

            self.go_to_setup.emit(user_id)

        else:
            QMessageBox.warning(
                self,
                "Signup Failed",
                result["error"]
            )