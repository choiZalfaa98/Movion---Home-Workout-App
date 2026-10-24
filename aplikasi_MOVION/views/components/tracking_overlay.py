from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QColor, QFont
from PyQt6.QtCore import QTimer

SKELETON_CONNECTIONS = [
    # torso
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),

    # left arm
    (11, 13),
    (13, 15),

    # right arm
    (12, 14),
    (14, 16),

    # left leg
    (23, 25),
    (25, 27),
    (27, 31),

    # right leg
    (24, 26),
    (26, 28),
    (28, 32),

    # hands
    (15, 17),
    (17, 19),
    (19, 21),

    (16, 18),
    (18, 20),
    (20, 22),

    # feet
    (27, 29),
    (29, 31),

    (28, 30),
    (30, 32),
]

RELEVANT_LANDMARKS = list(range(11, 33))

class TrackingOverlay:
    # --- VISUAL FEEDBACK AND STATUS COLORS ---
    UNDETECTED = QColor("#3D3E56")
    DETECTED = QColor("#CA502A")
    TRACKING   = QColor("#CA502A")

    VALID = QColor("#2ECC71") 
    WRONG = QColor("#FF03A7")      
    FINISHED = QColor("#00D1FF") 

    def __init__(self, scene):
        self.scene = scene

        self.box1 = self.create_box()
        self.box2 = self.create_box()

        font = QFont("Poppins")
        font.setPointSize(16)
        font.setWeight(QFont.Weight.DemiBold)

        self.name1 = self.create_text(font, QColor("#CA502A"))
        self.name2 = self.create_text(font, QColor("#CA502A"))

        instr_font = QFont("Noto Sans")
        instr_font.setPointSize(18)
        instr_font.setWeight(QFont.Weight.Bold)
        
        self.instruction = self.create_text(instr_font, QColor("#621F0A"))
        self.instruction.setPlainText(
            "Please stand in the marked area so your full body is visible"
        )

        self.box2.hide()
        self.name2.hide()

        self.mode = "single"

        self.track_box1 = self._create_track_box()
        self.track_box2 = self._create_track_box()

        self._track_flash_token = {
            "user1": 0,
            "user2": 0,
        }

    def create_box(self):
        box = QGraphicsRectItem()
        pen = QPen(self.TRACKING)
        pen.setWidth(3)
        box.setPen(pen)
        self.set_color(box, self.UNDETECTED)
        box.setZValue(10)
        box.hide()

        self.scene.addItem(box)

        return box

    def create_text(self, font, color=QColor("white")):
        text = QGraphicsTextItem()
        text.setFont(font)
        text.setDefaultTextColor(color)
        text.setZValue(11)
        self.scene.addItem(text)
        return text

    def set_color(self, item, color):
        pen = QPen(color)
        pen.setWidth(4)
        item.setPen(pen)

    def detected(self, user):
        box = (
            self.box1
            if user == "user1"
            else self.box2
        )
        self.set_color(box, self.DETECTED)

    def reset_colors(self):
        self.set_color(self.box1, self.UNDETECTED)
        self.set_color(self.box2, self.UNDETECTED)

    def show_all(self, mode):
        self.mode = mode
        self.box1.show()
        self.name1.show()
        self.instruction.show()

        if mode == "multi":
            self.box2.show()
            self.name2.show()
        else:
            self.box2.hide()
            self.name2.hide()

    def hide_all(self):
        for item in (
            self.box1, self.box2,
            self.name1, self.name2,
            self.instruction
        ):
            item.hide()
    
    def hide_detected_box(self, user_key):
        if user_key == "user1":
            self.box1.hide()
            self.name1.hide()
        else:
            self.box2.hide()
            self.name2.hide()

        if not self.box1.isVisible() and not self.box2.isVisible():
            self.instruction.hide()

    def relayout(self, w, h):
        if w == 0 or h == 0:
            return

        if self.mode == "single":
            self._layout_single(w, h)
        else:
            self._layout_multi(w, h)

        iw = self.instruction.boundingRect().width()
        self.instruction.setPos((w - iw) / 2, h - 80)
    
    def _layout_single(self, w, h):
        bw = w * 0.22
        bh = h * 0.65
        x = (w - bw) / 2
        y = (h - bh) / 2
        self.box1.setRect(x, y, bw, bh)

        nw = self.name1.boundingRect().width()
        self.name1.setPos(x + (bw - nw) / 2, y - 50)

    def _layout_multi(self, w, h):
        bw = w * 0.22
        bh = h * 0.65
        y = h * 0.12

        # mirrored screen, resulted in box1 is for user2, and the opposite
        x1 = w * 0.08
        x2 = w - x1 - bw

        self.box1.setRect(x1, y, bw, bh)
        self.box2.setRect(x2, y, bw, bh)

        nw1 = self.name1.boundingRect().width()
        nw2 = self.name2.boundingRect().width()
        self.name1.setPos(x1 + (bw - nw1) / 2, y - 50)
        self.name2.setPos(x2 + (bw - nw2) / 2, y - 50)
    
    def _create_track_box(self):
        box = QGraphicsRectItem()
        pen = QPen(self.TRACKING)
        pen.setWidth(3)
        box.setPen(pen)
        box.setZValue(10)
        box.hide()
        self.scene.addItem(box)
        return box

    def update_track_box(self, user_key, bbox_viewport):
        box = self.track_box1 if user_key == "user1" else self.track_box2
        x1, y1, x2, y2 = bbox_viewport
        box.setRect(x1, y1, x2 - x1, y2 - y1)
        box.show()

    def _get_track_box(self, user_key):
        return self.track_box1 if user_key == "user1" else self.track_box2

    def set_track_box_color(self, user_key, color, width=4):
        box = self._get_track_box(user_key)
        pen = QPen(color)
        pen.setWidth(width)
        box.setPen(pen)

    def reset_track_box_color(self, user_key):
        self.set_track_box_color(user_key, self.TRACKING, width=4)

    def flash_track_box(self, user_key, status, duration_ms=None):
        box = self._get_track_box(user_key)

        if status == "valid":
            color = self.VALID
            duration = 700 if duration_ms is None else duration_ms

        elif status == "wrong":
            color = self.WRONG
            duration = 1200 if duration_ms is None else duration_ms

        elif status == "finished":
            color = self.FINISHED
            duration = 1500 if duration_ms is None else duration_ms

        else:
            color = self.TRACKING
            duration = 400 if duration_ms is None else duration_ms

        self._track_flash_token[user_key] += 1
        token = self._track_flash_token[user_key]

        self.set_track_box_color(user_key, color, width=5)

        def restore_color():
            if self._track_flash_token.get(user_key) != token:
                return

            self.reset_track_box_color(user_key)

        QTimer.singleShot(duration, restore_color)

    def hide_track_box(self, user_key, hide_skeleton=True):
        self._track_flash_token[user_key] += 1

        box = self._get_track_box(user_key)
        box.hide()

        self.reset_track_box_color(user_key)

        if hide_skeleton:
            self.hide_skeleton(user_key)

    def init_skeleton_items(self):
        self._skeleton_lines = {"user1": [], "user2": []}
        self._skeleton_dots  = {"user1": [], "user2": []}

        line_pen = QPen(QColor("#7F48FF"))
        line_pen.setWidth(5)

        dot_pen = QPen(QColor("#3B51AB"))
        dot_pen.setWidth(5)
        dot_brush = QColor("#3B51AB")

        for user_key in ("user1", "user2"):
            for _ in SKELETON_CONNECTIONS:
                item = QGraphicsLineItem()
                item.setPen(line_pen)
                item.setZValue(12)
                item.hide()
                self.scene.addItem(item)
                self._skeleton_lines[user_key].append(item)

            for _ in RELEVANT_LANDMARKS:
                item = QGraphicsEllipseItem(0, 0, 8, 8)
                item.setPen(dot_pen)
                item.setBrush(dot_brush)
                item.setZValue(13)
                item.hide()
                self.scene.addItem(item)
                self._skeleton_dots[user_key].append(item)

    def update_skeleton(self, user_key, landmarks_viewport):
        lines = self._skeleton_lines[user_key]
        dots  = self._skeleton_dots[user_key]

        for i, (start_idx, end_idx) in enumerate(SKELETON_CONNECTIONS):
            if start_idx >= len(landmarks_viewport) or end_idx >= len(landmarks_viewport):
                lines[i].hide()
                continue
            x1, y1 = landmarks_viewport[start_idx]
            x2, y2 = landmarks_viewport[end_idx]
            lines[i].setLine(x1, y1, x2, y2)
            lines[i].show()

        for i, lm_idx in enumerate(RELEVANT_LANDMARKS):
            if lm_idx >= len(landmarks_viewport):
                dots[i].hide()
                continue
            x, y = landmarks_viewport[lm_idx]
            dots[i].setRect(x - 4, y - 4, 8, 8)
            dots[i].show()

    def hide_skeleton(self, user_key):
        for item in self._skeleton_lines[user_key]:
            item.hide()
        for item in self._skeleton_dots[user_key]:
            item.hide()

    def hide_track_boxes(self):
        self.hide_track_box("user1", hide_skeleton=True)
        self.hide_track_box("user2", hide_skeleton=True)