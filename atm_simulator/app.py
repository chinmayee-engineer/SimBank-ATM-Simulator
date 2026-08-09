from __future__ import annotations

import os
import datetime

from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QStackedWidget, QMessageBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QSpinBox, QDoubleSpinBox,
    QDateEdit, QFileDialog, QGroupBox, QFormLayout, QScrollArea, QSizePolicy
)

from shared import db, security, i18n
from shared.i18n import t, LANGUAGES, localizer
from shared.theme import DARK_QSS
from shared.documents import (format_currency, generate_receipt_pdf, print_receipt_dialog,
                               txn_receipt_lines, export_transactions_excel)
from atm_simulator.session import Session, ATMError, insert_card, authenticate_pin, flags as get_flags
from atm_simulator import session as biz
from atm_simulator.keypad import NumericKeypad
from atm_simulator.admin import AdminDashboard

ADMIN_PASSWORD = "admin123"


def money(v) -> str:
    return format_currency(v)


class ClickableFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)


class MainMenuButton(QPushButton):
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(f"{icon}\n{text}", parent)
        self.setMinimumHeight(90)
        self.setMinimumWidth(180)
        f = QFont("Segoe UI", 11)
        f.setBold(True)
        self.setFont(f)


class ATMWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimBank ATM Simulator — SIMULATION / TEST ONLY")
        self.resize(1200, 780)
        self.setStyleSheet(DARK_QSS)

        self.session = Session()
        self.pin_flow = None          # "LOGIN" | "CHANGE_OLD" | "CHANGE_NEW" | "CHANGE_CONFIRM"
        self._temp_new_pin = None
        self._last_receipt_lines = None
        self._last_receipt_title = "TRANSACTION RECEIPT"
        self._session_timer = QTimer(self)
        self._session_timer.setSingleShot(True)
        self._session_timer.timeout.connect(self._on_session_timeout)

        self._build_shell()
        self._build_pages()
        self.goto_start()

    # ------------------------------------------------------------ shell --
    def _build_shell(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background-color:#0f1830; border-bottom:1px solid #26344d;")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 6, 18, 6)
        brand = QLabel("🏧 SimBank ATM")
        brand.setStyleSheet("font-size:17px; font-weight:800; color:#00c896;")
        hl.addWidget(brand)
        self.atm_label = QLabel("")
        self.atm_label.setStyleSheet("color:#8ba0bd;")
        hl.addWidget(self.atm_label)
        hl.addStretch()
        badge = QLabel("SIMULATION / TEST ONLY")
        badge.setStyleSheet("color:#ffb547; font-weight:700;")
        hl.addWidget(badge)
        hl.addSpacing(20)
        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet("color:#8ba0bd;")
        hl.addWidget(self.clock_label)
        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(1000)
        self._tick_clock()
        root.addWidget(header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.pages: dict[str, QWidget] = {}

    def _tick_clock(self):
        self.clock_label.setText(datetime.datetime.now().strftime("%d %b %Y  %H:%M:%S"))

    def add_page(self, name: str, widget: QWidget):
        self.pages[name] = widget
        self.stack.addWidget(widget)

    def goto(self, name: str):
        self.stack.setCurrentWidget(self.pages[name])
        if name not in ("start", "admin_login", "admin_dashboard"):
            self._session_timer.start(120_000)  # 2 minute idle timeout during a card session
        else:
            self._session_timer.stop()

    def _on_session_timeout(self):
        if self.session.authenticated:
            db.log_security_event("SESSION_TIMEOUT", self.session.card_row["card_number"],
                                   self.session.atm_code, "Idle timeout")
            QMessageBox.warning(self, t("error"), t("timeout_error"))
            self.end_session()

    def _build_pages(self):
        self.add_page("start", self._build_start_page())
        self.add_page("card_select", self._build_card_select_page())
        self.add_page("pin", self._build_pin_page())
        self.add_page("menu", self._build_menu_page())
        self.add_page("balance", self._build_balance_page())
        self.add_page("withdraw", self._build_withdraw_page())
        self.add_page("deposit", self._build_deposit_page())
        self.add_page("mini_statement", self._build_mini_statement_page())
        self.add_page("full_statement", self._build_full_statement_page())
        self.add_page("transfer", self._build_transfer_page())
        self.add_page("cheque", self._build_cheque_page())
        self.add_page("receipt", self._build_receipt_page())
        self.add_page("admin_login", self._build_admin_login_page())
        self.admin_dashboard = AdminDashboard(self)
        self.add_page("admin_dashboard", self.admin_dashboard)

    # ---------------------------------------------------------- helpers --
    def error_box(self, code: str, extra: str = ""):
        if code in i18n._STRINGS:
            msg = t(code)
            if extra:
                msg += f"\n{extra}"
        else:
            msg = extra or code
        QMessageBox.critical(self, t("error"), msg)

    def info_box(self, title_key: str, message: str):
        QMessageBox.information(self, t(title_key), message)

    def current_atm_name(self) -> str:
        atm = db.get_atm(self.session.atm_code)
        return atm["name"] if atm else self.session.atm_code

    def end_session(self):
        self.session.card_row = None
        self.session.authenticated = False
        self.pin_flow = None
        self.goto_start()

    # ============================================================ START =
    def _build_start_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(560)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 40, 40, 40)
        cl.setSpacing(16)

        title = QLabel("🏧 SimBank")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:34px; font-weight:800; color:#00c896;")
        cl.addWidget(title)

        self.welcome_label = QLabel(t("welcome"))
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setProperty("role", "title")
        cl.addWidget(self.welcome_label)

        sim = QLabel(t("simulation_notice"))
        sim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sim.setStyleSheet("color:#ffb547; font-weight:600;")
        cl.addWidget(sim)

        form = QFormLayout()
        self.lang_label = QLabel(t("select_language"))
        self.lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        form.addRow(self.lang_label, self.lang_combo)

        self.atm_select_label = QLabel(t("select_atm"))
        self.atm_combo_start = QComboBox()
        self._reload_atm_combo()
        form.addRow(self.atm_select_label, self.atm_combo_start)
        cl.addLayout(form)

        self.insert_card_btn = QPushButton(t("insert_card"))
        self.insert_card_btn.setProperty("variant", "primary")
        self.insert_card_btn.clicked.connect(self._go_card_select)
        cl.addWidget(self.insert_card_btn)

        admin_btn = QPushButton("🔐 Admin Access")
        admin_btn.setProperty("variant", "ghost")
        admin_btn.clicked.connect(lambda: self.goto("admin_login"))
        cl.addWidget(admin_btn)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _reload_atm_combo(self):
        self.atm_combo_start.clear()
        for atm in db.list_atms():
            label = f"{atm['code']} — {atm['name']} ({atm['status']})"
            self.atm_combo_start.addItem(label, atm["code"])

    def _on_language_changed(self):
        code = self.lang_combo.currentData()
        if code:
            localizer.set_language(code)
            self.session.language = code
            self.retranslate()

    def goto_start(self):
        self._reload_atm_combo()
        self.session.card_row = None
        self.session.authenticated = False
        self.pin_flow = None
        self.goto("start")

    def retranslate(self):
        self.welcome_label.setText(t("welcome"))
        self.lang_label.setText(t("select_language"))
        self.atm_select_label.setText(t("select_atm"))
        self.insert_card_btn.setText(t("insert_card"))
        self.card_select_heading.setText(t("insert_card"))
        self.pin_heading.setText(t("enter_pin"))
        self.pin_cancel_btn_ref.setText(t("cancel"))
        self._retranslate_menu()
        self._retranslate_misc()

    # ======================================================= CARD SELECT =
    def _build_card_select_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(560)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        self.card_select_heading = QLabel(t("insert_card"))
        self.card_select_heading.setProperty("role", "title")
        cl.addWidget(self.card_select_heading)

        note = QLabel("This simulator has no physical card reader — choose a test card "
                       "generated in the Card Generator app, or type its number.")
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        cl.addWidget(note)

        self.card_combo = QComboBox()
        cl.addWidget(self.card_combo)

        self.card_number_edit = QLineEdit()
        self.card_number_edit.setPlaceholderText("...or manually enter 16-digit card number")
        cl.addWidget(self.card_number_edit)

        btn_row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.goto_start)
        btn_row.addWidget(back_btn)
        continue_btn = QPushButton("Insert Card →")
        continue_btn.setProperty("variant", "primary")
        continue_btn.clicked.connect(self._do_insert_card)
        btn_row.addWidget(continue_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _go_card_select(self):
        self.session.atm_code = self.atm_combo_start.currentData() or "ATM-001"
        self.atm_label.setText(f"— {self.current_atm_name()} ({self.session.atm_code})")
        atm = db.get_atm(self.session.atm_code)
        if atm and atm["status"] != "ONLINE":
            self.error_box("network_error", f"{self.session.atm_code} is currently {atm['status']}.")
            return
        self.card_combo.clear()
        for c in db.list_cards():
            if c["status"] in ("ACTIVE", "INACTIVE", "LOCKED"):
                self.card_combo.addItem(
                    f"{security.mask_card_number(c['card_number'])} — {c['cardholder_name']} "
                    f"[{c['status']}]", c["card_number"])
        self.card_number_edit.clear()
        self.goto("card_select")

    def _do_insert_card(self):
        card_number = self.card_number_edit.text().strip() or self.card_combo.currentData()
        if not card_number:
            self.error_box("invalid_card_error")
            return
        try:
            card = insert_card(card_number)
        except ATMError as e:
            if e.code == "card_locked_msg":
                QMessageBox.critical(self, t("error"), e.message)
            else:
                self.error_box(e.code, e.message)
            return
        self.session.card_row = card
        self.pin_flow = "LOGIN"
        self._go_pin_screen()

    # ============================================================== PIN =
    def _build_pin_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(420)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(30, 30, 30, 30)
        cl.setSpacing(14)

        self.pin_heading = QLabel(t("enter_pin"))
        self.pin_heading.setProperty("role", "title")
        self.pin_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.pin_heading)

        self.pin_attempts_label = QLabel("")
        self.pin_attempts_label.setStyleSheet("color:#ffb547;")
        self.pin_attempts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.pin_attempts_label)

        self.pin_display = QLineEdit()
        self.pin_display.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_display.setReadOnly(True)
        f = QFont("Consolas", 22)
        self.pin_display.setFont(f)
        cl.addWidget(self.pin_display)

        self.pin_keypad = NumericKeypad(self.pin_display, max_length=4)
        self.pin_keypad.submitted.connect(self._on_pin_submitted)
        self.pin_keypad.cancelled.connect(self._on_pin_cancelled)
        self.pin_cancel_btn_ref = self.pin_keypad.cancel_btn
        cl.addWidget(self.pin_keypad)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _go_pin_screen(self):
        headings = {
            "LOGIN": t("enter_pin"),
            "CHANGE_OLD": t("old_pin"),
            "CHANGE_NEW": t("new_pin"),
            "CHANGE_CONFIRM": t("confirm_new_pin"),
        }
        self.pin_heading.setText(headings.get(self.pin_flow, t("enter_pin")))
        self.pin_display.clear()
        card = self.session.card_row
        if self.pin_flow == "LOGIN" and card is not None:
            remaining = max(0, 3 - card["failed_attempts"])
            self.pin_attempts_label.setText(f"{remaining} {t('attempts_remaining')}")
        else:
            self.pin_attempts_label.setText("")
        self.goto("pin")

    def _on_pin_cancelled(self):
        if self.pin_flow == "LOGIN":
            self.goto_start()
        else:
            self.pin_flow = None
            self.goto("menu")

    def _on_pin_submitted(self, value: str):
        if not (value.isdigit() and len(value) == 4):
            QMessageBox.warning(self, t("error"), "PIN must be exactly 4 digits.")
            return

        if self.pin_flow == "LOGIN":
            self._handle_login_pin(value)
        elif self.pin_flow == "CHANGE_OLD":
            self._old_pin_value = value
            self.pin_flow = "CHANGE_NEW"
            self._go_pin_screen()
        elif self.pin_flow == "CHANGE_NEW":
            self._temp_new_pin = value
            self.pin_flow = "CHANGE_CONFIRM"
            self._go_pin_screen()
        elif self.pin_flow == "CHANGE_CONFIRM":
            self._finish_change_pin(value)

    def _handle_login_pin(self, pin_value: str):
        card = self.session.card_row
        try:
            ok, attempts = authenticate_pin(card, pin_value)
        except Exception:
            self.error_box("database_error")
            return
        if ok:
            self.session.card_row = db.get_card(card["card_id"])
            self.session.authenticated = True
            self.pin_flow = None
            self.goto("menu")
            self._refresh_menu_header()
        else:
            refreshed = db.get_card(card["card_id"])
            self.session.card_row = refreshed
            if refreshed["status"] == "RETAINED":
                self.error_box("card_locked")
                self.end_session()
                return
            remaining = max(0, 3 - attempts)
            QMessageBox.warning(self, t("incorrect_pin"),
                                 f"{t('incorrect_pin')}. {remaining} {t('attempts_remaining')}")
            self.pin_display.clear()
            self.pin_attempts_label.setText(f"{remaining} {t('attempts_remaining')}")

    def _finish_change_pin(self, confirm_value: str):
        if confirm_value != self._temp_new_pin:
            QMessageBox.warning(self, t("error"), t("pin_mismatch"))
            self.pin_flow = "CHANGE_NEW"
            self._go_pin_screen()
            return
        try:
            biz.perform_pin_change(self.session.card_row, self._old_pin_value, self._temp_new_pin)
        except ATMError as e:
            if e.code == "incorrect_pin_remaining":
                QMessageBox.warning(self, t("incorrect_pin"),
                                     f"{t('incorrect_pin')}. {e.message} {t('attempts_remaining')}")
                self.pin_flow = "CHANGE_OLD"
                self._go_pin_screen()
                return
            elif e.code == "card_retained_error":
                self.error_box("card_retained_error")
                self.end_session()
                return
            else:
                self.error_box(e.code, e.message)
                self.pin_flow = None
                self.goto("menu")
                return
        self.pin_flow = None
        self.info_box("success", t("pin_changed_success"))
        self.session.card_row = db.get_card(self.session.card_row["card_id"])
        self.goto("menu")

    # ============================================================= MENU =
    def _build_menu_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(30, 20, 30, 20)

        header = QHBoxLayout()
        self.menu_welcome_label = QLabel("")
        self.menu_welcome_label.setProperty("role", "title")
        header.addWidget(self.menu_welcome_label)
        header.addStretch()
        self.menu_balance_chip = QLabel("")
        self.menu_balance_chip.setStyleSheet(
            "background:#122a22; color:#00c896; padding:8px 14px; border-radius:10px; font-weight:700;")
        header.addWidget(self.menu_balance_chip)
        outer.addLayout(header)

        self.menu_heading = QLabel(t("main_menu"))
        self.menu_heading.setProperty("role", "heading")
        outer.addWidget(self.menu_heading)

        grid = QGridLayout()
        grid.setSpacing(16)
        self.menu_buttons = {}
        entries = [
            ("balance_inquiry", "💰", lambda: self._go_balance()),
            ("withdraw_cash", "💵", lambda: self._go_withdraw()),
            ("deposit_cash", "🏦", lambda: self._go_deposit()),
            ("mini_statement", "🧾", lambda: self._go_mini_statement()),
            ("full_statement", "📄", lambda: self._go_full_statement()),
            ("change_pin", "🔑", self._go_change_pin),
            ("transfer_funds", "🔁", lambda: self._go_transfer()),
            ("cheque_request", "📘", lambda: self._go_cheque()),
            ("exit", "🚪", self._do_exit),
        ]
        for i, (key, icon, handler) in enumerate(entries):
            btn = MainMenuButton(icon, t(key))
            btn.clicked.connect(handler)
            self.menu_buttons[key] = btn
            grid.addWidget(btn, i // 3, i % 3)
        outer.addLayout(grid)
        outer.addStretch()
        return w

    def _retranslate_menu(self):
        self.menu_heading.setText(t("main_menu"))
        for key, btn in self.menu_buttons.items():
            icon = btn.text().split("\n")[0]
            btn.setText(f"{icon}\n{t(key)}")
        self._refresh_menu_header()

    def _refresh_menu_header(self):
        if self.session.card_row:
            self.menu_welcome_label.setText(f"{t('welcome_customer')}, {self.session.card_row['cardholder_name']}")
            self.menu_balance_chip.setText(f"{t('available_balance')}: {money(self.session.card_row['balance'])}")

    def _guarded(self, fn):
        """Wrap a screen navigation callback with global failure/authorization checks."""
        if not self.session.authenticated or not self.session.card_row:
            self.goto_start()
            return
        try:
            fn()
        except ATMError as e:
            self.error_box(e.code, e.message if e.code not in i18n._STRINGS else "")
            if e.code == "card_retained_error":
                self.end_session()

    def _refresh_card_row(self):
        if self.session.card_row:
            self.session.card_row = db.get_card(self.session.card_row["card_id"])
            self._refresh_menu_header()

    def _do_exit(self):
        db.log_security_event("SESSION_END", self.session.card_row["card_number"],
                               self.session.atm_code, "Customer ended session")
        QMessageBox.information(self, t("thank_you"), f"{t('take_your_card')}\n\n{t('thank_you')}")
        self.end_session()

    # ========================================================== BALANCE =
    def _build_balance_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(480)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)
        self.balance_heading = QLabel(t("balance_inquiry"))
        self.balance_heading.setProperty("role", "title")
        cl.addWidget(self.balance_heading)
        self.balance_value_label = QLabel("")
        self.balance_value_label.setStyleSheet("font-size:30px; font-weight:800; color:#00c896;")
        cl.addWidget(self.balance_value_label)
        self.balance_account_label = QLabel("")
        self.balance_account_label.setProperty("role", "muted")
        cl.addWidget(self.balance_account_label)

        btn_row = QHBoxLayout()
        self.balance_print_btn = QPushButton(t("print_receipt"))
        self.balance_print_btn.clicked.connect(lambda: self._print_last_receipt())
        btn_row.addWidget(self.balance_print_btn)
        self.balance_pdf_btn = QPushButton(t("save_pdf"))
        self.balance_pdf_btn.clicked.connect(lambda: self._save_last_receipt_pdf())
        btn_row.addWidget(self.balance_pdf_btn)
        cl.addLayout(btn_row)

        self.balance_back_btn = QPushButton(t("back"))
        self.balance_back_btn.clicked.connect(lambda: self.goto("menu"))
        cl.addWidget(self.balance_back_btn)
        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _go_balance(self):
        self._guarded(self._do_balance)

    def _do_balance(self):
        result = biz.perform_balance_inquiry(self.session.atm_code, self.session.card_row)
        self._refresh_card_row()
        self.balance_value_label.setText(money(result["balance"]))
        self.balance_account_label.setText(f"Account: {self.session.card_row['account_number']}")
        txn = db.get_transaction(result["txn_id"])
        self._set_last_receipt(txn, title="BALANCE INQUIRY RECEIPT")
        self.goto("balance")

    # ========================================================= WITHDRAW =
    def _build_withdraw_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(520)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        self.withdraw_heading = QLabel(t("withdraw_cash"))
        self.withdraw_heading.setProperty("role", "title")
        cl.addWidget(self.withdraw_heading)

        self.withdraw_balance_label = QLabel("")
        self.withdraw_balance_label.setProperty("role", "muted")
        cl.addWidget(self.withdraw_balance_label)

        quick_row = QGridLayout()
        self.quick_amount_buttons = []
        for i, amt in enumerate([500, 1000, 2000, 5000, 10000, 20000]):
            btn = QPushButton(money(amt))
            btn.clicked.connect(lambda checked=False, a=amt: self._set_withdraw_amount(a))
            quick_row.addWidget(btn, i // 3, i % 3)
            self.quick_amount_buttons.append(btn)
        cl.addLayout(quick_row)

        self.withdraw_amount_label = QLabel(t("enter_amount"))
        cl.addWidget(self.withdraw_amount_label)
        self.withdraw_amount_edit = QLineEdit()
        self.withdraw_amount_edit.setPlaceholderText("Custom amount (multiples of 100)")
        cl.addWidget(self.withdraw_amount_edit)

        btn_row = QHBoxLayout()
        self.withdraw_cancel_btn = QPushButton(t("cancel"))
        self.withdraw_cancel_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(self.withdraw_cancel_btn)
        self.withdraw_confirm_btn = QPushButton(t("confirm"))
        self.withdraw_confirm_btn.setProperty("variant", "primary")
        self.withdraw_confirm_btn.clicked.connect(self._confirm_withdraw)
        btn_row.addWidget(self.withdraw_confirm_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _set_withdraw_amount(self, amt):
        self.withdraw_amount_edit.setText(str(amt))

    def _go_withdraw(self):
        def do():
            self.withdraw_amount_edit.clear()
            self.withdraw_balance_label.setText(
                f"{t('available_balance')}: {money(self.session.card_row['balance'])}")
            self.goto("withdraw")
        self._guarded(do)

    def _confirm_withdraw(self):
        text = self.withdraw_amount_edit.text().strip()
        if not text.isdigit() or int(text) <= 0:
            QMessageBox.warning(self, t("error"), t("enter_amount"))
            return
        amount = int(text)
        try:
            result = biz.perform_withdrawal(self.session.atm_code, self.session.card_row, amount)
        except ATMError as e:
            self.error_box(e.code, e.message)
            if e.code == "card_retained_error":
                self.end_session()
            return
        self._refresh_card_row()
        txn = db.get_transaction(result["txn_id"])
        plan_str = ", ".join(f"{c}×₹{d}" for d, c in sorted(result["plan"].items(), reverse=True))
        self._set_last_receipt(txn, title="WITHDRAWAL RECEIPT", extra={"Notes Dispensed": plan_str})
        msg = f"{t('transaction_successful')}\n\n{t('take_your_cash')}\nDispensed: {plan_str}"
        if result.get("low_cash"):
            msg += f"\n\n⚠ {t('low_cash_warning')}"
        QMessageBox.information(self, t("transaction_successful"), msg)
        self.goto("receipt")

    # ========================================================== DEPOSIT =
    def _build_deposit_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(520)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        self.deposit_heading = QLabel(t("deposit_cash"))
        self.deposit_heading.setProperty("role", "title")
        cl.addWidget(self.deposit_heading)

        note = QLabel("Simulate inserting cash by entering how many notes of each "
                       "denomination you are depositing.")
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        cl.addWidget(note)

        form = QFormLayout()
        self.deposit_spins: dict[int, QSpinBox] = {}
        for denom in db.DEFAULT_DENOMINATIONS:
            spin = QSpinBox()
            spin.setRange(0, 500)
            spin.valueChanged.connect(self._update_deposit_total)
            self.deposit_spins[denom] = spin
            form.addRow(f"₹{denom} notes:", spin)
        cl.addLayout(form)

        self.deposit_total_label = QLabel(f"{t('enter_amount')}: ₹0.00")
        self.deposit_total_label.setStyleSheet("font-weight:700; color:#00c896;")
        cl.addWidget(self.deposit_total_label)

        btn_row = QHBoxLayout()
        self.deposit_cancel_btn = QPushButton(t("cancel"))
        self.deposit_cancel_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(self.deposit_cancel_btn)
        self.deposit_confirm_btn = QPushButton(t("confirm_deposit"))
        self.deposit_confirm_btn.setProperty("variant", "primary")
        self.deposit_confirm_btn.clicked.connect(self._confirm_deposit)
        btn_row.addWidget(self.deposit_confirm_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _update_deposit_total(self):
        total = sum(denom * spin.value() for denom, spin in self.deposit_spins.items())
        self.deposit_total_label.setText(f"{t('enter_amount')}: {money(total)}")

    def _go_deposit(self):
        def do():
            for spin in self.deposit_spins.values():
                spin.setValue(0)
            self._update_deposit_total()
            self.goto("deposit")
        self._guarded(do)

    def _confirm_deposit(self):
        counts = {denom: spin.value() for denom, spin in self.deposit_spins.items() if spin.value() > 0}
        if not counts:
            QMessageBox.warning(self, t("error"), t("enter_amount"))
            return
        try:
            result = biz.perform_deposit(self.session.atm_code, self.session.card_row, counts)
        except ATMError as e:
            self.error_box(e.code, e.message)
            return
        self._refresh_card_row()
        txn = db.get_transaction(result["txn_id"])
        self._set_last_receipt(txn, title="DEPOSIT RECEIPT")
        QMessageBox.information(self, t("deposit_success"),
                                 f"{t('deposit_success')}\n{money(result['amount'])} credited.")
        self.goto("receipt")

    # ==================================================== MINI STATEMENT =
    def _build_mini_statement_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(30, 20, 30, 20)
        self.mini_heading = QLabel(t("mini_statement"))
        self.mini_heading.setProperty("role", "title")
        outer.addWidget(self.mini_heading)

        self.mini_table = QTableWidget(0, 5)
        self.mini_table.setHorizontalHeaderLabels(["Txn ID", "Date/Time", "Type", "Amount", "Balance"])
        self.mini_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mini_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mini_table.setAlternatingRowColors(True)
        outer.addWidget(self.mini_table, 1)

        btn_row = QHBoxLayout()
        self.mini_pdf_btn = QPushButton(t("save_pdf"))
        self.mini_pdf_btn.clicked.connect(self._save_mini_statement_pdf)
        btn_row.addWidget(self.mini_pdf_btn)
        self.mini_print_btn = QPushButton(t("print_receipt"))
        self.mini_print_btn.clicked.connect(self._print_mini_statement)
        btn_row.addWidget(self.mini_print_btn)
        btn_row.addStretch()
        self.mini_back_btn = QPushButton(t("back"))
        self.mini_back_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(self.mini_back_btn)
        outer.addLayout(btn_row)
        return w

    def _go_mini_statement(self):
        def do():
            rows = db.list_transactions(account_id=self.session.card_row["account_id"], limit=10)
            self._populate_txn_table(self.mini_table, rows)
            self._mini_rows = rows
            self.goto("mini_statement")
        self._guarded(do)

    def _populate_txn_table(self, table: QTableWidget, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["txn_id"], row["timestamp"][:19].replace("T", " "), row["txn_type"],
                      money(row["amount"]), money(row["balance_after"]) if row["balance_after"] is not None else ""]
            for col, val in enumerate(values):
                table.setItem(r, col, QTableWidgetItem(val))

    def _save_mini_statement_pdf(self):
        if not getattr(self, "_mini_rows", None):
            return
        lines = [(r["txn_id"], f"{r['txn_type']} {money(r['amount'])}") for r in self._mini_rows]
        path = os.path.join(db.RECEIPTS_DIR, f"mini_statement_{self.session.card_row['account_number']}.pdf")
        generate_receipt_pdf(path, self.current_atm_name(), self.session.atm_code, lines,
                              title="MINI STATEMENT")
        QMessageBox.information(self, t("save_pdf"), f"Saved to:\n{path}")

    def _print_mini_statement(self):
        if get_flags().get("receipt_printer"):
            self.error_box("printer_error")
            return
        if not getattr(self, "_mini_rows", None):
            return
        lines = [(r["txn_id"], f"{r['txn_type']} {money(r['amount'])}") for r in self._mini_rows]
        print_receipt_dialog(self, self.current_atm_name(), self.session.atm_code, lines,
                              title="MINI STATEMENT")

    # ==================================================== FULL STATEMENT =
    def _build_full_statement_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(30, 20, 30, 20)
        self.full_heading = QLabel(t("full_statement"))
        self.full_heading.setProperty("role", "title")
        outer.addWidget(self.full_heading)

        filt = QHBoxLayout()
        self.full_search = QLineEdit()
        self.full_search.setPlaceholderText(t("search_placeholder") if "search_placeholder" in i18n._STRINGS
                                             else "Search transaction ID / remarks...")
        filt.addWidget(self.full_search, 1)
        self.full_type_combo = QComboBox()
        self.full_type_combo.addItems(["All Types", "WITHDRAWAL", "DEPOSIT", "TRANSFER_OUT",
                                        "TRANSFER_IN", "BALANCE_INQUIRY", "ADMIN_ADJUSTMENT"])
        filt.addWidget(self.full_type_combo)
        self.full_status_combo = QComboBox()
        self.full_status_combo.addItems(["All Statuses", "SUCCESS", "FAILED"])
        filt.addWidget(self.full_status_combo)
        self.full_date_from = QDateEdit(calendarPopup=True)
        self.full_date_from.setDate(QDate.currentDate().addMonths(-3))
        filt.addWidget(QLabel(t("from_date") if "from_date" in i18n._STRINGS else "From:"))
        filt.addWidget(self.full_date_from)
        self.full_date_to = QDateEdit(calendarPopup=True)
        self.full_date_to.setDate(QDate.currentDate())
        filt.addWidget(QLabel(t("to_date") if "to_date" in i18n._STRINGS else "To:"))
        filt.addWidget(self.full_date_to)
        apply_btn = QPushButton(t("apply") if "apply" in i18n._STRINGS else "Apply")
        apply_btn.setProperty("variant", "primary")
        apply_btn.clicked.connect(self._apply_full_statement_filter)
        filt.addWidget(apply_btn)
        outer.addLayout(filt)

        self.full_table = QTableWidget(0, 7)
        self.full_table.setHorizontalHeaderLabels(
            ["Txn ID", "Date/Time", "Type", "Amount", "Balance", "Status", "Remarks"])
        self.full_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.full_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.full_table.setAlternatingRowColors(True)
        outer.addWidget(self.full_table, 1)

        btn_row = QHBoxLayout()
        export_btn = QPushButton(t("export_excel") if "export_excel" in i18n._STRINGS else "Export to Excel")
        export_btn.clicked.connect(self._export_full_statement)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        back_btn = QPushButton(t("back"))
        back_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(back_btn)
        outer.addLayout(btn_row)
        return w

    def _go_full_statement(self):
        def do():
            self._apply_full_statement_filter()
            self.goto("full_statement")
        self._guarded(do)

    def _apply_full_statement_filter(self):
        txn_type = self.full_type_combo.currentText()
        status = self.full_status_combo.currentText()
        rows = db.list_transactions(
            account_id=self.session.card_row["account_id"],
            txn_type=None if txn_type == "All Types" else txn_type,
            status=None if status == "All Statuses" else status,
            date_from=self.full_date_from.date().toString("yyyy-MM-dd"),
            date_to=self.full_date_to.date().toString("yyyy-MM-dd"),
            search=self.full_search.text().strip() or None,
        )
        self._full_rows = rows
        self.full_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [row["txn_id"], row["timestamp"][:19].replace("T", " "), row["txn_type"],
                      money(row["amount"]),
                      money(row["balance_after"]) if row["balance_after"] is not None else "",
                      row["status"], row["remarks"] or ""]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 5:
                    item.setForeground(QColor("#00c896" if row["status"] == "SUCCESS" else "#ff5470"))
                self.full_table.setItem(r, col, item)

    def _export_full_statement(self):
        rows = getattr(self, "_full_rows", [])
        if not rows:
            QMessageBox.information(self, t("export_excel") if "export_excel" in i18n._STRINGS else "Export",
                                     "No transactions to export.")
            return
        default_path = os.path.join(db.EXPORTS_DIR,
                                     f"statement_{self.session.card_row['account_number']}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Export Transactions", default_path, "Excel Files (*.xlsx)")
        if not path:
            return
        export_transactions_excel(path, rows)
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    # =========================================================== TRANSFER =
    def _build_transfer_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(480)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        self.transfer_heading = QLabel(t("transfer_funds"))
        self.transfer_heading.setProperty("role", "title")
        cl.addWidget(self.transfer_heading)

        form = QFormLayout()
        self.transfer_account_label = QLabel(t("transfer_to_account"))
        self.transfer_account_edit = QLineEdit()
        self.transfer_account_edit.setPlaceholderText("SIMxxxxxxxxxxx")
        form.addRow(self.transfer_account_label, self.transfer_account_edit)
        self.transfer_amount_label = QLabel(t("transfer_amount"))
        self.transfer_amount_edit = QLineEdit()
        form.addRow(self.transfer_amount_label, self.transfer_amount_edit)
        cl.addLayout(form)

        btn_row = QHBoxLayout()
        self.transfer_cancel_btn = QPushButton(t("cancel"))
        self.transfer_cancel_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(self.transfer_cancel_btn)
        self.transfer_confirm_btn = QPushButton(t("confirm"))
        self.transfer_confirm_btn.setProperty("variant", "primary")
        self.transfer_confirm_btn.clicked.connect(self._confirm_transfer)
        btn_row.addWidget(self.transfer_confirm_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _go_transfer(self):
        def do():
            self.transfer_account_edit.clear()
            self.transfer_amount_edit.clear()
            self.goto("transfer")
        self._guarded(do)

    def _confirm_transfer(self):
        acct = self.transfer_account_edit.text().strip()
        amt_text = self.transfer_amount_edit.text().strip()
        if not acct or not amt_text.replace(".", "", 1).isdigit():
            QMessageBox.warning(self, t("error"), "Enter a valid account number and amount.")
            return
        try:
            result = biz.perform_transfer(self.session.atm_code, self.session.card_row,
                                           acct, float(amt_text))
        except ATMError as e:
            self.error_box(e.code, e.message)
            return
        self._refresh_card_row()
        txn = db.get_transaction(result["txn_id"])
        self._set_last_receipt(txn, title="FUND TRANSFER RECEIPT")
        QMessageBox.information(self, t("transfer_success"),
                                 f"{t('transfer_success')}\nTo: {result['recipient']}")
        self.goto("receipt")

    # ============================================================= CHEQUE =
    def _build_cheque_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(440)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        self.cheque_heading = QLabel(t("cheque_request"))
        self.cheque_heading.setProperty("role", "title")
        cl.addWidget(self.cheque_heading)

        form = QFormLayout()
        self.cheque_leaves_label = QLabel(t("cheque_leaves") if "cheque_leaves" in i18n._STRINGS
                                           else "Number of Leaves")
        self.cheque_leaves_spin = QSpinBox()
        self.cheque_leaves_spin.setRange(10, 100)
        self.cheque_leaves_spin.setSingleStep(10)
        self.cheque_leaves_spin.setValue(25)
        form.addRow(self.cheque_leaves_label, self.cheque_leaves_spin)
        cl.addLayout(form)

        btn_row = QHBoxLayout()
        self.cheque_cancel_btn = QPushButton(t("cancel"))
        self.cheque_cancel_btn.clicked.connect(lambda: self.goto("menu"))
        btn_row.addWidget(self.cheque_cancel_btn)
        self.cheque_confirm_btn = QPushButton(t("confirm"))
        self.cheque_confirm_btn.setProperty("variant", "primary")
        self.cheque_confirm_btn.clicked.connect(self._confirm_cheque)
        btn_row.addWidget(self.cheque_confirm_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _go_cheque(self):
        self._guarded(lambda: self.goto("cheque"))

    def _confirm_cheque(self):
        try:
            biz.perform_cheque_request(self.session.atm_code, self.session.card_row,
                                        self.cheque_leaves_spin.value())
        except ATMError as e:
            self.error_box(e.code, e.message)
            return
        QMessageBox.information(self, t("cheque_requested") if "cheque_requested" in i18n._STRINGS
                                 else "Requested",
                                 f"Cheque book request for {self.cheque_leaves_spin.value()} leaves "
                                 f"submitted (SIMULATION).")
        self.goto("menu")

    # ============================================================= RECEIPT =
    def _build_receipt_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(420)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(30, 30, 30, 30)
        cl.setSpacing(10)

        self.receipt_heading = QLabel(t("receipt"))
        self.receipt_heading.setProperty("role", "title")
        cl.addWidget(self.receipt_heading)

        self.receipt_text = QLabel("")
        self.receipt_text.setStyleSheet("font-family:Consolas; font-size:12px;")
        self.receipt_text.setWordWrap(True)
        cl.addWidget(self.receipt_text)

        btn_row = QHBoxLayout()
        self.receipt_print_btn = QPushButton(t("print_receipt"))
        self.receipt_print_btn.clicked.connect(self._print_last_receipt)
        btn_row.addWidget(self.receipt_print_btn)
        self.receipt_pdf_btn = QPushButton(t("save_pdf"))
        self.receipt_pdf_btn.clicked.connect(self._save_last_receipt_pdf)
        btn_row.addWidget(self.receipt_pdf_btn)
        cl.addLayout(btn_row)

        self.receipt_done_btn = QPushButton(t("back"))
        self.receipt_done_btn.setProperty("variant", "primary")
        self.receipt_done_btn.clicked.connect(lambda: self.goto("menu"))
        cl.addWidget(self.receipt_done_btn)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _set_last_receipt(self, txn_row, title="TRANSACTION RECEIPT", extra=None):
        self._last_receipt_lines = txn_receipt_lines(txn_row, extra)
        self._last_receipt_title = title
        display = "\n".join(f"{k:<16}{v}" for k, v in self._last_receipt_lines)
        self.receipt_text.setText(display)

    def _print_last_receipt(self):
        if get_flags().get("receipt_printer"):
            self.error_box("printer_error")
            return
        if not self._last_receipt_lines:
            return
        print_receipt_dialog(self, self.current_atm_name(), self.session.atm_code,
                              self._last_receipt_lines, title=self._last_receipt_title)

    def _save_last_receipt_pdf(self):
        if not self._last_receipt_lines:
            return
        acct = self.session.card_row["account_number"] if self.session.card_row else "receipt"
        default_path = os.path.join(db.RECEIPTS_DIR, f"receipt_{acct}_{int(datetime.datetime.now().timestamp())}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, t("save_pdf"), default_path, "PDF Files (*.pdf)")
        if not path:
            return
        generate_receipt_pdf(path, self.current_atm_name(), self.session.atm_code,
                              self._last_receipt_lines, title=self._last_receipt_title)
        QMessageBox.information(self, t("save_pdf"), f"Saved to:\n{path}")

    # ========================================================= CHANGE PIN =
    def _go_change_pin(self):
        def do():
            self.pin_flow = "CHANGE_OLD"
            self._go_pin_screen()
        self._guarded(do)

    # ============================================================== ADMIN =
    def _build_admin_login_page(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(400)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(36, 36, 36, 36)
        cl.setSpacing(14)

        heading = QLabel(t("admin_login"))
        heading.setProperty("role", "title")
        cl.addWidget(heading)
        note = QLabel("Default password: admin123 (change in shared/config for deployment)")
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        cl.addWidget(note)

        self.admin_password_edit = QLineEdit()
        self.admin_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password_edit.setPlaceholderText(t("admin_password"))
        self.admin_password_edit.returnPressed.connect(self._do_admin_login)
        cl.addWidget(self.admin_password_edit)

        btn_row = QHBoxLayout()
        back_btn = QPushButton(t("back"))
        back_btn.clicked.connect(self.goto_start)
        btn_row.addWidget(back_btn)
        login_btn = QPushButton(t("admin_login"))
        login_btn.setProperty("variant", "primary")
        login_btn.clicked.connect(self._do_admin_login)
        btn_row.addWidget(login_btn)
        cl.addLayout(btn_row)

        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    def _do_admin_login(self):
        if self.admin_password_edit.text() == ADMIN_PASSWORD:
            self.admin_password_edit.clear()
            db.log_security_event("ADMIN_LOGIN", "", "", "Admin dashboard accessed")
            self.admin_dashboard.refresh_all()
            self.goto("admin_dashboard")
        else:
            QMessageBox.warning(self, t("error"), t("invalid_admin_password"))

    def _retranslate_misc(self):
        # Re-apply translated captions across the remaining customer screens.
        self.balance_heading.setText(t("balance_inquiry"))
        self.balance_print_btn.setText(t("print_receipt"))
        self.balance_pdf_btn.setText(t("save_pdf"))
        self.balance_back_btn.setText(t("back"))
        self.withdraw_heading.setText(t("withdraw_cash"))
        self.withdraw_amount_label.setText(t("enter_amount"))
        self.withdraw_cancel_btn.setText(t("cancel"))
        self.withdraw_confirm_btn.setText(t("confirm"))
        self.deposit_heading.setText(t("deposit_cash"))
        self.deposit_cancel_btn.setText(t("cancel"))
        self.mini_heading.setText(t("mini_statement"))
        self.mini_pdf_btn.setText(t("save_pdf"))
        self.mini_print_btn.setText(t("print_receipt"))
        self.mini_back_btn.setText(t("back"))
        self.full_heading.setText(t("full_statement"))
        self.transfer_heading.setText(t("transfer_funds"))
        self.transfer_account_label.setText(t("transfer_to_account"))
        self.transfer_amount_label.setText(t("transfer_amount"))
        self.transfer_cancel_btn.setText(t("cancel"))
        self.transfer_confirm_btn.setText(t("confirm"))
        self.cheque_heading.setText(t("cheque_request"))
        self.cheque_cancel_btn.setText(t("cancel"))
        self.cheque_confirm_btn.setText(t("confirm"))
        self.receipt_heading.setText(t("receipt"))
        self.receipt_print_btn.setText(t("print_receipt"))
        self.receipt_pdf_btn.setText(t("save_pdf"))
        self.receipt_done_btn.setText(t("back"))
