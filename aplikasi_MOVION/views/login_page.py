from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QFrame, QLabel, QSizePolicy, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QIcon, QAction

from services.auth_service import login_user
from services.profile_service import get_profile
from services.session_service import save_session

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

logo_path = BASE_DIR / "assets" / "logo" / "logo_vertical.svg"

class LoginPage(QWidget):
    go_to_forgot = pyqtSignal()
    go_to_signup = pyqtSignal()
    go_to_home = pyqtSignal(str)
    go_to_setup = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout()

        left_side = QFrame()
        left_side.setProperty("role", "logoFrame")
        left_layout = QVBoxLayout(left_side)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QSvgWidget(str(logo_path))
        logo.setMaximumSize(346, 254)
        left_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        right_side = QWidget()
        right_layout = QVBoxLayout(right_side)

        login_container = QWidget()
        login_container.setMaximumWidth(500)
        
        login_layout = QVBoxLayout(login_container)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(40, 0, 40, 0)

        heading = QLabel("Log in to your account")
        heading.setObjectName("loginHeading")

        subheading = QLabel("Enter your email and password to recall your saved data")
        subheading.setObjectName("loginSubheading")

        # --- INPUT FIELDS (AUTH DATA ENTRY) ---
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

        self.eye_closed_icon = QIcon(str(BASE_DIR / "assets" / "icons" / "eye_closed.svg"))
        self.eye_open_icon   = QIcon(str(BASE_DIR / "assets" / "icons" / "eye_opened.svg"))

        self.toggle_action = QAction(self.eye_closed_icon, "Show/Hide", self.password_input)
        self.password_input.addAction(self.toggle_action, QLineEdit.ActionPosition.TrailingPosition)

        self.toggle_action.triggered.connect(self.toggle_password)

        login_btn = QPushButton("Log in with email")
        login_btn.setProperty("role", "authButton")
        login_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        login_btn.clicked.connect(self.handle_login)

        forgot_pass = QLabel("<a href='#' style='color:#B8C6FF; text-decoration: none;'>Forgot Password?</a>")
        forgot_pass.setObjectName("forgotPass")
        forgot_pass.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        forgot_pass.setOpenExternalLinks(False)
        forgot_pass.linkActivated.connect(lambda _: self.go_to_forgot.emit())

        to_signup = QLabel("Don't have an account? <a href='#' style='color:#B8C6FF;'>Sign Up</a>")
        to_signup.setObjectName("authChangingPage")
        to_signup.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        to_signup.setOpenExternalLinks(False)
        to_signup.linkActivated.connect(lambda _: self.go_to_signup.emit())

        rightL_alignment = Qt.AlignmentFlag.AlignHCenter

        form_layout.addWidget(self.email_input)
        form_layout.addSpacing(6)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(8)
        form_layout.addWidget(login_btn)
        form_layout.addSpacing(2)
        form_layout.addWidget(forgot_pass, alignment=Qt.AlignmentFlag.AlignRight)

        login_layout.addWidget(heading, alignment=rightL_alignment)
        login_layout.addSpacing(10)
        login_layout.addWidget(subheading, alignment=rightL_alignment)
        login_layout.addSpacing(20)
        login_layout.addWidget(form_container)
        login_layout.addSpacing(70)
        login_layout.addWidget(to_signup, alignment=rightL_alignment)

        right_layout.addWidget(
            login_container,
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
        
    def handle_login(self):
        email = self.email_input.text()
        password = self.password_input.text()

        if not email or not password:
            QMessageBox.warning(
                self,
                "Login Failed",
                "Email and password cannot be empty"
            )

            return

        result = login_user(
            email,
            password
        )
        
        if not result["success"]:
            QMessageBox.warning(
                self,
                "Login Failed",
                result["error"]
            )

            return
        
        user_id = result["user"].id
        profile = get_profile(user_id)

        if not profile["success"]:
            QMessageBox.warning(
                self,
                "Login Failed",
                profile["error"]
            )
            return

        if profile["exists"]:
            save_session(result["session"])
            self.go_to_home.emit(user_id)
        else:
            self.go_to_setup.emit(user_id)