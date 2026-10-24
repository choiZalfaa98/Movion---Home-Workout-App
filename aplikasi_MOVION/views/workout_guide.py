from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QToolButton, QFrame, QGraphicsView, QGraphicsScene, QGraphicsProxyWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QRectF, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QIcon, QBrush, QColor
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class VideoGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("videoFrame")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor("black")))
        self.setScene(self._scene)

        # Left video item (front view)
        self.front_item = QGraphicsVideoItem()
        self.front_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self._scene.addItem(self.front_item)

        # Right video item (side view)
        self.side_item = QGraphicsVideoItem()
        self.side_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self._scene.addItem(self.side_item)

        self.front_player = QMediaPlayer()
        self.front_player.setVideoOutput(self.front_item)
        self.front_player.setLoops(QMediaPlayer.Loops.Infinite)

        self.side_player = QMediaPlayer()
        self.side_player.setVideoOutput(self.side_item)
        self.side_player.setLoops(QMediaPlayer.Loops.Infinite)

        self.play_btn = QPushButton()
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setFixedSize(80, 80)
        self.play_btn.setObjectName("playWorkoutVids")
        
        play_icon_path = BASE_DIR / "assets" / "icons" / "play.svg"
        self.play_icon = QIcon(str(play_icon_path))
        self.play_btn.setIcon(self.play_icon)
        pause_icon_path = BASE_DIR / "assets" / "icons" / "pause2.svg"
        self.pause_icon = QIcon(str(pause_icon_path))
        self.play_btn.setIconSize(QSize(80, 80))
        
        self._proxy = QGraphicsProxyWidget()
        self._proxy.setWidget(self.play_btn)
        self._scene.addItem(self._proxy)
        self._proxy.setZValue(10)

        self.is_playing = False
        self.play_btn.clicked.connect(self.toggle)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_items()

    def _layout_items(self):
        w = self.viewport().width()
        h = self.viewport().height()

        half_w = w / 2

        self.front_item.setPos(0, 0)
        self.front_item.setSize(QRectF(0, 0, half_w, h).size())

        self.side_item.setPos(half_w, 0)
        self.side_item.setSize(QRectF(0, 0, half_w, h).size())

        self._scene.setSceneRect(0, 0, w, h)

        bw = self._proxy.boundingRect().width()
        bh = self._proxy.boundingRect().height()
        self._proxy.setPos((w - bw) / 2, (h - bh) / 2)

    def toggle(self):
        if self.is_playing:
            self.front_player.pause()
            self.side_player.pause()
            self.play_btn.setIcon(self.play_icon)
            self.is_playing = False
        else:
            self.front_player.play()
            self.side_player.play()
            self.play_btn.setIcon(self.pause_icon)
            self.is_playing = True

    def load_videos(self, front_path: str, side_path: str):
        self.front_player.stop()
        self.side_player.stop()

        self.front_player.setSource(QUrl.fromLocalFile(front_path))
        self.side_player.setSource(QUrl.fromLocalFile(side_path))

        self.front_player.pause()
        self.side_player.pause()

        self.is_playing = False
        self.play_btn.setIcon(self.play_icon)

    def stop_all(self):
        self.front_player.stop()
        self.side_player.stop()
        self.is_playing = False
        self.play_btn.setIcon(self.play_icon)


