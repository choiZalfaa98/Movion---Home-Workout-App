from PyQt6.QtWidgets import (
    QFrame,
    QScrollArea,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QGridLayout,
    QLineEdit,
    QComboBox,
    QFileDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QColor, QPen

from pathlib import Path
import requests
import mimetypes
import os
import uuid

from views.components.sidebar import Sidebar
from views.page_constants import Page
from services.profile_service import get_avatar_path, get_profile, update_avatar_url, update_profile, get_email


BASE_DIR = Path(__file__).resolve().parent.parent


class ProfilePage(QWidget):
    go_to_logout = pyqtSignal()

    def __init__(self, navigate_func):
      super().__init__()

      root_layout = QHBoxLayout()

      # --- SIDEBAR ---
      self.sidebar = Sidebar(active_page=Page.PROFILE)
      self.navigate = navigate_func
      self.user_id = None

      self.sidebar.navigate_requested.connect(self.navigate)
        
      # --- MAIN CONTENT ---
      content = QWidget()
      content_layout = QVBoxLayout()

      page_title = QLabel("Profile")
      page_title.setProperty("role", "pageTitle")

      scroll_area = QScrollArea()
      scroll_area.setWidgetResizable(True)
      scroll_area.setFrameShape(QFrame.Shape.NoFrame)

      scroll_content = QWidget()
      scroll_content.setProperty("role", "scrollContent")

      scroll_layout = QVBoxLayout()

      account_card = self.create_acc_card()

      self.is_editing = False
      details_form = self.create_details_form()

      scroll_layout.addWidget(account_card)
      scroll_layout.addWidget(details_form)
      scroll_layout.setSpacing(80)

      scroll_layout.setContentsMargins(46, 46, 46, 50)

      scroll_content.setLayout(scroll_layout)
      scroll_area.setWidget(scroll_content)

      content_layout.addWidget(
        page_title,
        alignment=Qt.AlignmentFlag.AlignHCenter
      )
      content_layout.addWidget(scroll_area)

      content.setLayout(content_layout)

      root_layout.addWidget(self.sidebar, 0)
      root_layout.addWidget(content, 1)
      root_layout.setContentsMargins(0, 0, 0, 0)

      self.setLayout(root_layout)
    
    def circular_pixmap(self, pixmap: QPixmap, size, border_color="#3A3A3A", border_width=2):
      if pixmap.isNull():
         fallback = QPixmap(size, size)
         fallback.fill(Qt.GlobalColor.lightGray)
         return fallback

      scaled = pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
      )

      result = QPixmap(size, size)
      result.fill(Qt.GlobalColor.transparent)

      painter = QPainter(result)
      painter.setRenderHint(QPainter.RenderHint.Antialiasing)

      radius = border_width // 2

      path = QPainterPath()
      path.addEllipse(radius, radius, size - border_width, size - border_width)

      painter.setClipPath(path)

      x = (size - scaled.width()) // 2
      y = (size - scaled.height()) // 2

      painter.drawPixmap(x, y, scaled)

      painter.setClipping(False)

      pen = QPen(QColor(border_color))
      pen.setWidth(border_width)

      painter.setPen(pen)
      painter.setBrush(Qt.BrushStyle.NoBrush)

      painter.drawEllipse(radius, radius, size - border_width, size - border_width)

      painter.end()

      return result

    def load_profile_pic(self, user_id: str, size: int) -> QPixmap:
        avatar_url = get_avatar_path(user_id)

        if not avatar_url:
          pixmap = QPixmap(size, size)
          pixmap.fill(Qt.GlobalColor.lightGray)
          return self.circular_pixmap(pixmap, size)

        try:
          resp = requests.get(avatar_url)
          if resp.status_code == 200:
            pixmap = QPixmap()
            pixmap.loadFromData(resp.content)
          else:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.lightGray)
        except Exception:
          pixmap = QPixmap(size, size)
          pixmap.fill(Qt.GlobalColor.lightGray)


        return self.circular_pixmap(pixmap, size)

    def change_photo(self, size: int):
      file_name, _ = QFileDialog.getOpenFileName(
        self, "Select Profile Photo", "",
        "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
      )

      if not file_name:
        return
      
      file_size = os.path.getsize(file_name)
      if file_size > 10 * 1024 * 1024:
        QMessageBox.warning(
          self,
          "Upload Failed",
          "This image is too large. Maximum allowed size is 10 MB"
        )
        return

      mime_type, _ = mimetypes.guess_type(file_name)
      if not mime_type or not mime_type.startswith("image/"):
        QMessageBox.warning(
          self,
          "Upload Failed",
          "Invalid file format. Please select an image (PNG, JPG, JPEG, etc.)"
        )
        return
      
      try:
        with open(file_name, "rb") as f:
          file_bytes = f.read()
        
        file_path = f"{self.user_id}/{uuid.uuid4()}.png"

        success = update_avatar_url(self.user_id, file_path, file_bytes, "image/png")

        if success:
          new_pixmap = self.load_profile_pic(self.user_id, size)
          self.pic_label.setPixmap(new_pixmap)
        else:
          QMessageBox.warning(self, "Upload Failed", "Could not update photo in database.")
      
      except Exception as e:
        QMessageBox.warning(self, "Upload Failed", f"Failed to change photo: {e}")

    def create_acc_card(self, pic_size: int = 74):
      acc_card = QWidget()
      card_layout = QVBoxLayout(acc_card)
      card_layout.setContentsMargins(0, 0, 0, 0)

      upper_layout = QHBoxLayout()

      lower_widget = QFrame()
      lower_widget.setObjectName("accFrame")

      lowerW_layout = QHBoxLayout(lower_widget)
      sublayout1 = QVBoxLayout()
      sublayout2 = QVBoxLayout()

      heading = QLabel("User Account")
      heading.setProperty("role", "heading3")

      logout_icon_path = BASE_DIR / "assets" / "icons" / "logout.svg"
      logout_btn = QToolButton()
      logout_btn.setText("Log Out")
      logout_btn.setObjectName("logoutButton")
      logout_icon = QIcon(str(logout_icon_path))
      logout_btn.setIcon(logout_icon)
      logout_btn.setIconSize(QSize(30, 30))
      logout_btn.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextBesideIcon 
      )
      logout_btn.clicked.connect(lambda: self.go_to_logout.emit())

      upper_layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignLeft)
      upper_layout.addStretch()
      upper_layout.addWidget(logout_btn, alignment=Qt.AlignmentFlag.AlignRight)
      
      pic_size = 74
      
      self.pic_label = QLabel()
      self.pic_label.setFixedSize(pic_size, pic_size)
      placeholder = QPixmap(pic_size, pic_size)
      placeholder.fill(Qt.GlobalColor.lightGray)

      self.pic_label.setPixmap(
      self.circular_pixmap(placeholder, pic_size)
      )

      btn = QPushButton("Change Photo")
      btn.setProperty("role", "changeButton")
      btn.setFixedWidth(110)
      btn.clicked.connect(lambda: self.change_photo(pic_size))

      sublayout1.addWidget(self.pic_label, alignment=Qt.AlignmentFlag.AlignHCenter)
      sublayout1.addSpacing(8)
      sublayout1.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
      sublayout1.setContentsMargins(30, 0, 30, 0)

      user_name = "Unknown"
      email = "_"

      self.inner_heading = QLabel(f'Back in action, <span style="font-weight:700; font-size:26px;">{user_name}</span>')
      self.inner_heading.setObjectName("innerHeading")
      self.emailText = QLabel(f"{email}")
      self.emailText.setObjectName("emailText")

      sublayout2.addWidget(self.inner_heading)
      sublayout2.addSpacing(10)
      sublayout2.addWidget(self.emailText)

      lowerW_layout.addLayout(sublayout1)
      lowerW_layout.addSpacing(50)
      lowerW_layout.addLayout(sublayout2)
      lowerW_layout.addStretch()

      card_layout.addLayout(upper_layout)
      card_layout.setSpacing(10)
      card_layout.addWidget(lower_widget)

      return acc_card

    def toggle_edit_mode(self):
        if self.is_editing:
          return
        
        self.is_editing = True
        self.edit_btn.setText(" Editing...")
        self.edit_btn.setEnabled(True)
        self.edit_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "edit_dark.svg")))
        self.save_btn.show()

        self.name_input.setReadOnly(False)
        self.age_input.setReadOnly(False)
        self.gender_input.setEnabled(True)
        self.height_input.setReadOnly(False)
        self.weight_input.setReadOnly(False)

    def toggle_edit_mode_back(self):
      self.is_editing = False

      self.edit_btn.setText(" Edit")
      self.edit_btn.setEnabled(True)
      self.edit_btn.setIcon(QIcon(str(BASE_DIR / "assets" / "icons" / "edit.svg")))

      self.save_btn.hide()


      self.name_input.setReadOnly(True)
      self.age_input.setReadOnly(True)
      self.height_input.setReadOnly(True)
      self.weight_input.setReadOnly(True)

      self.gender_input.setEnabled(False)

    def create_details_form(self):
      container = QWidget()
      main_layout = QVBoxLayout(container)
      main_layout.setContentsMargins(0, 0, 0, 0)
      main_layout.setSpacing(20)

      heading = QLabel("Personal & Physical Details")
      heading.setProperty("role", "heading3")

      content_layout = QHBoxLayout()
      content_layout.setContentsMargins(0, 0, 0, 0)
      content_layout.setSpacing(12)

      details_frame = QFrame()
      details_frame.setObjectName("detailsFrame")

      grid = QGridLayout(details_frame)
      grid.setContentsMargins(20, 20, 20, 20)
      grid.setHorizontalSpacing(12)
      grid.setVerticalSpacing(10)

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

        grid.addWidget(label, row, 0)
        grid.addWidget(colon, row, 1)
        grid.addWidget(widget, row, 2)

      grid.setColumnStretch(2, 1)

      edit_icon_path = BASE_DIR / "assets" / "icons" / "edit.svg"
      self.edit_btn = QToolButton()
      self.edit_btn.setText(" Edit")
      self.edit_btn.setObjectName("editButton")
      self.edit_btn.setIcon(QIcon(str(edit_icon_path)))
      self.edit_btn.setIconSize(QSize(30, 30))
      self.edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

      save_icon_path = BASE_DIR / "assets" / "icons" / "save.svg"
      self.save_btn = QPushButton("  Save Changes")
      self.save_btn.setObjectName("saveButton")
      self.save_btn.setIcon(QIcon(str(save_icon_path)))
      self.save_btn.setIconSize(QSize(16, 16))
      self.save_btn.hide()
      self.save_btn.clicked.connect(
        self.save_profile
      )

      right_layout = QVBoxLayout()
      right_layout.addWidget(self.edit_btn, alignment=Qt.AlignmentFlag.AlignTop)
      right_layout.addStretch()
      right_layout.addWidget(self.save_btn, alignment=Qt.AlignmentFlag.AlignBottom)

      self.edit_btn.clicked.connect(self.toggle_edit_mode)

      content_layout.addWidget(details_frame, 4)
      content_layout.addLayout(right_layout, 1)

      main_layout.addWidget(heading)
      main_layout.setSpacing(16)
      main_layout.addLayout(content_layout)

      self.name_input.setReadOnly(True)
      self.age_input.setReadOnly(True)
      self.height_input.setReadOnly(True)
      self.weight_input.setReadOnly(True)
      self.gender_input.setEnabled(False)

      return container
    
    def save_profile(self):

      try:
        data = {
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


      result = update_profile(
        self.user_id,
        data
      )


      if result["success"]:

        QMessageBox.information(
            self,
            "Saved",
            "Profile updated successfully"
        )

        self.toggle_edit_mode_back()

      else:

        QMessageBox.warning(
            self,
            "Failed",
            result["error"]
        )

    def load_profile(self):

      profile = get_profile(self.user_id)

      if profile["success"] and profile["exists"]:

        data = profile["data"]

        self.name_input.setText(
            data.get("name", "")
        )

        self.age_input.setText(
            str(data.get("age", ""))
        )

        gender = data.get("gender", "")

        index = self.gender_input.findText(gender.capitalize())

        if index >= 0:
            self.gender_input.setCurrentIndex(index)


        self.height_input.setText(
            str(data.get("height_cm", ""))
        )

        self.weight_input.setText(
            str(data.get("weight_kg", ""))
        )

    def set_user_id(self, user_id):
      #print("PROFILE USER ID:", user_id)
      self.user_id = user_id
      self.load_profile()
      
      profile = get_profile(self.user_id)

      if profile["success"] and profile["exists"]:
        data = profile["data"]

        user_name = data.get("name", "Unknown")
        email = data.get("email", "_")

        email = get_email()

        self.inner_heading.setText(
          f'Back in action, <span style="font-weight:700; font-size:26px;">{user_name}</span>'
        )

        self.emailText.setText(email)

      self.pic_label.setPixmap(
        self.load_profile_pic(user_id, 74)
      )
  