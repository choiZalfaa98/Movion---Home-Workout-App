from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtGui import QShortcut, QKeySequence

class BaseWindow(QMainWindow):
  def __init__(self, parent=None):
    super().__init__(parent)

    self.setWindowTitle("MOVION: Home Workout App")
    self.setMinimumSize(1280, 720)

    self.fullscreen_shortcut = QShortcut(
      QKeySequence("F11"),
      self
    )

    self.fullscreen_shortcut.activated.connect(
      self.toggle_fullscreen
    )

  def toggle_fullscreen(self):
    if self.isFullScreen():
      self.showMaximized()
    else:
      self.showFullScreen()
