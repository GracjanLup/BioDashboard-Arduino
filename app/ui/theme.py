"""Application theme and color helpers."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.models import STATUS_AROUSED, STATUS_NORMAL, STATUS_RELAX


COLOR_BACKGROUND = "#0f141a"
COLOR_PANEL = "#151c24"
COLOR_PANEL_ALT = "#1a232d"
COLOR_BORDER = "#263341"
COLOR_TEXT = "#e6edf3"
COLOR_MUTED = "#8ea2b5"
COLOR_ACCENT = "#4fb3d8"
COLOR_SUCCESS = "#61d394"
COLOR_WARNING = "#f2c14e"
COLOR_DANGER = "#e06c75"


STATUS_COLORS = {
    STATUS_RELAX: COLOR_SUCCESS,
    STATUS_NORMAL: COLOR_ACCENT,
    STATUS_AROUSED: COLOR_WARNING,
    "OFFLINE": COLOR_MUTED,
    "WAITING": COLOR_MUTED,
    "INVALID": COLOR_DANGER,
    "ERROR": COLOR_DANGER,
}


def apply_theme(app: QApplication) -> None:
    """Apply the desktop medical dark theme."""

    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(_stylesheet())


def color_for_status(status: str) -> str:
    """Return a stable color for a physiological or connection status."""

    return STATUS_COLORS.get(status.upper(), COLOR_MUTED)


def _stylesheet() -> str:
    return f"""
QMainWindow {{
    background: {COLOR_BACKGROUND};
    color: {COLOR_TEXT};
}}

QWidget#AppRoot, QWidget#Body, QWidget#PageContent, QWidget#PlainPage {{
    background: {COLOR_BACKGROUND};
    color: {COLOR_TEXT};
}}

QLabel {{
    background: transparent;
    color: {COLOR_TEXT};
}}

QFrame#TopBar {{
    background: #111821;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QFrame#Sidebar {{
    background: #111821;
    border-right: 1px solid {COLOR_BORDER};
}}

QFrame#MetricCard, QFrame#PanelCard, QTextEdit#EventLog {{
    background: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}

QLabel#AppTitle {{
    color: {COLOR_TEXT};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#SectionTitle {{
    color: {COLOR_TEXT};
    font-size: 14px;
    font-weight: 650;
}}

QLabel#MetricTitle {{
    color: {COLOR_MUTED};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
}}

QLabel#MetricValue {{
    color: {COLOR_TEXT};
    font-size: 28px;
    font-weight: 700;
}}

QLabel#MetricUnit, QLabel#MutedLabel {{
    color: {COLOR_MUTED};
}}

QPushButton, QToolButton {{
    background: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    color: {COLOR_TEXT};
    padding: 8px 12px;
    font-weight: 600;
}}

QPushButton:hover, QToolButton:hover {{
    background: #223040;
    border-color: #35516a;
}}

QPushButton:pressed, QToolButton:pressed {{
    background: #1d2935;
}}

QPushButton:disabled, QToolButton:disabled {{
    color: #546475;
    background: #121820;
    border-color: #1d2833;
}}

QPushButton#PrimaryButton {{
    background: #1d596f;
    border-color: #2f7d99;
}}

QPushButton#PrimaryButton:hover {{
    background: #236b85;
}}

QPushButton#DangerButton {{
    background: #4d2228;
    border-color: #74404a;
}}

QPushButton#DangerButton:hover {{
    background: #62303a;
}}

QPushButton#SidebarButton {{
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 10px 12px;
    text-align: left;
    color: {COLOR_MUTED};
}}

QPushButton#SidebarButton:hover {{
    background: #18222d;
    color: {COLOR_TEXT};
}}

QPushButton#SidebarButton:checked {{
    background: #18313c;
    color: {COLOR_TEXT};
}}

QComboBox, QSpinBox, QLineEdit {{
    background: #111821;
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    color: {COLOR_TEXT};
    padding: 7px 9px;
    min-height: 20px;
}}

QComboBox::drop-down {{
    border: 0;
    width: 24px;
}}

QTableView {{
    background: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    gridline-color: {COLOR_BORDER};
    selection-background-color: #21485a;
    alternate-background-color: #111821;
}}

QHeaderView::section {{
    background: #111821;
    color: {COLOR_MUTED};
    border: 0;
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 8px;
    font-weight: 600;
}}

QTextEdit#EventLog {{
    color: #c7d2de;
    padding: 8px;
}}

QScrollArea {{
    border: 0;
    background: {COLOR_BACKGROUND};
}}

QScrollArea > QWidget > QWidget {{
    background: {COLOR_BACKGROUND};
}}

QSplitter::handle {{
    background: {COLOR_BORDER};
}}
"""
