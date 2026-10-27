"""Custom widgets, shared with pii-roundtrip so both applications look like one house.

Ground is the window itself: navy, a slow beam of aurora light, a soft glow and
a field of faint particles. BrandMark is the mark and wordmark. DropZone, the
progress line and the hover glow are the rest of the vocabulary. Nothing here
knows anything about SQL.
"""

from __future__ import annotations

import itertools
import sys

from PySide6.QtCore import Property, QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


def white(alpha: float) -> QColor:
    return QColor(255, 255, 255, round(255 * alpha))


class DropZone(QWidget):
    """A large rounded area: dashed hairline at rest, solid and lighter while a file hovers over it."""

    file_dropped = Signal(str)
    choose = Signal()

    def __init__(self, t: dict):
        super().__init__()
        self.t = t
        self.setAcceptDrops(True)
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(120)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)
        v.addStretch(1)
        self.glyph = QLabel()
        self.glyph.setFixedSize(40, 40)
        self.glyph.paintEvent = self._paint_glyph  # type: ignore[method-assign]
        v.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(8)
        self.headline = QLabel(t["drop_title"])
        self.headline.setObjectName("headline")
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.headline)
        sub = QLabel(t["drop_sub"])
        sub.setObjectName("sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)
        v.addSpacing(12)
        button = QPushButton(t["choose_file"])
        button.setProperty("primary", True)
        glow(button, primary=True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(self.choose.emit)
        v.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addStretch(1)

    def _get_hover(self) -> float:
        return self._hover

    def _set_hover(self, value: float) -> None:
        self._hover = value
        self.update()
        self.glyph.update()

    hover = Property(float, _get_hover, _set_hover)

    def _animate(self, to: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(to)
        self._anim.start()
        self.headline.setText(self.t["drop_release"] if to else self.t["drop_title"])

    def _paint_glyph(self, _event) -> None:
        p = QPainter(self.glyph)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(white(0.6 + 0.4 * self._hover), 1.5))
        p.translate(0, -4 * self._hover)
        path = QPainterPath()
        path.moveTo(9, 4)
        path.lineTo(25, 4)
        path.lineTo(32, 11)
        path.lineTo(32, 36)
        path.lineTo(9, 36)
        path.closeSubpath()
        p.drawPath(path)
        for y in (17, 23, 29):
            p.drawLine(14, y, 27, y)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        from PySide6.QtGui import QRadialGradient

        g = QRadialGradient(r.center(), max(r.width(), r.height()) * 0.6)
        g.setColorAt(0, aurora(0.05 + 0.13 * self._hover))
        g.setColorAt(1, aurora(0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, 14, 14)
        p.setBrush(white(0.03 * self._hover))
        pen = QPen(aurora(0.25 + 0.6 * self._hover) if self._hover else white(0.2), 1 + 0.5 * self._hover)
        if self._hover < 1:
            pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)

    def enterEvent(self, _e) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.45)
        self._anim.start()

    def leaveEvent(self, _e) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._animate(1.0)

    def dragLeaveEvent(self, _e) -> None:
        self._animate(0.0)

    def dropEvent(self, e) -> None:
        self._animate(0.0)
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.file_dropped.emit(urls[0].toLocalFile())
            e.acceptProposedAction()




class ProgressLine(QWidget):
    """A 2px line with a white segment sliding across: the app is working."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(2)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(1200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.hide()

    def _get(self) -> float:
        return self._offset

    def _set(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get, _set)

    def start(self) -> None:
        self.show()
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()
        self.hide()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), white(0.06))
        w = 120
        x = round((self.width() + w) * self._offset) - w
        p.fillRect(x, 0, w, 2, white(0.6))


class Segmented(QWidget):
    """Two segments, e.g. Request | Answer."""

    changed = Signal(int)

    def __init__(self, labels: tuple[str, str]):
        super().__init__()
        self.setObjectName("segmented")
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(0)
        self.buttons = []
        for i, label in enumerate(labels):
            b = QPushButton(label)
            b.setProperty("segment", True)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self.select(i, emit=True))
            h.addWidget(b)
            self.buttons.append(b)
        self.select(0)

    def select(self, i: int, emit: bool = False) -> None:
        for k, b in enumerate(self.buttons):
            b.setChecked(k == i)
        if emit:
            self.changed.emit(i)


def keycap(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("keycap")
    return label


# ---------- brand and motion ----------

AURORA = QColor(127, 202, 222)  # the site's logo aurora, used only as light, never as a fill colour


def aurora(alpha: float) -> QColor:
    c = QColor(AURORA)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


# Easter eggs: constellations that now and then light up in the starfield. Each is a list of
# polylines in a unit box; the stars sit at the points.
CONSTELLATIONS = {
    "ursa": [
        [(0.0, 0.35), (0.18, 0.30), (0.32, 0.38), (0.47, 0.45), (0.52, 0.70), (0.78, 0.75), (0.82, 0.48), (0.47, 0.45)]
    ],
    "lock": [
        [(0.32, 0.45), (0.32, 0.25), (0.42, 0.1), (0.58, 0.1), (0.68, 0.25), (0.68, 0.45)],
        [(0.2, 0.45), (0.8, 0.45), (0.8, 0.95), (0.2, 0.95), (0.2, 0.45)],
        [(0.5, 0.62), (0.5, 0.78)],
    ],
    "label": [
        [(0.12, 0.25), (0.0, 0.25), (0.0, 0.75), (0.12, 0.75)],
        [(0.88, 0.25), (1.0, 0.25), (1.0, 0.75), (0.88, 0.75)],
        [(0.25, 0.5), (0.5, 0.5), (0.75, 0.5)],
    ],
    "besk": [
        [(0.0, 0.0), (0.0, 1.0)],
        [(0.0, 0.0), (0.13, 0.1), (0.13, 0.4), (0.0, 0.5), (0.15, 0.6), (0.15, 0.9), (0.0, 1.0)],
        [(0.42, 0.0), (0.28, 0.0), (0.28, 0.5), (0.28, 1.0), (0.42, 1.0)],
        [(0.28, 0.5), (0.39, 0.5)],
        [(0.68, 0.05), (0.56, 0.0), (0.54, 0.3), (0.68, 0.6), (0.66, 0.95), (0.54, 1.0)],
        [(0.8, 0.0), (0.8, 1.0)],
        [(0.95, 0.0), (0.8, 0.55), (0.96, 1.0)],
    ],
}
SHOW_FOR = 9.0  # seconds: 2 to appear, 5 to stay, 2 to fade


class Ground(QWidget):
    """The window background, after the site: navy, a volumetric beam of aurora light that
    sways slowly from the top, a soft glow, and a sparse field of faint twinkling particles.
    The top strip (under the macOS window buttons) moves the window, as a title bar does."""

    DRAG_HEIGHT = 76

    def __init__(self):
        import random

        from PySide6.QtCore import QElapsedTimer, QTimer

        super().__init__()
        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rnd = random.Random(7)
        # x, y in 0..1, radius, twinkle speed and phase, drift
        self._stars = [
            (
                rnd.random(),
                rnd.random(),
                rnd.uniform(0.5, 1.4),
                rnd.uniform(0.3, 1.1),
                rnd.uniform(0, 6.3),
                rnd.uniform(-0.004, 0.004),
            )
            for _ in range(90)
        ]
        self._drag_from = None
        self.names: dict[str, str] = {}  # constellation names in the interface language
        self._rnd = rnd
        self._sky: tuple[str, float, float, float, float] | None = None  # name, start, x, y, size
        self._next_sky = 25.0  # the first one shows up soon, so that it is noticed
        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(50)

    # ---------- moving the window by its top strip ----------

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < self.DRAG_HEIGHT:
            handle = self.window().windowHandle()
            # elsewhere the system move is native; on macOS it can report success and do nothing
            # under the expanded client area, so there the window simply follows the mouse
            if sys.platform == "darwin" or handle is None or not handle.startSystemMove():
                self._drag_from = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_from is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_from)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_from = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.position().y() < self.DRAG_HEIGHT:
            w = self.window()
            w.showNormal() if w.isMaximized() else w.showMaximized()
            return
        super().mouseDoubleClickEvent(e)

    # ---------- constellations ----------

    def _occupied(self) -> list[QRectF]:
        """Where the interface has something to read or press, in this widget's coordinates."""
        from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QTextBrowser

        rects = []
        for w in self.findChildren(QWidget):
            if not w.isVisible() or w.width() <= 0:
                continue
            if isinstance(w, DropZone):
                # its dashed outline: a constellation sits wholly inside the zone or wholly outside
                z = QRectF(w.mapTo(self, w.rect().topLeft()), w.size().toSizeF())
                for edge in (
                    QRectF(z.left(), z.top(), z.width(), 1),
                    QRectF(z.left(), z.bottom(), z.width(), 1),
                    QRectF(z.left(), z.top(), 1, z.height()),
                    QRectF(z.right(), z.top(), 1, z.height()),
                ):
                    rects.append(edge.adjusted(-10, -10, 10, 10))
                continue
            frame = isinstance(w, QFrame) and w.objectName() in ("card", "hair")
            if not (frame or isinstance(w, (QLabel, QAbstractButton, QPlainTextEdit, QTextBrowser, BrandMark))):
                continue
            r = QRectF(w.mapTo(self, w.rect().topLeft()), w.size().toSizeF())
            if isinstance(w, QLabel) and w.text() and not w.wordWrap():
                # a label stretched by its layout occupies only its text
                text_w = min(r.width(), w.sizeHint().width())
                align = w.alignment()
                if align & Qt.AlignmentFlag.AlignHCenter:
                    r.setLeft(r.center().x() - text_w / 2)
                elif align & Qt.AlignmentFlag.AlignRight:
                    r.setLeft(r.right() - text_w)
                r.setWidth(text_w)
            rects.append(r.adjusted(-22, -16, 22, 16))
        return rects

    def show_constellation(self, name: str, now: float | None = None) -> bool:
        """Light up a constellation in a free part of the sky; False if there is no room."""
        t = self._clock.elapsed() / 1000.0 if now is None else now
        w, h = self.width(), self.height()
        aspect = 0.45 if name == "besk" else (0.6 if name == "label" else 1.0)
        busy = self._occupied()
        for size in (220.0, 180.0, 150.0, 120.0, 100.0) if name == "besk" else (150.0, 115.0, 90.0):
            spots = []
            for gx in range(30):
                for gy in range(30):
                    x = 16 + (w - size - 32) * gx / 29
                    y = self.DRAG_HEIGHT + 8 + (h - self.DRAG_HEIGHT - size * aspect - 48) * gy / 29
                    box = QRectF(x, y, size, size * aspect + 30)  # with the name under it
                    if box.right() < w - 8 and box.bottom() < h - 8 and not any(box.intersects(r) for r in busy):
                        spots.append((x, y))
            if spots:
                x, y = self._rnd.choice(spots)
                self._sky = (name, t, x, y, size)
                return True
        return False

    def _paint_sky(self, p: QPainter, t: float) -> None:
        if (self._sky is None and t >= self._next_sky
                and not self.show_constellation(
                    self._rnd.choice(["ursa", "lock", "label"]), t)):
            self._next_sky = t + 20  # no free sky right now: try again a little later
        if self._sky is None:
            return
        name, start, x, y, size = self._sky
        age = t - start
        if age > SHOW_FOR:
            self._sky = None
            self._next_sky = t + self._rnd.uniform(60, 100)
            return
        env = max(0.0, min(1.0, age / 2.0, (SHOW_FOR - age) / 2.0))
        aspect = 0.45 if name == "besk" else (0.6 if name == "label" else 1.0)
        from PySide6.QtCore import QPointF

        def at(pt):
            return QPointF(x + pt[0] * size, y + pt[1] * size * aspect)

        p.setPen(QPen(white(0.16 * env), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for line in CONSTELLATIONS[name]:
            for a, b in itertools.pairwise(line):
                p.drawLine(at(a), at(b))
        p.setPen(Qt.PenStyle.NoPen)
        for line in CONSTELLATIONS[name]:
            for pt in line:
                p.setBrush(aurora(0.25 * env))
                p.drawEllipse(at(pt), 4.0, 4.0)
                p.setBrush(white(0.75 * env))
                p.drawEllipse(at(pt), 1.6, 1.6)
        label = self.names.get(name, "")
        if label:
            font = QFont("Space Grotesk")
            font.setPixelSize(10)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.6)
            p.setFont(font)
            p.setPen(white(0.4 * env))
            p.drawText(QPointF(x, y + size * aspect + 22), label.upper())

    # ---------- light ----------

    def paintEvent(self, e) -> None:
        import math

        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QConicalGradient, QRadialGradient

        super().paintEvent(e)
        t = self._clock.elapsed() / 1000.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # the glow: a wide aurora wash at the top, drifting left and right
        cx = w * (0.5 + 0.22 * math.sin(t / 9.0))
        r = max(w, h) * 0.75
        g = QRadialGradient(cx, -r * 0.30, r)
        g.setColorAt(0.0, aurora(0.26))
        g.setColorAt(0.45, aurora(0.08))
        g.setColorAt(1.0, aurora(0.0))
        p.fillRect(self.rect(), g)
        # the beam: a narrow cone of light from above the top edge, swaying a few degrees
        # the source of the beam wanders left and right while the beam sways, two slow rhythms
        origin = QPointF(w * (0.62 + 0.16 * math.sin(t / 11.0)), -h * 0.08)
        sway = 9.0 * math.sin(t / 7.0)
        cone = QConicalGradient(origin, 250 + sway)
        cone.setColorAt(0.00, aurora(0.0))
        cone.setColorAt(0.03, aurora(0.16))
        cone.setColorAt(0.07, aurora(0.05))
        cone.setColorAt(0.11, aurora(0.0))
        cone.setColorAt(1.00, aurora(0.0))
        p.save()
        fade = QRadialGradient(origin, max(w, h) * 1.1)
        fade.setColorAt(0, QColor(0, 0, 0, 255))
        fade.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(cone)
        p.setPen(Qt.PenStyle.NoPen)
        p.setOpacity(0.9)
        p.drawRect(self.rect())
        p.restore()
        # particles: a sparse starfield, each one breathing slowly
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, rad, speed, phase, drift in self._stars:
            a = 0.06 + 0.22 * (0.5 + 0.5 * math.sin(t * speed + phase))
            px = ((x + drift * t) % 1.0) * w
            p.setBrush(white(a))
            p.drawEllipse(QPointF(px, y * h), rad, rad)
        self._paint_sky(p, t)


class BrandMark(QWidget):
    """The app mark and wordmark. On hover the bar inside the mark sweeps across like a
    redaction and the mark picks up the aurora glow. Click returns to the start."""

    clicked = Signal()

    def __init__(self, name: str = "Askbase"):
        super().__init__()
        self.name = name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        font = QFont("Inter")
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.ExtraBold)
        self.font_ = font
        from PySide6.QtGui import QFontMetrics

        self.setFixedWidth(32 + 10 + QFontMetrics(font).horizontalAdvance(name) + 4)
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get(self) -> float:
        return self._hover

    def _set(self, v: float) -> None:
        self._hover = v
        self.update()

    hover = Property(float, _get, _set)

    def _to(self, v: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(v)
        self._anim.start()

    def enterEvent(self, _e) -> None:
        self._to(1.0)

    def leaveEvent(self, _e) -> None:
        self._to(0.0)

    def mouseReleaseEvent(self, e) -> None:
        if self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _e) -> None:
        from PySide6.QtGui import QLinearGradient, QRadialGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self._hover
        box = QRectF(2, 2, 28, 28)
        if h:
            g = QRadialGradient(box.center(), 22)
            g.setColorAt(0, aurora(0.35 * h))
            g.setColorAt(1, aurora(0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(box.center(), 22, 22)
        p.setBrush(QColor(11, 16, 38))
        lg = QLinearGradient(box.topLeft(), box.bottomRight())
        lg.setColorAt(0, white(0.85))
        lg.setColorAt(1, aurora(0.55 + 0.45 * h))
        p.setPen(QPen(lg, 1.6))
        p.drawRoundedRect(box, 8, 8)
        # three rows of a result, the top one a question that fills in on
        # hover: the product in one glyph. Not pii-roundtrip's redaction bar,
        # which is a different promise entirely.
        rows = ((9.5, 11.0), (14.5, 15.5), (19.5, 7.0))
        left = box.left() + 6.0
        for i, (y, full) in enumerate(rows):
            fade = (0.95, 0.68, 0.40)[i]
            p.setPen(QPen(white(fade), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            # on hover each row grows to its full width, top one first
            grow = max(0.0, min(1.0, h * 1.6 - i * 0.3))
            w = full * (0.72 + 0.28 * grow)
            p.drawLine(QPointF(left, y), QPointF(left + w, y))
        # the caret on the question row
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(white(0.9))
        p.drawRoundedRect(QRectF(box.left() + 19.4, 7.6, 1.8, 4.0), 0.9, 0.9)
        # The wordmark. Cut once by accident along with the old glyph, which
        # left the header with a mark and no name at all.
        p.setFont(self.font_)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(42, 0, self.width() - 42, self.height()),
                   Qt.AlignmentFlag.AlignVCenter, self.name)


class HoverGlow(QObject):
    """Soft glow that rises under a button on hover and a 1px lift, like the site's buttons."""

    def __init__(self, button: QPushButton, color: QColor):
        super().__init__(button)
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        self.button = button
        self.effect = QGraphicsDropShadowEffect(button)
        self.effect.setOffset(0, 0)
        self.effect.setBlurRadius(0)
        self.effect.setColor(color)
        button.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"blurRadius", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        button.installEventFilter(self)

    def eventFilter(self, obj, e) -> bool:
        from PySide6.QtCore import QEvent

        if e.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            on = e.type() == QEvent.Type.Enter
            self.anim.stop()
            self.anim.setStartValue(self.effect.blurRadius())
            self.anim.setEndValue(28 if on else 0)
            self.anim.start()
        return False


def glow(button: QPushButton, primary: bool = False) -> QPushButton:
    HoverGlow(button, white(0.45) if primary else aurora(0.55))
    return button


class LangSwitch(QWidget):
    """RU | EN, the interface language."""

    changed = Signal(str)

    def __init__(self, current: str):
        super().__init__()
        self.setObjectName("segmented")
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(0)
        for code in ("ru", "en"):
            b = QPushButton(code.upper())
            b.setProperty("segment", True)
            b.setCheckable(True)
            b.setChecked(code == current)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=code, cur=current: c != cur and self.changed.emit(c))
            h.addWidget(b)
