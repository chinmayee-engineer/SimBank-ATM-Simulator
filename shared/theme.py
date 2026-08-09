"""Premium dark ATM-style Qt stylesheet used across both applications."""

COLOR_BG = "#0b1220"
COLOR_PANEL = "#121c2e"
COLOR_PANEL_ALT = "#17233a"
COLOR_ACCENT = "#00c896"
COLOR_ACCENT_DARK = "#00a37a"
COLOR_ACCENT_BLUE = "#3d8bff"
COLOR_TEXT = "#e8edf5"
COLOR_MUTED = "#8ba0bd"
COLOR_DANGER = "#ff5470"
COLOR_WARNING = "#ffb547"
COLOR_BORDER = "#26344d"

DARK_QSS = f"""
* {{
    font-family: 'Segoe UI', 'Noto Sans', Arial, sans-serif;
    outline: none;
}}
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
}}
QMainWindow, QDialog {{
    background-color: {COLOR_BG};
}}
#Card, .Card {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 14px;
}}
QLabel {{
    color: {COLOR_TEXT};
    background: transparent;
}}
QLabel[role="muted"] {{
    color: {COLOR_MUTED};
}}
QLabel[role="title"] {{
    color: {COLOR_TEXT};
    font-size: 20px;
    font-weight: 700;
}}
QLabel[role="heading"] {{
    color: {COLOR_ACCENT};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QPushButton {{
    background-color: {COLOR_PANEL_ALT};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #1e2c47;
    border-color: {COLOR_ACCENT};
}}
QPushButton:pressed {{
    background-color: #0f1930;
}}
QPushButton:disabled {{
    color: {COLOR_MUTED};
    background-color: #101827;
}}
QPushButton[variant="primary"] {{
    background-color: {COLOR_ACCENT};
    color: #052018;
    border: none;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {COLOR_ACCENT_DARK};
}}
QPushButton[variant="danger"] {{
    background-color: {COLOR_DANGER};
    color: #2b0410;
    border: none;
}}
QPushButton[variant="danger"]:hover {{
    background-color: #e2405d;
}}
QPushButton[variant="ghost"] {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER};
}}
QPushButton[variant="keypad"] {{
    background-color: {COLOR_PANEL_ALT};
    border-radius: 30px;
    font-size: 18px;
    font-weight: 700;
    min-width: 60px;
    min-height: 60px;
}}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background-color: #0f1830;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_ACCENT};
    selection-color: #052018;
}}
QTableWidget, QTableView {{
    background-color: {COLOR_PANEL};
    alternate-background-color: {COLOR_PANEL_ALT};
    gridline-color: {COLOR_BORDER};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    selection-background-color: #1c3a52;
    selection-color: {COLOR_TEXT};
}}
QHeaderView::section {{
    background-color: {COLOR_PANEL_ALT};
    color: {COLOR_MUTED};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
    font-weight: 700;
}}
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    background: {COLOR_PANEL};
    color: {COLOR_MUTED};
    padding: 10px 18px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLOR_PANEL_ALT};
    color: {COLOR_ACCENT};
    font-weight: 700;
}}
QProgressBar {{
    background-color: {COLOR_PANEL_ALT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    text-align: center;
    color: {COLOR_TEXT};
}}
QProgressBar::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: 8px;
}}
QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QCheckBox, QRadioButton {{
    color: {COLOR_TEXT};
    spacing: 8px;
}}
QToolTip {{
    background-color: {COLOR_PANEL_ALT};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    padding: 4px;
}}
QStatusBar {{
    background-color: {COLOR_PANEL};
    color: {COLOR_MUTED};
    border-top: 1px solid {COLOR_BORDER};
}}
QListWidget {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}
#Badge[status="ACTIVE"] {{ color: {COLOR_ACCENT}; font-weight: 700; }}
#Badge[status="INACTIVE"] {{ color: {COLOR_MUTED}; font-weight: 700; }}
#Badge[status="LOCKED"] {{ color: {COLOR_WARNING}; font-weight: 700; }}
#Badge[status="RETAINED"] {{ color: {COLOR_DANGER}; font-weight: 700; }}
"""
