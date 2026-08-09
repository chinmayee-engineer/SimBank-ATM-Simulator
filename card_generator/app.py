from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QFormLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QDialogButtonBox, QAbstractItemView, QSplitter, QStatusBar, QToolBar,
    QComboBox, QFrame, QApplication
)

from shared import db, security
from shared.theme import DARK_QSS
from card_generator.widgets import CardPreviewWidget

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Kabir", "Ananya", "Diya",
               "Sara", "Meera", "Priya", "Neha", "Karthik", "Arjun", "Vikram", "Sneha",
               "Pooja", "Rahul", "Sanjay", "Divya", "Kiran", "Manav", "Riya", "Tara"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Reddy", "Nair", "Gupta", "Rao", "Singh",
              "Patel", "Kulkarni", "Menon", "Bose", "Chatterjee", "Das", "Pillai"]


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def status_color(status: str) -> str:
    return {
        "ACTIVE": "#00c896", "INACTIVE": "#8ba0bd", "LOCKED": "#ffb547", "RETAINED": "#ff5470",
    }.get(status, "#8ba0bd")


class IssuedCardDialog(QDialog):
    """Shown once right after generating a card — the only time full secrets are revealed."""

    def __init__(self, card: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Card Issued — SIMULATION")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        preview = CardPreviewWidget()
        preview.set_card(card["card_number"], card["cardholder_name"],
                          card["expiry_month"], card["expiry_year"], "ACTIVE", show_full=True)
        layout.addWidget(preview)

        warn = QLabel("⚠ These test details are shown once. Note them down now.")
        warn.setStyleSheet("color:#ffb547; font-weight:600;")
        layout.addWidget(warn)

        form = QFormLayout()
        for label, value in [
            ("Card Number", security.format_card_number(card["card_number"])),
            ("Cardholder", card["cardholder_name"]),
            ("Account Number", card["account_number"]),
            ("Expiry", f"{card['expiry_month']:02d}/{card['expiry_year']}"),
            ("CVV", card["cvv"]),
            ("PIN", card["pin"]),
            ("Opening Balance", f"₹{card['balance']:.2f}"),
        ]:
            v = QLabel(value)
            v.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            form.addRow(QLabel(label + ":"), v)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)


class PinDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.pin_edit = QLineEdit()
        self.pin_edit.setMaxLength(4)
        self.pin_edit.setPlaceholderText("4-digit PIN")
        self.pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New PIN:", self.pin_edit)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setMaxLength(4)
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Confirm PIN:", self.confirm_edit)
        layout.addLayout(form)

        random_btn = QPushButton("Generate Random PIN")
        random_btn.clicked.connect(self._randomize)
        layout.addWidget(random_btn)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.result_pin = None

    def _randomize(self):
        pin = security.generate_pin()
        self.pin_edit.setText(pin)
        self.confirm_edit.setText(pin)

    def _validate(self):
        p1, p2 = self.pin_edit.text().strip(), self.confirm_edit.text().strip()
        if not (p1.isdigit() and len(p1) == 4):
            QMessageBox.warning(self, "Invalid PIN", "PIN must be exactly 4 digits.")
            return
        if p1 != p2:
            QMessageBox.warning(self, "Mismatch", "PINs do not match.")
            return
        self.result_pin = p1
        self.accept()


class CardGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimBank Debit Card Generator — SIMULATION / TEST ONLY")
        self.resize(1180, 720)
        self.setStyleSheet(DARK_QSS)
        self._build_ui()
        self.refresh_table()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("💳 SimBank Debit Card Generator")
        title.setProperty("role", "title")
        header.addWidget(title)
        header.addStretch()
        badge = QLabel("SIMULATION / TEST ONLY — no real bank or money")
        badge.setStyleSheet("color:#ffb547; font-weight:700;")
        header.addWidget(badge)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # ---- Left: generation panel + preview
        left = QFrame()
        left.setObjectName("Card")
        left.setMinimumWidth(360)
        left.setMaximumWidth(420)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(18, 18, 18, 18)
        left_l.setSpacing(10)

        heading = QLabel("GENERATE NEW TEST CARD")
        heading.setProperty("role", "heading")
        left_l.addWidget(heading)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Leave blank for random name")
        form.addRow("Customer Name:", self.name_edit)

        self.balance_spin = QDoubleSpinBox()
        self.balance_spin.setRange(0, 10_000_000)
        self.balance_spin.setDecimals(2)
        self.balance_spin.setValue(10000)
        self.balance_spin.setPrefix("₹ ")
        form.addRow("Opening Balance:", self.balance_spin)

        self.wlimit_spin = QDoubleSpinBox()
        self.wlimit_spin.setRange(1000, 1_000_000)
        self.wlimit_spin.setValue(25000)
        self.wlimit_spin.setPrefix("₹ ")
        form.addRow("Daily Withdrawal Limit:", self.wlimit_spin)

        self.tlimit_spin = QDoubleSpinBox()
        self.tlimit_spin.setRange(1000, 1_000_000)
        self.tlimit_spin.setValue(50000)
        self.tlimit_spin.setPrefix("₹ ")
        form.addRow("Daily Transfer Limit:", self.tlimit_spin)

        self.expiry_spin = QSpinBox()
        self.expiry_spin.setRange(1, 10)
        self.expiry_spin.setValue(4)
        self.expiry_spin.setSuffix(" year(s)")
        form.addRow("Valid For:", self.expiry_spin)

        self.custom_pin_check = QCheckBox("Set custom PIN (else random)")
        form.addRow(self.custom_pin_check)
        self.custom_pin_edit = QLineEdit()
        self.custom_pin_edit.setMaxLength(4)
        self.custom_pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_pin_edit.setEnabled(False)
        self.custom_pin_check.toggled.connect(self.custom_pin_edit.setEnabled)
        form.addRow("Custom PIN:", self.custom_pin_edit)

        left_l.addLayout(form)

        gen_btn = QPushButton("Generate Card")
        gen_btn.setProperty("variant", "primary")
        gen_btn.clicked.connect(self.generate_single)
        left_l.addWidget(gen_btn)

        left_l.addWidget(self._hline())

        bulk_heading = QLabel("BULK TEST-CARD GENERATION")
        bulk_heading.setProperty("role", "heading")
        left_l.addWidget(bulk_heading)
        bulk_row = QHBoxLayout()
        self.bulk_spin = QSpinBox()
        self.bulk_spin.setRange(1, 500)
        self.bulk_spin.setValue(10)
        bulk_row.addWidget(self.bulk_spin)
        bulk_btn = QPushButton("Bulk Generate")
        bulk_btn.clicked.connect(self.generate_bulk)
        bulk_row.addWidget(bulk_btn)
        left_l.addLayout(bulk_row)

        left_l.addWidget(self._hline())

        preview_heading = QLabel("PREVIEW")
        preview_heading.setProperty("role", "heading")
        left_l.addWidget(preview_heading)
        self.preview = CardPreviewWidget()
        left_l.addWidget(self.preview)
        self.reveal_check = QCheckBox("Show full card number in preview")
        self.reveal_check.toggled.connect(self._refresh_preview)
        left_l.addWidget(self.reveal_check)

        left_l.addStretch()
        splitter.addWidget(left)

        # ---- Right: table + management
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, card number or account...")
        self.search_edit.textChanged.connect(self.refresh_table)
        toolbar.addWidget(self.search_edit, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Statuses", "ACTIVE", "INACTIVE", "LOCKED", "RETAINED"])
        self.status_filter.currentIndexChanged.connect(self.refresh_table)
        toolbar.addWidget(self.status_filter)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.clicked.connect(self.refresh_table)
        toolbar.addWidget(refresh_btn)
        right_l.addLayout(toolbar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Card Number", "Holder", "Account No.", "Balance", "Status", "Expiry",
             "Failed Attempts", "Created"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setAlternatingRowColors(True)
        right_l.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.btn_activate = QPushButton("Activate")
        self.btn_deactivate = QPushButton("Deactivate")
        self.btn_lock = QPushButton("Lock")
        self.btn_unlock = QPushButton("Unlock")
        self.btn_retain = QPushButton("Retain")
        self.btn_retain.setProperty("variant", "danger")
        self.btn_change_pin = QPushButton("Change PIN")
        self.btn_reset_pin = QPushButton("Reset PIN")
        self.btn_details = QPushButton("View Full Details")
        self.btn_delete = QPushButton("Delete Card")
        self.btn_delete.setProperty("variant", "danger")

        for b in [self.btn_activate, self.btn_deactivate, self.btn_lock, self.btn_unlock,
                  self.btn_retain, self.btn_change_pin, self.btn_reset_pin, self.btn_details,
                  self.btn_delete]:
            actions.addWidget(b)
        right_l.addLayout(actions)

        self.btn_activate.clicked.connect(lambda: self._set_status("ACTIVE"))
        self.btn_deactivate.clicked.connect(lambda: self._set_status("INACTIVE"))
        self.btn_lock.clicked.connect(lambda: self._set_status("LOCKED"))
        self.btn_unlock.clicked.connect(lambda: self._set_status("ACTIVE"))
        self.btn_retain.clicked.connect(lambda: self._set_status("RETAINED", confirm=True))
        self.btn_change_pin.clicked.connect(self.change_pin)
        self.btn_reset_pin.clicked.connect(self.reset_pin)
        self.btn_details.clicked.connect(self.view_details)
        self.btn_delete.clicked.connect(self.delete_card)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._set_status_message()

    def _hline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #26344d;")
        return line

    # ------------------------------------------------------------- actions --
    def generate_single(self):
        name = self.name_edit.text().strip() or random_name()
        pin = None
        if self.custom_pin_check.isChecked():
            pin = self.custom_pin_edit.text().strip()
            if not (pin.isdigit() and len(pin) == 4):
                QMessageBox.warning(self, "Invalid PIN", "Custom PIN must be exactly 4 digits.")
                return
        card = db.create_card(
            customer_name=name,
            opening_balance=self.balance_spin.value(),
            pin=pin,
            expiry_years=self.expiry_spin.value(),
            withdrawal_limit=self.wlimit_spin.value(),
            transfer_limit=self.tlimit_spin.value(),
        )
        db.log_security_event("CARD_ISSUED", card["card_number"], "", f"Issued for {name}")
        self.name_edit.clear()
        self.custom_pin_edit.clear()
        self.custom_pin_check.setChecked(False)
        self.refresh_table()
        dlg = IssuedCardDialog(card, self)
        dlg.exec()

    def generate_bulk(self):
        count = self.bulk_spin.value()
        confirm = QMessageBox.question(
            self, "Bulk Generate",
            f"Generate {count} random SIMULATION test cards?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for _ in range(count):
            name = random_name()
            balance = random.choice([5000, 10000, 15000, 25000, 50000, 100000])
            db.create_card(customer_name=name, opening_balance=balance)
        db.log_security_event("BULK_CARD_ISSUED", "", "", f"{count} test cards generated")
        self.refresh_table()
        QMessageBox.information(self, "Bulk Generation Complete",
                                 f"{count} SIMULATION test cards were created.\n"
                                 f"Use 'View Full Details' on any row to see PIN/CVV.")

    def refresh_table(self):
        cards = db.list_cards()
        search = self.search_edit.text().strip().lower()
        status_f = self.status_filter.currentText()
        rows = []
        for c in cards:
            if search and search not in c["cardholder_name"].lower() \
                    and search not in c["card_number"] and search not in c["account_number"]:
                continue
            if status_f != "All Statuses" and c["status"] != status_f:
                continue
            rows.append(c)

        self.table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            values = [
                security.mask_card_number(c["card_number"]),
                c["cardholder_name"],
                c["account_number"],
                f"₹{c['balance']:.2f}",
                c["status"],
                f"{c['expiry_month']:02d}/{c['expiry_year']}",
                str(c["failed_attempts"]),
                c["created_at"][:19].replace("T", " "),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c["card_id"])
                if col == 4:
                    item.setForeground(QColor(status_color(c["status"])))
                self.table.setItem(r, col, item)
        self._set_status_message()

    def _set_status_message(self):
        cards = db.list_cards()
        active = sum(1 for c in cards if c["status"] == "ACTIVE")
        self.status_bar.showMessage(
            f"Total cards: {len(cards)}  |  Active: {active}  |  "
            f"All data is SIMULATED and stored locally in SQLite.")

    def _selected_card_id(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self):
        card_id = self._selected_card_id()
        if card_id is None:
            return
        self._refresh_preview()

    def _refresh_preview(self):
        card_id = self._selected_card_id()
        if card_id is None:
            return
        c = db.get_card(card_id)
        if not c:
            return
        self.preview.set_card(c["card_number"], c["cardholder_name"], c["expiry_month"],
                               c["expiry_year"], c["status"], show_full=self.reveal_check.isChecked())

    def _require_selection(self) -> int | None:
        card_id = self._selected_card_id()
        if card_id is None:
            QMessageBox.information(self, "No Selection", "Select a card from the table first.")
            return None
        return card_id

    def _set_status(self, status: str, confirm: bool = False):
        card_id = self._require_selection()
        if card_id is None:
            return
        if confirm:
            reply = QMessageBox.question(
                self, "Confirm Retain",
                "Retaining this card simulates the ATM swallowing it. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        db.set_card_status(card_id, status)
        c = db.get_card(card_id)
        db.log_security_event(f"CARD_{status}", c["card_number"], "", "Changed via Card Generator")
        self.refresh_table()
        self._refresh_preview()

    def change_pin(self):
        card_id = self._require_selection()
        if card_id is None:
            return
        dlg = PinDialog("Change PIN", self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_pin:
            db.set_pin(card_id, dlg.result_pin)
            c = db.get_card(card_id)
            db.log_security_event("PIN_CHANGED", c["card_number"], "", "Changed via Card Generator")
            QMessageBox.information(self, "PIN Updated", "PIN was updated successfully.")
            self.refresh_table()

    def reset_pin(self):
        card_id = self._require_selection()
        if card_id is None:
            return
        new_pin = security.generate_pin()
        db.set_pin(card_id, new_pin)
        c = db.get_card(card_id)
        db.log_security_event("PIN_RESET", c["card_number"], "", "Reset via Card Generator")
        QMessageBox.information(self, "PIN Reset", f"New PIN generated: {new_pin}\n"
                                                     f"(Shown once — note it down.)")
        self.refresh_table()

    def view_details(self):
        card_id = self._require_selection()
        if card_id is None:
            return
        c = db.get_card(card_id)
        QMessageBox.information(
            self, "Card Details (SIMULATION)",
            f"Card Number: {security.format_card_number(c['card_number'])}\n"
            f"Cardholder: {c['cardholder_name']}\n"
            f"Account Number: {c['account_number']}\n"
            f"Balance: ₹{c['balance']:.2f}\n"
            f"Expiry: {c['expiry_month']:02d}/{c['expiry_year']}\n"
            f"CVV: {c['cvv']}\n"
            f"Status: {c['status']}\n"
            f"Failed PIN Attempts: {c['failed_attempts']}\n"
            f"Created: {c['created_at']}\n\n"
            f"Note: PIN is stored as a salted hash and cannot be displayed — "
            f"use 'Change PIN' or 'Reset PIN' if needed."
        )

    def delete_card(self):
        card_id = self._require_selection()
        if card_id is None:
            return
        c = db.get_card(card_id)
        reply = QMessageBox.question(
            self, "Delete Card",
            f"Permanently delete card for {c['cardholder_name']}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_card(card_id)
            db.log_security_event("CARD_DELETED", c["card_number"], "", "Deleted via Card Generator")
            self.refresh_table()
