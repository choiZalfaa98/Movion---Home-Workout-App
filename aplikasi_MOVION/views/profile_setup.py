from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QFrame, QLabel, QSizePolicy, QComboBox, QGridLayout, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget

from services.profile_service import create_profile

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

logo_path = BASE_DIR / "assets" / "logo" / "logo_vertical.svg"

class ProfileSetup(QWidget):
    continue_to_login = pyqtSignal()
    
    def __init__(self):
        super().__init__()

        self.user_id = None

        self.name_input = None
        self.age_input = None
        self.gender_input = None
        self.height_input = None
        self.weight_input = None

        root_layout = QVBoxLayout()

        heading = QLabel("Fill with your personal data")
        heading.setObjectName("setupHeading")

        subheading = QLabel("This data will be used for calorie burn estimation after the workout session is completed")
        subheading.setObjectName("setupSubheading")

        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        logo_layout = QVBoxLayout()

        
        personal_form = self.create_form_card("Personal")
        physical_form = self.create_form_card("Physical")

        notice = QLabel("*Data can be changed anytime on <span style='font-weight:700;'>Profile Page</span>")
        notice.setObjectName("notice")
        
        logo = QSvgWidget(str(logo_path))
        logo.setMaximumSize(300, 220)

        cta_btn = QPushButton("Continue to Log in")
        cta_btn.setObjectName("setupButton")
        cta_btn.setFixedSize(275, 40)
        cta_btn.clicked.connect(self.save_profile)

        form_layout.addWidget(personal_form)
        form_layout.addSpacing(30)
        form_layout.addWidget(physical_form)
        form_layout.addStretch()
        form_layout.addWidget(notice, alignment=Qt.AlignmentFlag.AlignRight)

        logo_layout.addStretch()
        logo_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        logo_layout.addStretch()
        logo_layout.addWidget(cta_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        content_layout.addLayout(form_layout, 2)
        content_layout.addSpacing(50)
        content_layout.addLayout(logo_layout, 1)

        root_layout.addWidget(heading)
        root_layout.addSpacing(10)
        root_layout.addWidget(subheading)
        root_layout.addSpacing(50)
        root_layout.addWidget(content_container)
        root_layout.setContentsMargins(50, 50, 50, 50)
        
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setLayout(root_layout)

    def set_user_id(self, user_id):
      self.user_id = user_id

    def create_form_card(self, form_type: str) -> QWidget:
      
      container = QWidget()
      container_layout = QVBoxLayout(container)
      container_layout.setContentsMargins(0, 0, 0, 0)
      container_layout.setSpacing(8)

      heading = QLabel(f"{form_type} Details")
      heading.setObjectName("formHeading")
    
      card = QFrame()
      card.setProperty("role", "formCard")

      card_layout = QVBoxLayout(card)
      card_layout.setContentsMargins(20, 20, 20, 20)
   
      form_layout = QGridLayout()
      form_layout.setHorizontalSpacing(12)
      form_layout.setVerticalSpacing(10)

      # --- PERSONAL DATA FIELDS ---
      if form_type.lower() == "personal":
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("your name")

        self.age_input = QLineEdit()
        self.age_input.setPlaceholderText("your age in numeric")

        self.gender_input = QComboBox()
        self.gender_input.addItems(["Male", "Female"])

        fields = [
            ("Name", self.name_input),
            ("Age", self.age_input),
            ("Gender", self.gender_input),
        ]

      # --- PHYSICAL DATA FIELDS ---
      elif form_type.lower() == "physical":
        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("your height in cm")

        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("your weight in kg")

        fields = [
            ("Height (cm)", self.height_input),
            ("Weight (kg)", self.weight_input),
        ]
      
      # --- FORM ROWS RENDERING ---
      for row, (label_text, widget) in enumerate(fields):
        label = QLabel(label_text)
        label.setProperty("role", "formLabel")
        label.setFixedWidth(100)

        colon = QLabel(":")
        colon.setProperty("role", "formLabel")

        widget.setProperty("role", "formValue")

        form_layout.addWidget(label, row, 0)
        form_layout.addWidget(colon, row, 1)
        form_layout.addWidget(widget, row, 2)

      form_layout.setColumnStretch(2, 1)

      card_layout.addLayout(form_layout)
    
      container_layout.addWidget(heading)
      container_layout.addWidget(card)

      container.setContentsMargins(0, 0, 0, 0)

      return container
    
    def save_profile(self):
      if self.user_id is None:
        QMessageBox.warning(
            self,
            "Error",
            "User ID not found. Please try signing up again"
        )
        return

      # --- DATA PARSING + VALIDATION ===
      try:
        data = {
          "id": self.user_id,
          "name": self.name_input.text(),
          "age": int(self.age_input.text()),
          "gender": self.gender_input.currentText().lower(),
          "height_cm": float(self.height_input.text()),
          "weight_kg": float(self.weight_input.text())
        }
      except ValueError:
        QMessageBox.warning(
          self,
          "Invalid Data",
          "Age must be a whole number (ex: 20)\nHeight and weight must be decimal numbers (ex: 170.0, 65.2)"
        )

        return

      # --- EMPTY FIELDS CHECK ---
      if (
        not self.name_input.text()
        or not self.age_input.text()
        or not self.height_input.text()
        or not self.weight_input.text()
      ):
        QMessageBox.warning(
          self,
          "Error",
          "Please fill all fields"
        )
        return

      result = create_profile(data)

      if result["success"]:
        QMessageBox.information(
            self,
            "Success",
            "Profile saved!"
        )

        self.continue_to_login.emit()

      else:
        QMessageBox.warning(
            self,
            "Error",
            result["error"]
        )