class WorkoutGuide(QWidget):
    back_or_pause = pyqtSignal()
    begin_each_workout = pyqtSignal(object)
    workout_finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()

        self.session = None
        self.current_workout = None

        self.build_ui()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.remaining_time = 0
        self.countdown_finished = False

    def build_ui(self):
        root_layout = QVBoxLayout()

        header = QWidget()
        header_layout = QHBoxLayout(header)

        pause_icon_path = BASE_DIR / "assets" / "icons" / "pause.svg"
        pause_btn = QToolButton()
        pause_btn.setText("Back/Pause")
        pause_btn.setProperty("role", "backPauseButton")
        pause_icon = QIcon(str(pause_icon_path))
        pause_btn.setIcon(pause_icon)
        pause_btn.setIconSize(QSize(18, 18))
        pause_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        pause_btn.clicked.connect(self.stop_guide_timer)

        page_title = QLabel("Workout Session")
        page_title.setProperty("role", "pageTitle")
        page_title.setContentsMargins(0, 0, 120, 0)

        header_layout.addWidget(pause_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        header_layout.addStretch()
        header_layout.addWidget(page_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        header_layout.addStretch()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(150, 20, 150, 20)

        guide_card = QFrame()
        guide_card.setObjectName("guideFrame")
        guide_card_layout = QVBoxLayout(guide_card)

        self.video_view = VideoGraphicsView()
        self.video_view.setMinimumHeight(240)
        self.video_view.setMaximumHeight(400)
        self.video_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.exercise_guide_name = QLabel()
        self.exercise_guide_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.exercise_guide_name.setObjectName("exerciseGuideName")

        self.muscle_container = QWidget()
        self.muscle_layout = QHBoxLayout(self.muscle_container)
        self.muscle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.muscle_layout.setSpacing(16)

        reps_layout = QHBoxLayout()
        reps_label = QLabel("Repetitions:")
        reps_label.setProperty("role", "workoutGuideText")
        self.reps_value = QLabel()
        self.reps_value.setProperty("role", "workoutGuideText")
        reps_layout.addWidget(reps_label, alignment=Qt.AlignmentFlag.AlignLeft)
        reps_layout.addWidget(self.reps_value, alignment=Qt.AlignmentFlag.AlignRight)

        instruction_layout = QVBoxLayout()
        instruction_label = QLabel("Instructions: ")
        instruction_label.setProperty("role", "workoutGuideText")
        self.instruction_text = QLabel()
        self.instruction_text.setObjectName("workoutGuideText2")
        self.instruction_text.setWordWrap(True)
        self.instruction_text.setAlignment(Qt.AlignmentFlag.AlignJustify)
        instruction_layout.addWidget(instruction_label)
        instruction_layout.addWidget(self.instruction_text)

        countdown_container = QWidget()
        count_container_layout = QHBoxLayout(countdown_container)
        time_icon_path = BASE_DIR / "assets" / "icons" / "timer.svg"
        time_icon = QSvgWidget(str(time_icon_path))
        time_icon.setFixedSize(60, 60)
        time_texts_layout = QVBoxLayout()
        self.time_seconds = QLabel()
        self.time_seconds.setObjectName("timer")
        self.timer_info = QLabel()
        self.timer_info.setObjectName("timerExerciseText")
        time_texts_layout.addWidget(self.time_seconds)
        time_texts_layout.addWidget(self.timer_info)
        count_container_layout.addWidget(time_icon)
        count_container_layout.addLayout(time_texts_layout)

        self.cta_btn = QPushButton()
        self.cta_btn.setObjectName("beginWorkoutBtn")
        self.cta_btn.setFixedSize(254, 40)
        self.cta_btn.clicked.connect(self.start_workout)

        lower_layout = QHBoxLayout()
        lower_layout.addWidget(countdown_container)
        lower_layout.addStretch()
        lower_layout.addWidget(self.cta_btn)

        guide_card_layout.addWidget(self.video_view, 1)
        guide_card_layout.addSpacing(20)
        guide_card_layout.addWidget(self.exercise_guide_name, 0)
        guide_card_layout.addWidget(self.muscle_container, 0)
        guide_card_layout.addLayout(reps_layout, 0)
        guide_card_layout.addSpacing(6)
        guide_card_layout.addLayout(instruction_layout, 0)
        guide_card_layout.addSpacing(20)
        guide_card_layout.addLayout(lower_layout, 0)
        guide_card_layout.setContentsMargins(10, 10, 10, 10)

        content_layout.addWidget(guide_card)

        root_layout.addWidget(header, 0)
        root_layout.addWidget(content, 1)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(root_layout)

    def load_workout(self):
        if not self.current_workout:
            return

        workout = self.current_workout

        self.exercise_guide_name.setText(workout["name"])
        self.reps_value.setText(str(workout["reps_target"]))
        self.instruction_text.setText(workout["instruction"])
        self.timer_info.setText(
            f'until <span style="font-weight:700;">{workout["name"]}</span> begins'
        )
        self.cta_btn.setText(f'Begin {workout["name"]}')
        self.update_muscles(workout["muscles"])
        self.load_videos(workout["videos"])

    def update_muscles(self, muscles):
        while self.muscle_layout.count():
            item = self.muscle_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for muscle in muscles:
            frame = QFrame()
            frame.setProperty("role", "muscleGainFrame")
            layout = QHBoxLayout(frame)
            label = QLabel(muscle)
            layout.addWidget(label)
            self.muscle_layout.addWidget(frame)

    def load_videos(self, videos):
        front_path = str(BASE_DIR / "assets" / "workout_vids" / videos["front"])
        side_path = str(BASE_DIR / "assets" / "workout_vids" / videos["side"])
        self.video_view.load_videos(front_path, side_path)

    def set_session(self, session, resume=False):
        self.session = session
        self.current_workout = session.get_current_workout()
        session.current_page = "guide"
        self.load_workout()
        if resume and session.remaining_guide_time is not None:
            #print("RESUMING from:", session.remaining_guide_time)  # debug
            self.remaining_time = session.remaining_guide_time
            self.countdown_finished = False
            self.time_seconds.setText(f"{self.remaining_time} s")
            self.countdown_timer.start(1000)
        else:
            self.start_countdown()
    
    def start_countdown(self):
        if not self.current_workout:
            return

        self.remaining_time = self.current_workout["duration"]
        self.countdown_finished = False
        self.time_seconds.setText(f"{self.remaining_time} s")
        self.countdown_timer.start(1000)

    def update_countdown(self):
        self.remaining_time -= 1
        self.time_seconds.setText(f"{self.remaining_time} s")

        if self.remaining_time <= 0:
            self.countdown_timer.stop()
            self.countdown_finished = True
            self.start_workout()

    def start_workout(self):
        self.countdown_timer.stop()
        self.video_view.stop_all()

        if self.session:
            self.session.remaining_guide_time = None
            self.session.current_page = "session"

        self.begin_each_workout.emit(self.session)

    def next_workout(self):
        if not self.session:
            return

        if self.session.next_workout():
            self.current_workout = self.session.get_current_workout()
            self.session.current_page = "guide"
            self.session.remaining_guide_time = None
            self.load_workout()
            self.start_countdown()
        else:
            self.session.current_page = None
            self.workout_finished.emit()

    def stop_guide_timer(self):
        self.countdown_timer.stop()

        if self.session:
            self.session.remaining_guide_time = self.remaining_time
            #print("SAVED remaining_guide_time:", self.session.remaining_guide_time)  # debug

        self.back_or_pause.emit()
