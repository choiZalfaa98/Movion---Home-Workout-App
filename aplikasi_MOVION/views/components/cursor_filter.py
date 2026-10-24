from PyQt6.QtWidgets import QPushButton, QToolButton, QComboBox, QRadioButton
from PyQt6.QtCore import QObject, QEvent, Qt

class CursorFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            if isinstance(obj, (QPushButton, QToolButton, QComboBox, QRadioButton)):
                obj.setCursor(Qt.CursorShape.PointingHandCursor)

        return super().eventFilter(obj, event)