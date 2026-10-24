from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QFrame, QLabel, QComboBox, QGridLayout, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class FillPerson2Details(QWidget):
    generate_report = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout()

        page_title = QLabel("Workout Session")
        page_title.setProperty("role", "pageTitle")

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.addWidget(page_title, alignment=Qt.AlignmentFlag.AlignHCenter)

        heading = QLabel("Fill in Person2's Personal and Physical Details")
        heading.setObjectName("person2Heading")

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        person2_form = self.create_form_card()
        person2_form.setMaximumWidth(700)

        cta_btn = QPushButton("Generate Report")
        cta_btn.setObjectName("person2Button")
        cta_btn.setFixedSize(275, 40)
        cta_btn.clicked.connect(self.submit)

        content_layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(person2_form)
        content_layout.addWidget(cta_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        content_layout.setSpacing(50)

        root_layout.addWidget(header, 0)
        root_layout.addWidget(content_container, 1)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(root_layout)

    def create_form_card(self):
      card = QFrame()
      card.setProperty("role", "formCard")

      card_layout = QVBoxLayout(card)

      form_layout = QGridLayout()
      form_layout.setHorizontalSpacing(12)
      form_layout.setVerticalSpacing(10)

      # --- FORM INPUTS ---
      self.name_input = QLineEdit()
      self.name_input.setPlaceholderText("your name")

      self.age_input = QLineEdit()
      self.age_input.setPlaceholderText("your age in numeric")

      self.gender_input = QComboBox()
      self.gender_input.addItems(["Male", "Female"])

      self.height_input = QLineEdit()
      self.height_input.setPlaceholderText("your height in cm")

      self.weight_input = QLineEdit()
      self.weight_input.setPlaceholderText("your weight in kg")

      # --- FIELD DEFINITIONS ---
      fields = [
        ("Name", self.name_input),
        ("Age", self.age_input),
        ("Gender", self.gender_input),
        ("Height (cm)", self.height_input),
        ("Weight (kg)", self.weight_input),
      ]

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
      form_layout.setContentsMargins(10, 20, 10, 20)

      card_layout.addLayout(form_layout)

      return card

    def submit(self):
      name = self.name_input.text().strip()
      age = self.age_input.text().strip()
      gender = self.gender_input.currentText().strip().lower()
      height = self.height_input.text().strip()
      weight = self.weight_input.text().strip()

      if not all([name, age, height, weight]):
        QMessageBox.warning(
          self,
          "Incomplete Form",
          "Please fill in all fields before generating the report."
        )
        return

      try:
        age_value = int(age)
        height_cm = float(height)
        weight_kg = float(weight)
      except ValueError:
        QMessageBox.warning(
          self,
          "Invalid Data",
          "Age must be a whole number (ex: 20)\nHeight and weight must be decimal numbers (ex: 170.0, 65.2)"
        )
        return

      # --- PERSON2 DATA PAYLOAD ---
      person2 = {
        "id": None,
        "name": name,
        "age": age_value,
        "gender": gender,
        "height_cm": height_cm,
        "weight_kg": weight_kg,

        # Compatibility for existing CalorieCalculator
        "height": height_cm,
        "weight": weight_kg,
      }

      self.generate_report.emit(person2)
