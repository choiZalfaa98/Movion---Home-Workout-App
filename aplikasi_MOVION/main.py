from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QFontDatabase

from views.app_window import AppWindow
from views.components.cursor_filter import CursorFilter

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FONTS_DIR = BASE_DIR / "assets" / "fonts"

logo_path = BASE_DIR / "assets" / "logo" / "logo_ico_framed.ico"
global_styles_path = BASE_DIR / "stylesheets" / "global.qss"

app = QApplication([])

cursor_filter = CursorFilter()
app.installEventFilter(cursor_filter)

for font_file in FONTS_DIR.glob("*.ttf"):
    QFontDatabase.addApplicationFont(str(font_file))

app.setApplicationName("MOVION")
app.setWindowIcon(QIcon(str(logo_path)))

app.setStyleSheet(global_styles_path.read_text(encoding="utf-8"))

window = AppWindow()
window.showMaximized()

app.exec()