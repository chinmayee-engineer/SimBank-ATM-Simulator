from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget

from shared import security


class CardPreviewWidget(QWidget):
    """A custom-painted, credit-card-shaped preview showing SIMULATION test data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 220)
        self.card_number = "0000 0000 0000 0000"
        self.holder = "CARDHOLDER NAME"
        self.expiry = "MM/YY"
        self.status = "ACTIVE"
        self.show_full = True
        self.network = "SIMNET"

    def sizeHint(self) -> QSize:
        return QSize(380, 230)

    def set_card(self, card_number: str, holder: str, expiry_month: int, expiry_year: int,
                 status: str = "ACTIVE", show_full: bool = True):
        self.show_full = show_full
        self.card_number = (security.format_card_number(card_number) if show_full
                             else security.mask_card_number(card_number))
        self.holder = holder.upper()
        self.expiry = f"{expiry_month:02d}/{str(expiry_year)[-2:]}"
        self.status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if self.status == "ACTIVE":
            gradient.setColorAt(0, QColor("#123a5e"))
            gradient.setColorAt(1, QColor("#0b1220"))
        elif self.status == "LOCKED":
            gradient.setColorAt(0, QColor("#5e3d12"))
            gradient.setColorAt(1, QColor("#0b1220"))
        elif self.status == "RETAINED":
            gradient.setColorAt(0, QColor("#5e1230"))
            gradient.setColorAt(1, QColor("#0b1220"))
        else:
            gradient.setColorAt(0, QColor("#3a3a3a"))
            gradient.setColorAt(1, QColor("#0b1220"))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#26344d"), 1))
        painter.drawRoundedRect(rect, 18, 18)

        # Bank brand
        painter.setPen(QColor("#e8edf5"))
        f = QFont("Segoe UI", 13)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(rect.left() + 20, rect.top() + 14, rect.width() - 40, 28),
                          Qt.AlignmentFlag.AlignLeft, "SimBank")

        f2 = QFont("Segoe UI", 7)
        f2.setBold(True)
        painter.setFont(f2)
        painter.setPen(QColor("#ffb547"))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + 36, rect.width() - 40, 16),
                          Qt.AlignmentFlag.AlignLeft, "SIMULATION / TEST ONLY")

        # Chip
        chip_rect = QRectF(rect.left() + 22, rect.top() + 62, 44, 34)
        chip_grad = QLinearGradient(chip_rect.topLeft(), chip_rect.bottomRight())
        chip_grad.setColorAt(0, QColor("#f4d97a"))
        chip_grad.setColorAt(1, QColor("#c9a227"))
        painter.setBrush(QBrush(chip_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(chip_rect, 6, 6)

        # Status badge
        painter.setPen(QColor("#e8edf5"))
        f3 = QFont("Segoe UI", 8)
        f3.setBold(True)
        painter.setFont(f3)
        painter.drawText(QRectF(rect.right() - 110, rect.top() + 14, 90, 20),
                          Qt.AlignmentFlag.AlignRight, self.status)

        # Card number
        f4 = QFont("Consolas", 15)
        f4.setBold(True)
        f4.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
        painter.setFont(f4)
        painter.setPen(QColor("#e8edf5"))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + 116, rect.width() - 40, 30),
                          Qt.AlignmentFlag.AlignLeft, self.card_number)

        # Holder / expiry
        f5 = QFont("Segoe UI", 8)
        painter.setFont(f5)
        painter.setPen(QColor("#8ba0bd"))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + 156, 140, 14),
                          Qt.AlignmentFlag.AlignLeft, "CARD HOLDER")
        painter.drawText(QRectF(rect.width() - 90, rect.top() + 156, 80, 14),
                          Qt.AlignmentFlag.AlignRight, "VALID THRU")

        f6 = QFont("Consolas", 11)
        f6.setBold(True)
        painter.setFont(f6)
        painter.setPen(QColor("#e8edf5"))
        painter.drawText(QRectF(rect.left() + 20, rect.top() + 170, 180, 20),
                          Qt.AlignmentFlag.AlignLeft, self.holder[:22])
        painter.drawText(QRectF(rect.width() - 90, rect.top() + 170, 80, 20),
                          Qt.AlignmentFlag.AlignRight, self.expiry)

        # Network wordmark
        f7 = QFont("Segoe UI", 12)
        f7.setBold(True)
        painter.setFont(f7)
        painter.setPen(QColor("#00c896"))
        painter.drawText(QRectF(rect.right() - 110, rect.bottom() - 34, 90, 24),
                          Qt.AlignmentFlag.AlignRight, self.network)
