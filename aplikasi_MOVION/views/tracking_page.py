from PyQt6.QtWidgets import QFrame, QScrollArea, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QRadioButton, QButtonGroup, QComboBox, QDialog, QMessageBox, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget

from views.components.sidebar import Sidebar
from views.page_constants import Page

from services.camera_service import get_cameras

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

single_path = BASE_DIR / "assets" / "icons" / "single_mode.svg" 
multi_path = BASE_DIR / "assets" / "icons" / "multi_mode.svg"
cam_icon_path = BASE_DIR / "assets" / "icons" / "camera.svg"

class TrackingMode(QWidget):
    continue_to_tips = pyqtSignal(str, int)
    
    def __init__(self, navigate_func):
      super().__init__()

      self.selected_mode = None
      self.single_radio = None
      self.multi_radio = None

      root_layout = QHBoxLayout()

      # --- SIDEBAR ---
      self.sidebar = Sidebar(active_page=Page.TRACKING_MODE)
      self.navigate = navigate_func

      self.sidebar.navigate_requested.connect(self.navigate)
        
      # --- MAIN CONTENT ---
      content = QWidget()
      content_layout = QVBoxLayout()

      page_title = QLabel("Workout Session")
      page_title.setProperty("role", "pageTitle")

      scroll_area = QScrollArea()
      scroll_area.setWidgetResizable(True)
      scroll_area.setFrameShape(QFrame.Shape.NoFrame)

      scroll_content = QWidget()
      scroll_content.setProperty("role", "scrollContent")

      scroll_layout = QVBoxLayout()

      heading = QLabel("Select Tracking Mode & Camera Source")
      heading.setProperty("role", "heading2")
      heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)

      heading.setContentsMargins(0, 0, 0, 0)    
      heading.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed
      )

      single_groupBox, self.single_radio = (
         self.create_tracking_options(
            single_path,
            "Single Person Mode",
            "Detect and analyze one person's movement"
         )
      )
      multi_groupBox, self.multi_radio = (
         self.create_tracking_options(
            multi_path,
            "Multi Person Mode",
            "Detect and analyze two people's movement"
         )
      )

      self.single_radio.toggled.connect(
        lambda checked:
        self.set_mode("single") if checked else None
      )
      self.multi_radio.toggled.connect(
        lambda checked:
        self.set_mode("multi") if checked else None
      )

      self.mode_group = QButtonGroup(self)
      self.mode_group.addButton(self.single_radio)
      self.mode_group.addButton(self.multi_radio)
      self.mode_group.setExclusive(True)

      mode_widget = QWidget()
      mode_layout = QHBoxLayout(mode_widget)
      mode_layout.setContentsMargins(0, 0, 0, 0)

      mode_layout.addWidget(single_groupBox)
      mode_layout.addWidget(multi_groupBox)
      mode_layout.setSpacing(150)

      cam_detected = self.create_camera_source()

      ctaBtn = QPushButton("Continue")
      ctaBtn.setProperty("role", "button1")
      ctaBtn.setFixedSize(275, 40)
      ctaBtn.clicked.connect(
        self.continue_clicked
      )

      scroll_layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignHCenter)
      scroll_layout.addWidget(mode_widget, alignment=Qt.AlignmentFlag.AlignHCenter)
      scroll_layout.addWidget(
        cam_detected,
        alignment=Qt.AlignmentFlag.AlignHCenter
      )
      scroll_layout.addWidget(
         ctaBtn,
         alignment=Qt.AlignmentFlag.AlignHCenter
      )

      scroll_layout.setContentsMargins(46, 46, 46, 50)
      scroll_layout.setSpacing(60)

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

    def create_tracking_options(self, icon_path, title, desc):
      cardButton = QWidget()
      cardButton_layout = QVBoxLayout(cardButton)
      cardButton_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

      card = QFrame()
      card.setProperty("role", "trackingFrame")
      card.setFixedSize(260, 240)

      tracking_layout = QVBoxLayout(card)
      tracking_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

      radio = QRadioButton()

      icon = QSvgWidget(str(icon_path))
      if icon_path == (BASE_DIR / "assets" / "icons" / "single_mode.svg"):
        icon.setFixedSize(60, 60)
      elif icon_path == (BASE_DIR / "assets" / "icons" / "multi_mode.svg"):
        icon.setFixedSize(120, 60)
      icon.setContentsMargins(0, 0, 0, 0)

      heading = QLabel(title)
      heading.setProperty("role", "trackingTitle")
      heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
      heading.setContentsMargins(0, 0, 0, 0)

      desc = QLabel(desc)
      desc.setProperty("role", "trackingDesc")
      desc.setWordWrap(True)
      desc.setAlignment(Qt.AlignmentFlag.AlignHCenter)
      desc.setContentsMargins(0, 0, 0, 0)

      tracking_layout.addWidget(
        icon,
        alignment=Qt.AlignmentFlag.AlignHCenter
      )
      tracking_layout.addSpacing(30)
      tracking_layout.addWidget(
        heading,
        alignment=Qt.AlignmentFlag.AlignHCenter
      )
      tracking_layout.addSpacing(2)
      tracking_layout.addWidget(
        desc,
        alignment=Qt.AlignmentFlag.AlignHCenter
      )
      tracking_layout.setContentsMargins(20, 20, 20, 20)

      cardButton_layout.addWidget(card)
      cardButton_layout.addSpacing(30)
      cardButton_layout.addWidget(radio, alignment=Qt.AlignmentFlag.AlignHCenter)

      return cardButton, radio

    def create_camera_source(self):
      camera_frame = QFrame()
      camera_frame.setObjectName("camFrame")
      camera_frame.setMaximumWidth(520)
      camera_frame.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed
      )

      frame_layout = QHBoxLayout(camera_frame)
      frame_layout.setContentsMargins(0, 0, 0, 0)
      frame_layout.setSpacing(0)
      
      subframe1_widget = QWidget()
      subframe2_widget = QWidget()
      subframe1 = QHBoxLayout(subframe1_widget)
      subframe2 = QVBoxLayout(subframe2_widget)
      subframe1.setAlignment(Qt.AlignmentFlag.AlignCenter)
      subframe2.setAlignment(Qt.AlignmentFlag.AlignCenter)
      subframe1.setContentsMargins(20, 16, 20, 16)
      subframe2.setContentsMargins(20, 16, 20, 16)
      subframe1.setSpacing(20)
      subframe2.setSpacing(10)

      divider = QFrame()
      divider.setFixedWidth(1)
      divider.setObjectName("divider")

      camera_icon = QSvgWidget(str(cam_icon_path))
      camera_icon.setFixedSize(50, 50)

      heading = QLabel("Camera Source Detected")
      heading.setObjectName("camDetectedTitle")

      cameras = get_cameras()
      self.current_camera_source = (
        cameras[0]["index"] 
        if cameras 
        else None
      )

      default_camera = (
        cameras[0]["name"]
        if cameras
        else "No Camera Detected"
      )

      self.cam_source_label = QLabel(default_camera)
      self.cam_source_label.setObjectName("camSourceName")

      btn = QPushButton("Change Source")
      btn.setProperty("role", "changeButton")
      btn.setFixedWidth(110)
      btn.clicked.connect(self.open_camera_selector)

      subframe1.addWidget(camera_icon)
      subframe1.addWidget(heading)

      subframe2.addWidget(self.cam_source_label)
      subframe2.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

      frame_layout.addWidget(subframe1_widget)
      frame_layout.addWidget(divider)
      frame_layout.addWidget(subframe2_widget)

      return camera_frame
    
    def open_camera_selector(self):
      cameras = get_cameras()

      dialog = QDialog(self)
      dialog.setObjectName("camSelection")
      layout = QVBoxLayout(dialog)

      combo = QComboBox()

      if cameras:
        for cam in cameras:
          combo.addItem(
            cam["name"],
            cam["index"]
          )
      else:
        combo.addItem("No Camera Detected")

      layout.addWidget(combo)

      ok_btn = QPushButton("OK")
      ok_btn.clicked.connect(
        lambda: self.confirm_camera_selection(
          dialog,
          combo
        )
      )

      layout.addWidget(ok_btn)

      dialog.exec()

    def set_camera_source(self, combo):
      name = combo.currentText()
      index = combo.currentData()

      self.current_camera_source = index

      self.cam_source_label.setText(name)

      #print("Camera source changed:", name, index)

    def confirm_camera_selection(self, dialog, combo):
      self.set_camera_source(combo)
      dialog.accept()

    def set_mode(self, mode):
      self.selected_mode = mode
    
    def continue_clicked(self):
      if self.selected_mode is None:
        #print("Select tracking mode first")
        QMessageBox.warning(
              self,
              "Unselected Tracking Mode",
              "Please select one tracking mode to continue"
            )
        return

      mode = self.selected_mode
      camera = self.current_camera_source

      self.reset_tracking_mode()

      self.continue_to_tips.emit(
        mode, camera
      )

    def reset_tracking_mode(self):

      self.mode_group.setExclusive(False)

      self.single_radio.setChecked(False)
      self.multi_radio.setChecked(False)

      self.mode_group.setExclusive(True)

      self.selected_mode = None