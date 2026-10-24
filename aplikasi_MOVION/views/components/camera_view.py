from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QFrame
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QTransform
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem

class CameraView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:black;border:none;")

        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor("black")))
        self.setScene(self.scene)

        self.video_item = QGraphicsVideoItem()
        self.video_item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)

        # --- SCENE MIRRORING ---
        mirror = QTransform()
        mirror.scale(-1, 1)
        self.video_item.setTransform(mirror)

        self.scene.addItem(self.video_item)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._update_video_geometry)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_video_geometry()

    def _update_video_geometry(self):
        w = self.viewport().width()
        h = self.viewport().height()
        if w == 0 or h == 0:
            return

        # --- MIRROR OFFSET FIX ---
        self.video_item.setPos(w, 0)
        self.video_item.setSize(
            QRectF(0, 0, w, h).size()
        )
        self.scene.setSceneRect(0, 0, w, h)
