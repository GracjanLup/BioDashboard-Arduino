from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class ThemePalette:
    background: str
    panel: str
    panel_alt: str
    border: str
    text: str
    muted: str
    accent: str
    success: str
    warning: str
    danger: str
    top_bar: str
    hover: str
    hover_border: str
    pressed: str
    disabled_text: str
    disabled_background: str
    primary: str
    primary_border: str
    primary_hover: str
    danger_background: str
    danger_border: str
    danger_hover: str
    sidebar_hover: str
    sidebar_checked: str
    input_background: str
    table_alternate: str
    table_selection: str
    event_text: str


THEME_MEDICAL_DARK = "Medical Dark"
THEME_HIGH_CONTRAST_DARK = "High Contrast Dark"


THEMES = {
    THEME_MEDICAL_DARK: ThemePalette(
        background=COLOR_BACKGROUND,
        panel=COLOR_PANEL,
        panel_alt=COLOR_PANEL_ALT,
        border=COLOR_BORDER,
        text=COLOR_TEXT,
        muted=COLOR_MUTED,
        accent=COLOR_ACCENT,
        success=COLOR_SUCCESS,
        warning=COLOR_WARNING,
        danger=COLOR_DANGER,
        top_bar="#111821",
        hover="#223040",
        hover_border="#35516a",
        pressed="#1d2935",
        disabled_text="#546475",
        disabled_background="#121820",
        primary="#1d596f",
        primary_border="#2f7d99",
        primary_hover="#236b85",
        danger_background="#4d2228",
        danger_border="#74404a",
        danger_hover="#62303a",
        sidebar_hover="#18222d",
        sidebar_checked="#18313c",
        input_background="#111821",
        table_alternate="#111821",
        table_selection="#21485a",
        event_text="#c7d2de",
    ),
    THEME_HIGH_CONTRAST_DARK: ThemePalette(
        background="#000000",
        panel="#050505",
        panel_alt="#111111",
        border="#f8fafc",
        text="#ffffff",
        muted="#e5e7eb",
        accent="#00e5ff",
        success="#00ff66",
        warning="#ffd400",
        danger="#ff4d4d",
        top_bar="#000000",
        hover="#1f2937",
        hover_border="#ffffff",
        pressed="#111827",
        disabled_text="#9ca3af",
        disabled_background="#101010",
        primary="#004f63",
        primary_border="#00e5ff",
        primary_hover="#006f8c",
        danger_background="#5f0000",
        danger_border="#ff4d4d",
        danger_hover="#7f1111",
        sidebar_hover="#111827",
        sidebar_checked="#003744",
        input_background="#050505",
        table_alternate="#111111",
        table_selection="#004b5f",
        event_text="#ffffff",
    ),
}

_active_palette = THEMES[THEME_MEDICAL_DARK]


def theme_palette(theme_name: str | None = None) -> ThemePalette:
    if theme_name is None:
        return _active_palette
    return THEMES.get(theme_name, THEMES[THEME_MEDICAL_DARK])


def apply_theme(app: QApplication, theme_name: str = THEME_MEDICAL_DARK) -> None:
    global _active_palette

    _active_palette = theme_palette(theme_name)

    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(_stylesheet(_active_palette))


def color_for_status(status: str) -> str:
    colors = _status_colors(_active_palette)
    return colors.get(status.upper(), _active_palette.muted)


def _status_colors(palette: ThemePalette) -> dict[str, str]:
    return {
        STATUS_RELAX: palette.success,
        STATUS_NORMAL: palette.accent,
        STATUS_AROUSED: palette.warning,
        "CONNECTED": palette.success,
        "OFFLINE": palette.muted,
        "WAITING": palette.muted,
        "INVALID": palette.danger,
        "ERROR": palette.danger,
        "NO DATA": palette.muted,
        "IN RANGE": palette.success,
        "LOW": palette.warning,
        "ELEVATED": palette.warning,
    }


