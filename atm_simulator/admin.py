from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, QFormLayout, QSpinBox,
    QComboBox, QMessageBox, QCheckBox, QGridLayout, QLineEdit, QFrame, QInputDialog
)

from shared import db, security


FAILURE_LABELS = {
    "card_reader": "Card Reader Failure",
    "cash_dispenser": "Cash Dispenser Failure",
    "receipt_printer": "Receipt Printer Failure",
    "network": "Network Unavailable",
    "low_cash": "Low Cash Warning",
    "out_of_cash": "Out of Cash",
    "database": "Database Unavailable",
    "invalid_card": "Force Invalid Card",
    "card_retained": "Force Card Retained",
    "transaction_timeout": "Transaction Timeout",
}


class AdminDashboard(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        title = QLabel("🛠 Admin Dashboard")
        title.setProperty("role", "title")
        header.addWidget(title)
        header.addStretch()
        logout_btn = QPushButton("Logout")
        logout_btn.setProperty("variant", "danger")
        logout_btn.clicked.connect(self._logout)
        header.addWidget(logout_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_cards_tab(), "Card / Customer Management")
        self.tabs.addTab(self._build_cash_tab(), "ATM Cash Management")
        self.tabs.addTab(self._build_logs_tab(), "Security Logs")
        self.tabs.addTab(self._build_diagnostics_tab(), "System Diagnostics")
        self.tabs.addTab(self._build_failure_tab(), "Failure Simulation")

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _logout(self):
        self.main_window.goto_start()

    def refresh_all(self):
        self._refresh_cards()
        self._refresh_atm_combo()
        self._refresh_cash_table()
        self._refresh_logs()
        self._refresh_diagnostics()
        self._refresh_failure_checks()

    def _on_tab_changed(self, index):
        self.refresh_all()

    # -------------------------------------------------------- Cards tab --
    def _build_cards_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        search_row = QHBoxLayout()
        self.card_search = QLineEdit()
        self.card_search.setPlaceholderText("Search by holder, card or account number...")
        self.card_search.textChanged.connect(self._refresh_cards)
        search_row.addWidget(self.card_search)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.clicked.connect(self._refresh_cards)
        search_row.addWidget(refresh_btn)
        l.addLayout(search_row)

        self.cards_table = QTableWidget(0, 7)
        self.cards_table.setHorizontalHeaderLabels(
            ["Card Number", "Holder", "Account No.", "Balance", "Status",
             "Failed Attempts", "Created"])
        self.cards_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cards_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cards_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cards_table.setAlternatingRowColors(True)
        l.addWidget(self.cards_table, 1)

        actions = QHBoxLayout()
        for label, status in [("Activate", "ACTIVE"), ("Deactivate", "INACTIVE"),
                               ("Lock", "LOCKED"), ("Unlock", "ACTIVE"), ("Retain", "RETAINED")]:
            btn = QPushButton(label)
            if status == "RETAINED":
                btn.setProperty("variant", "danger")
            btn.clicked.connect(lambda checked=False, s=status: self._set_card_status(s))
            actions.addWidget(btn)
        adjust_btn = QPushButton("Adjust Balance")
        adjust_btn.clicked.connect(self._adjust_balance)
        actions.addWidget(adjust_btn)
        l.addLayout(actions)
        return w

    def _selected_card_id(self):
        items = self.cards_table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _refresh_cards(self):
        cards = db.list_cards()
        search = self.card_search.text().strip().lower() if hasattr(self, "card_search") else ""
        rows = [c for c in cards if not search or search in c["cardholder_name"].lower()
                or search in c["card_number"] or search in c["account_number"]]
        self.cards_table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            values = [security.mask_card_number(c["card_number"]), c["cardholder_name"],
                      c["account_number"], f"₹{c['balance']:.2f}", c["status"],
                      str(c["failed_attempts"]), c["created_at"][:19].replace("T", " ")]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, c["card_id"])
                self.cards_table.setItem(r, col, item)

    def _set_card_status(self, status: str):
        card_id = self._selected_card_id()
        if card_id is None:
            QMessageBox.information(self, "No Selection", "Select a card first.")
            return
        db.set_card_status(card_id, status)
        c = db.get_card(card_id)
        db.log_security_event(f"CARD_{status}", c["card_number"], "", "Changed via Admin Dashboard")
        self._refresh_cards()

    def _adjust_balance(self):
        card_id = self._selected_card_id()
        if card_id is None:
            QMessageBox.information(self, "No Selection", "Select a card first.")
            return
        c = db.get_card(card_id)
        value, ok = QInputDialog.getDouble(self, "Adjust Balance",
                                            f"New balance for {c['cardholder_name']}:",
                                            c["balance"], 0, 100_000_000, 2)
        if ok:
            with db.get_conn() as conn:
                db.update_balance(conn, c["account_id"], value)
                db.record_transaction(conn, c["account_id"], card_id, "", "ADMIN_ADJUSTMENT",
                                       0, value, "SUCCESS", remarks="Balance adjusted by admin")
            db.log_security_event("BALANCE_ADJUSTED", c["card_number"], "",
                                   f"Set to ₹{value:.2f} via Admin Dashboard")
            self._refresh_cards()

    # ---------------------------------------------------- ATM cash tab --
    def _build_cash_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("Select ATM:"))
        self.atm_combo = QComboBox()
        self.atm_combo.currentIndexChanged.connect(self._refresh_cash_table)
        row.addWidget(self.atm_combo)
        row.addStretch()
        self.atm_status_combo = QComboBox()
        self.atm_status_combo.addItems(["ONLINE", "OFFLINE", "MAINTENANCE"])
        row.addWidget(QLabel("ATM Status:"))
        row.addWidget(self.atm_status_combo)
        set_status_btn = QPushButton("Apply Status")
        set_status_btn.clicked.connect(self._apply_atm_status)
        row.addWidget(set_status_btn)
        l.addLayout(row)

        self.cash_table = QTableWidget(0, 3)
        self.cash_table.setHorizontalHeaderLabels(["Denomination (₹)", "Notes Available", "Subtotal (₹)"])
        self.cash_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cash_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l.addWidget(self.cash_table)

        self.total_label = QLabel("Total Cash: ₹0.00")
        self.total_label.setProperty("role", "heading")
        l.addWidget(self.total_label)

        refill_box = QGroupBox("Refill ATM (add notes)")
        refill_layout = QGridLayout(refill_box)
        self.refill_spins: dict[int, QSpinBox] = {}
        for i, denom in enumerate(db.DEFAULT_DENOMINATIONS):
            refill_layout.addWidget(QLabel(f"₹{denom} notes to add:"), i, 0)
            spin = QSpinBox()
            spin.setRange(0, 5000)
            refill_layout.addWidget(spin, i, 1)
            self.refill_spins[denom] = spin
        refill_btn = QPushButton("Refill Selected ATM")
        refill_btn.setProperty("variant", "primary")
        refill_btn.clicked.connect(self._refill_atm)
        refill_layout.addWidget(refill_btn, len(db.DEFAULT_DENOMINATIONS), 0, 1, 2)
        l.addWidget(refill_box)
        return w

    def _refresh_atm_combo(self):
        current = self.atm_combo.currentData()
        self.atm_combo.blockSignals(True)
        self.atm_combo.clear()
        for atm in db.list_atms():
            self.atm_combo.addItem(f"{atm['code']} — {atm['name']}", atm["code"])
        if current:
            idx = self.atm_combo.findData(current)
            if idx >= 0:
                self.atm_combo.setCurrentIndex(idx)
        self.atm_combo.blockSignals(False)

    def _apply_atm_status(self):
        code = self.atm_combo.currentData()
        if not code:
            return
        db.set_atm_status(code, self.atm_status_combo.currentText())
        QMessageBox.information(self, "Status Updated", f"{code} status set to "
                                                          f"{self.atm_status_combo.currentText()}.")

    def _refresh_cash_table(self):
        code = self.atm_combo.currentData()
        if not code:
            self.cash_table.setRowCount(0)
            self.total_label.setText("Total Cash: ₹0.00")
            return
        rows = db.get_atm_cash(code)
        self.cash_table.setRowCount(len(rows))
        total = 0
        for r, row in enumerate(rows):
            subtotal = row["denomination"] * row["count"]
            total += subtotal
            self.cash_table.setItem(r, 0, QTableWidgetItem(f"₹{row['denomination']}"))
            self.cash_table.setItem(r, 1, QTableWidgetItem(str(row["count"])))
            self.cash_table.setItem(r, 2, QTableWidgetItem(f"₹{subtotal:,.2f}"))
        self.total_label.setText(f"Total Cash: ₹{total:,.2f}")
        atm = db.get_atm(code)
        if atm:
            self.atm_status_combo.setCurrentText(atm["status"])

    def _refill_atm(self):
        code = self.atm_combo.currentData()
        if not code:
            return
        amounts = {denom: spin.value() for denom, spin in self.refill_spins.items() if spin.value() > 0}
        if not amounts:
            QMessageBox.information(self, "Nothing to Refill", "Enter note counts to add.")
            return
        db.refill_atm(code, amounts)
        db.log_security_event("ATM_REFILLED", "", code, str(amounts))
        for spin in self.refill_spins.values():
            spin.setValue(0)
        self._refresh_cash_table()
        QMessageBox.information(self, "Refilled", f"{code} refilled successfully.")

    # --------------------------------------------------------- Logs tab --
    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        refresh_btn = QPushButton("⟳ Refresh Logs")
        refresh_btn.clicked.connect(self._refresh_logs)
        l.addWidget(refresh_btn)
        self.logs_table = QTableWidget(0, 5)
        self.logs_table.setHorizontalHeaderLabels(["Timestamp", "Event", "Card Number", "ATM", "Details"])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.logs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.logs_table.setAlternatingRowColors(True)
        l.addWidget(self.logs_table)
        return w

    def _refresh_logs(self):
        logs = db.list_security_logs(300)
        self.logs_table.setRowCount(len(logs))
        for r, row in enumerate(logs):
            values = [row["timestamp"], row["event_type"],
                      security.mask_card_number(row["card_number"]) if row["card_number"] else "",
                      row["atm_code"] or "", row["details"] or ""]
            for col, val in enumerate(values):
                self.logs_table.setItem(r, col, QTableWidgetItem(val))

    # --------------------------------------------------- Diagnostics tab --
    def _build_diagnostics_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.diag_labels = {}
        grid = QGridLayout()
        checks = ["Database Connectivity", "Total ATMs Online", "Total Cards Issued",
                  "Total Transactions", "Total Cash Across ATMs", "Active Failure Flags"]
        for i, label in enumerate(checks):
            grid.addWidget(QLabel(label + ":"), i, 0)
            val = QLabel("—")
            val.setStyleSheet("font-weight:700; color:#00c896;")
            self.diag_labels[label] = val
            grid.addWidget(val, i, 1)
        l.addLayout(grid)
        run_btn = QPushButton("Run Diagnostics")
        run_btn.setProperty("variant", "primary")
        run_btn.clicked.connect(self._refresh_diagnostics)
        l.addWidget(run_btn)
        l.addStretch()
        return w

    def _refresh_diagnostics(self):
        ok = db.is_db_reachable()
        atms = db.list_atms()
        online = sum(1 for a in atms if a["status"] == "ONLINE")
        cards = db.list_cards()
        txns = db.list_transactions()
        total_cash = sum(db.atm_total_cash(a["code"]) for a in atms)
        active_flags = [k for k, v in db.get_failure_flags().items() if v]

        self.diag_labels["Database Connectivity"].setText("OK ✔" if ok else "FAILED ✖")
        self.diag_labels["Database Connectivity"].setStyleSheet(
            "font-weight:700; color:%s;" % ("#00c896" if ok else "#ff5470"))
        self.diag_labels["Total ATMs Online"].setText(f"{online} / {len(atms)}")
        self.diag_labels["Total Cards Issued"].setText(str(len(cards)))
        self.diag_labels["Total Transactions"].setText(str(len(txns)))
        self.diag_labels["Total Cash Across ATMs"].setText(f"₹{total_cash:,.2f}")
        self.diag_labels["Active Failure Flags"].setText(
            ", ".join(FAILURE_LABELS[f] for f in active_flags) if active_flags else "None")

    # ------------------------------------------------ Failure sim tab --
    def _build_failure_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        note = QLabel("Toggle failure conditions to test how the ATM Simulator responds. "
                       "All effects apply immediately across every running ATM session.")
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        l.addWidget(note)

        grid = QGridLayout()
        self.failure_checks: dict[str, QCheckBox] = {}
        for i, (key, label) in enumerate(FAILURE_LABELS.items()):
            cb = QCheckBox(label)
            cb.stateChanged.connect(lambda state, k=key: self._toggle_failure(k, state))
            self.failure_checks[key] = cb
            grid.addWidget(cb, i // 2, i % 2)
        l.addLayout(grid)

        reset_btn = QPushButton("Reset All Failure Flags")
        reset_btn.setProperty("variant", "danger")
        reset_btn.clicked.connect(self._reset_failures)
        l.addWidget(reset_btn)
        l.addStretch()
        return w

    def _toggle_failure(self, key, state):
        db.set_failure_flag(key, bool(state))
        db.log_security_event("FAILURE_FLAG_TOGGLED", "", "", f"{key}={bool(state)}")

    def _reset_failures(self):
        db.reset_failure_flags()
        self._refresh_failure_checks()

    def _refresh_failure_checks(self):
        current = db.get_failure_flags()
        for key, cb in self.failure_checks.items():
            cb.blockSignals(True)
            cb.setChecked(current.get(key, False))
            cb.blockSignals(False)
