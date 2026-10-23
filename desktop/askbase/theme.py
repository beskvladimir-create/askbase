"""BESK TECH look for Askbase: navy ground, hairline cards, white primary buttons, no colour accent.

Fonts (SIL Open Font License) ship inside the package: Inter for text, Space Grotesk for
micro-labels and placeholders.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

FONTS = Path(__file__).with_name("fonts")

GROUND = "#0B1026"
CARD = "#141B33"
TEXT = "#9CA3AF"
MUTED = "#6B7280"
PAPER = "#FAFAFA"
HAIR = "rgba(255, 255, 255, 0.10)"
HAIR_2 = "rgba(255, 255, 255, 0.20)"

STYLE = f"""
* {{ font-family: "Inter"; font-size: 14px; color: {PAPER}; }}
QMainWindow, QDialog, QWidget#root {{ background: {GROUND}; }}
QLabel {{ color: {TEXT}; background: transparent; }}
QLabel#doctitle {{ color: rgba(250, 250, 250, 0.64); font-size: 13px; font-weight: 600; }}
QLabel#headline {{ color: #FFFFFF; font-size: 26px; font-weight: 800; }}
QLabel#sub {{ color: {TEXT}; font-size: 15px; }}
QLabel#micro {{ font-family: "Space Grotesk"; color: {TEXT}; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; }}
QLabel#trust {{ font-family: "Playfair Display"; font-style: italic; font-size: 17px; color: rgba(255, 255, 255, 0.72); }}
QLabel#summary, QLabel#footer, QLabel#note {{ color: {TEXT}; font-size: 13px; }}
QLabel#errtitle {{ color: #FFFFFF; font-size: 17px; font-weight: 600; }}
QLabel#errbody {{ color: {TEXT}; font-size: 14px; }}
QPushButton#brand {{ background: transparent; border: none; padding: 0; min-height: 0; color: #FFFFFF; font-size: 14px; font-weight: 800; text-align: left; }}
QPushButton#brand:hover {{ color: {PAPER}; }}
QPushButton[small="true"] {{ min-height: 32px; padding: 0 14px; border-radius: 10px; font-size: 13px; }}
QLabel#status {{ color: {TEXT}; font-size: 12px; padding: 6px 24px 0 24px; }}
QPushButton#remove {{ min-height: 0; padding: 0; border-radius: 8px; background: transparent; color: {MUTED}; font-size: 12px; font-weight: 400; }}
QPushButton#remove:hover {{ background: rgba(255, 255, 255, 0.08); color: #FFFFFF; }}
QTextBrowser#terms {{ background: transparent; border: none; color: {TEXT}; font-size: 14px; }}
QLabel#saved {{ color: {TEXT}; font-size: 13px; background: rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 10px 14px; }}
QLabel#keycap {{ color: #FFFFFF; font-size: 12px; font-weight: 600; border: 1px solid {HAIR_2}; border-radius: 8px; padding: 1px 6px; }}
QTextBrowser#paper {{ background: {PAPER}; border: none; border-radius: 8px; padding: 28px 32px; color: #111827; }}
QFrame#card {{ background: {CARD}; border: 1px solid {HAIR}; border-radius: 14px; }}
QFrame#hair {{ background: {HAIR}; max-height: 1px; min-height: 1px; border: none; }}
QPlainTextEdit#doc {{ background: transparent; border: none; color: rgba(250, 250, 250, 0.9); font-size: 15px;
  selection-background-color: rgba(255, 255, 255, 0.22); }}

QPushButton {{ min-height: 40px; padding: 0 20px; border-radius: 12px; font-size: 14px; font-weight: 600;
  color: #FFFFFF; background: rgba(255, 255, 255, 0.08); border: none; }}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.13); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 0.18); }}
QPushButton[primary="true"] {{ background: #FFFFFF; color: {GROUND}; }}
QPushButton[primary="true"]:hover {{ background: {PAPER}; }}
QPushButton[primary="true"]:pressed {{ background: #E5E7EB; }}
QLabel#wordmark {{ color: #FFFFFF; font-size: 15px; font-weight: 800; }}
QLabel#maker {{ color: {TEXT}; font-size: 12px; }}
QLabel#aboutname {{ color: #FFFFFF; font-size: 22px; font-weight: 900; }}
QPushButton[link="true"] {{ border: none; background: transparent; padding: 0; min-height: 0; color: {TEXT}; font-weight: 400; font-size: 13px; }}
QPushButton[link="true"]:hover {{ color: #FFFFFF; }}
QPushButton[recent="true"] {{ border: none; background: transparent; border-radius: 8px; min-height: 36px; padding: 0 12px; text-align: left;
  font-weight: 400; color: {PAPER}; }}
QPushButton[recent="true"]:hover {{ background: rgba(255, 255, 255, 0.04); }}
QWidget#segmented {{ border: 1px solid {HAIR}; border-radius: 8px; }}
QPushButton[segment="true"] {{ min-height: 24px; padding: 0 14px; border: none; background: transparent; border-radius: 8px; font-size: 12px;
  color: {TEXT}; }}
QPushButton[segment="true"]:checked {{ background: rgba(255, 255, 255, 0.10); color: #FFFFFF; }}

QMenu {{ background: {CARD}; border: 1px solid {HAIR_2}; border-radius: 12px; padding: 4px; }}
QMenu::item {{ padding: 8px 16px; border-radius: 8px; color: {PAPER}; }}
QMenu::item:selected {{ background: rgba(255, 255, 255, 0.08); }}
QLineEdit {{ background: {CARD}; border: 1px solid {HAIR_2}; border-radius: 8px; padding: 8px 10px; color: {PAPER}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 10px 12px; border-radius: 8px; color: {PAPER}; }}
QListWidget::item:selected {{ background: rgba(255, 255, 255, 0.10); }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {HAIR_2}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QTableWidget {{ background: transparent; border: 1px solid {HAIR}; border-radius: 12px; gridline-color: transparent;
  color: {PAPER}; font-size: 14px; }}
QTableWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {HAIR}; }}
QTableWidget::item:selected {{ background: rgba(255, 255, 255, 0.10); color: #FFFFFF; }}
QTableWidget QHeaderView::section {{ background: {CARD}; color: {MUTED};
  font-family: "Space Grotesk"; font-size: 11px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase;
  border: none; border-bottom: 1px solid {HAIR_2}; padding: 10px 12px; text-align: left; }}
QTableWidget QTableCornerButton::section {{ background: transparent; border: none; }}
QComboBox {{ background: {CARD}; border: 1px solid {HAIR_2}; border-radius: 8px; padding: 8px 10px; color: {PAPER}; min-height: 24px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {HAIR_2}; selection-background-color: rgba(255,255,255,0.10); color: {PAPER}; }}
QToolTip {{ background: {CARD}; color: {PAPER}; border: 1px solid {HAIR_2}; border-radius: 8px; padding: 6px 8px; }}
"""


def apply(app: QApplication) -> None:
    for f in sorted(FONTS.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter", 14))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)


def mono() -> QFont:
    font = QFont("Space Grotesk", 13)
    font.setWeight(QFont.Weight.DemiBold)
    return font