def _stylesheet(palette: ThemePalette) -> str:
    return f"""
QMainWindow {{
    background: {palette.background};
    color: {palette.text};
}}

QWidget#AppRoot, QWidget#Body, QWidget#PageContent, QWidget#PlainPage {{
    background: {palette.background};
    color: {palette.text};
}}

QLabel {{
    background: transparent;
    color: {palette.text};
}}

QFrame#TopBar {{
    background: {palette.top_bar};
    border-bottom: 1px solid {palette.border};
}}

QFrame#Sidebar {{
    background: {palette.top_bar};
    border-right: 1px solid {palette.border};
}}

QFrame#MetricCard, QFrame#PanelCard, QTextEdit#EventLog {{
    background: {palette.panel};
    border: 1px solid {palette.border};
    border-radius: 8px;
}}

QLabel#AppTitle {{
    color: {palette.text};
    font-size: 18px;
    font-weight: 700;
}}

QLabel#SectionTitle {{
    color: {palette.text};
    font-size: 14px;
    font-weight: 650;
}}

QLabel#MetricTitle {{
    color: {palette.muted};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
}}

QLabel#MetricValue {{
    color: {palette.text};
    font-size: 28px;
    font-weight: 700;
}}

QLabel#MetricUnit, QLabel#MutedLabel {{
    color: {palette.muted};
}}

QLabel#ModeIndicator, QLabel#DetailLabel {{
    background: {palette.input_background};
    border: 1px solid {palette.border};
    border-radius: 7px;
    color: {palette.muted};
}}

QLabel#ModeIndicator {{
    padding: 6px 10px;
}}

QLabel#DetailLabel {{
    padding: 9px 10px;
    font-size: 12px;
}}

QPushButton, QToolButton {{
    background: {palette.panel_alt};
    border: 1px solid {palette.border};
    border-radius: 7px;
    color: {palette.text};
    padding: 8px 12px;
    font-weight: 600;
}}

QPushButton:hover, QToolButton:hover {{
    background: {palette.hover};
    border-color: {palette.hover_border};
}}

QPushButton:pressed, QToolButton:pressed {{
    background: {palette.pressed};
}}

QPushButton:disabled, QToolButton:disabled {{
    color: {palette.disabled_text};
    background: {palette.disabled_background};
    border-color: {palette.panel_alt};
}}

QPushButton#PrimaryButton {{
    background: {palette.primary};
    border-color: {palette.primary_border};
}}

QPushButton#PrimaryButton:hover {{
    background: {palette.primary_hover};
}}

QPushButton#DangerButton {{
    background: {palette.danger_background};
    border-color: {palette.danger_border};
}}

QPushButton#DangerButton:hover {{
    background: {palette.danger_hover};
}}

QPushButton#SidebarButton {{
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 10px 12px;
    text-align: left;
    color: {palette.muted};
}}

QPushButton#SidebarButton:hover {{
    background: {palette.sidebar_hover};
    color: {palette.text};
}}

QPushButton#SidebarButton:checked {{
    background: {palette.sidebar_checked};
    color: {palette.text};
}}

QComboBox, QSpinBox, QLineEdit {{
    background: {palette.input_background};
    border: 1px solid {palette.border};
    border-radius: 7px;
    color: {palette.text};
    padding: 7px 9px;
    min-height: 20px;
}}

QComboBox::drop-down {{
    border: 0;
    width: 24px;
}}

QProgressBar {{
    background: {palette.input_background};
    border: 1px solid {palette.border};
    border-radius: 6px;
    color: {palette.text};
    min-height: 18px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {palette.accent};
    border-radius: 5px;
}}

QTableView {{
    background: {palette.panel};
    border: 1px solid {palette.border};
    border-radius: 8px;
    gridline-color: {palette.border};
    selection-background-color: {palette.table_selection};
    alternate-background-color: {palette.table_alternate};
}}

QHeaderView::section {{
    background: {palette.input_background};
    color: {palette.muted};
    border: 0;
    border-bottom: 1px solid {palette.border};
    padding: 8px;
    font-weight: 600;
}}

QTextEdit#EventLog {{
    color: {palette.event_text};
    padding: 8px;
}}

QScrollArea {{
    border: 0;
    background: {palette.background};
}}

QScrollArea > QWidget > QWidget {{
    background: {palette.background};
}}

QSplitter::handle {{
    background: {palette.border};
}}
"""
