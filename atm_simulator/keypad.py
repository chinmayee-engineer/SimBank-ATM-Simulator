from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout


class NumericKeypad(QWidget):
    """A reusable numeric keypad. Feeds digits into a bound QLineEdit."""

    submitted = Signal(str)
    cancelled = Signal()

    def __init__(self, target: QLineEdit, max_length: int = 4, parent=None):
        super().__init__(parent)
        self.target = target
        self.max_length = max_length
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)
        buttons = [
            ("1", 0, 0), ("2", 0, 1), ("3", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2),
            ("⌫", 3, 0), ("0", 3, 1), ("C", 3, 2),
        ]
        for label, row, col in buttons:
            btn = QPushButton(label)
            btn.setProperty("variant", "keypad")
            btn.clicked.connect(lambda checked=False, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)
        layout.addLayout(grid)

        action_row = QHBoxLayout()
        self.enter_btn = QPushButton("ENTER")
        self.enter_btn.setProperty("variant", "primary")
        self.enter_btn.clicked.connect(self._on_enter)
        self.cancel_btn = QPushButton("CANCEL")
        self.cancel_btn.setProperty("variant", "danger")
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.enter_btn)
        layout.addLayout(action_row)

    def _on_key(self, label: str):
        if label == "C":
            self.target.clear()
        elif label == "⌫":
            self.target.setText(self.target.text()[:-1])
        else:
            if len(self.target.text()) < self.max_length:
                self.target.setText(self.target.text() + label)

    def _on_enter(self):
        self.submitted.emit(self.target.text())
