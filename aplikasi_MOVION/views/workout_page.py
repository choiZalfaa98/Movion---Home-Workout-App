from PyQt6.QtWidgets import QFrame, QScrollArea, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QPixmap

from views.components.sidebar import Sidebar
from views.page_constants import Page

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

mat_path = BASE_DIR / "assets" / "icons" / "yoga_mat.svg"

class WorkoutPage(QWidget):
   continue_to_track_mode = pyqtSignal()

   def __init__(self, navigate_func):
      super().__init__()

      root_layout = QHBoxLayout()

      # --- SIDEBAR ---
      self.sidebar = Sidebar(active_page=Page.WORKOUT_PREVIEW)
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

      heading = QLabel("Workout Preview")
      heading.setProperty("role", "heading2")
      heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)

      workout_preview = QFrame()
      workout_preview.setObjectName("workoutPreview")

      workout_prev_layout = QVBoxLayout(workout_preview)
      
      preview_heading = QLabel("Exercises Set")
      preview_heading.setProperty("role", "heading3")
      preview_details_layout = QVBoxLayout()
      preview_details_layout.setContentsMargins(0, 0, 0, 0)
      preview_details_layout.setSpacing(18)
      preview_details = [
         (
            BASE_DIR / "assets" / "workout_pics" / "jump_jacks_start.png",
            BASE_DIR / "assets" / "workout_pics" / "jump_jacks_end.png",
            "Jumping Jacks",
            15
         ),
         (
            BASE_DIR / "assets" / "workout_pics" / "mount_climb_start.png",
            BASE_DIR / "assets" / "workout_pics" / "mount_climb_end.png",
            "Mountain Climber",
            15
         ),
         (
            BASE_DIR / "assets" / "workout_pics" / "squat_start.png",
            BASE_DIR / "assets" / "workout_pics" / "squat_end.png",
            "Squat",
            15
         ),
         (
            BASE_DIR / "assets" / "workout_pics" / "knee_push_up_start.png",
            BASE_DIR / "assets" / "workout_pics" / "knee_push_up_end.png",
            "Knee Push Up",
            15
         ),
         (
            BASE_DIR / "assets" / "workout_pics" / "sit_up_start.png",
            BASE_DIR / "assets" / "workout_pics" / "sit_up_end.png",
            "Sit Up",
            15
         )
      ]
      
      for first_path, second_path, workout_name, reps in preview_details:
        preview_details_layout.addWidget(
          self.create_previews_section(
             first_path,
             second_path,
             workout_name,
             reps
          )
        )
      
      workout_prev_layout.addWidget(preview_heading)
      workout_prev_layout.addSpacing(20)
      workout_prev_layout.addLayout(preview_details_layout)
      workout_prev_layout.setContentsMargins(0, 0, 0, 0)

      btn = QPushButton("Select Tracking Mode")
      btn.setProperty("role", "button1")
      btn.setFixedSize(275, 40)
      btn.clicked.connect(lambda: self.continue_to_track_mode.emit())

      scroll_layout.addWidget(heading)
      scroll_layout.addWidget(self.create_tips_card(mat_path), alignment=Qt.AlignmentFlag.AlignHCenter)
      scroll_layout.addWidget(workout_preview, alignment=Qt.AlignmentFlag.AlignHCenter)
      scroll_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
      scroll_layout.setSpacing(46)

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

   def create_tips_card(self, mat_path):
      tips_frame = QFrame()
      tips_frame.setObjectName("tipsFrame")

      tips_layout = QHBoxLayout(tips_frame)

      title = QLabel("Tips")
      title.setProperty("role", "subheading2")

      yoga_mat = QSvgWidget(str(mat_path))
      yoga_mat.setFixedSize(50, 50)

      tips = QLabel("It is recommended to use an exercise mat")
      tips.setObjectName("tipsText")

      tips_layout.addWidget(title)
      tips_layout.addSpacing(50)
      tips_layout.addWidget(yoga_mat)
      tips_layout.addSpacing(40)
      tips_layout.addWidget(tips)

      return tips_frame
   
   def create_previews_section(self, first_step_path, second_step_path, workout_name, reps):
      card = QFrame()
      card.setProperty("role","exerciseCard")

      card_layout = QHBoxLayout(card)

      images_layout = QHBoxLayout()
      THUMB_SIZE = 100

      img1 = QLabel()
      img1.setPixmap(
         QPixmap(str(first_step_path))
         .scaled(
            THUMB_SIZE,
            THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
         )
      )
      img1.setProperty("role", "workoutImage")

      img2 = QLabel()
      img2.setPixmap(
         QPixmap(str(second_step_path))
         .scaled(
            THUMB_SIZE,
            THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
         )
      )
      img2.setProperty("role", "workoutImage")

      arrow = QLabel("→")

      images_layout.addWidget(img1)
      images_layout.addWidget(arrow)
      images_layout.addWidget(img2)

      text_layout = QVBoxLayout()
      title = QLabel(workout_name)
      title.setProperty("role", "heading4")

      reps_label = QLabel(f"{reps} repetitions")
      reps_label.setProperty("role", "repsText")

      text_layout.addWidget(title)
      text_layout.addWidget(reps_label)

      card_layout.addLayout(images_layout)
      card_layout.addSpacing(100)
      card_layout.addLayout(text_layout)
      card_layout.setContentsMargins(0, 0, 0, 0)

      return card