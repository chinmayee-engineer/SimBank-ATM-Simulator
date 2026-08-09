"""
Shared SQLite data-access layer for the ATM Simulation System.

Both the Card Generator and the ATM Simulator import this module so they
always read/write the SAME local database file, guaranteeing cards created
in one app are usable in the other.

Everything in this system is FICTIONAL / SIMULATION ONLY.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from shared import security

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Allow both packaged .exe apps to point at one shared data folder even when
# built/installed into different directories (set ATM_SIM_DATA_DIR to override).
DATA_DIR = os.environ.get("ATM_SIM_DATA_DIR") or os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "atm_system.db")
RECEIPTS_DIR = os.path.join(DATA_DIR, "..", "receipts") if not os.environ.get("ATM_SIM_DATA_DIR") \
    else os.path.join(DATA_DIR, "receipts")
RECEIPTS_DIR = os.path.abspath(RECEIPTS_DIR)
EXPORTS_DIR = os.path.join(DATA_DIR, "..", "exports") if not os.environ.get("ATM_SIM_DATA_DIR") \
    else os.path.join(DATA_DIR, "exports")
EXPORTS_DIR = os.path.abspath(EXPORTS_DIR)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

_lock = threading.Lock()

FAILURE_FLAG_NAMES = [
    "card_reader",
    "cash_dispenser",
    "receipt_printer",
    "network",
    "low_cash",
    "out_of_cash",
    "database",
    "invalid_card",
    "card_retained",
    "transaction_timeout",
]

DEFAULT_DENOMINATIONS = [2000, 500, 200, 100, 50]


class SimulatedDatabaseUnavailable(Exception):
    """Raised when the admin 'database unavailable' failure flag is active."""


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


@contextmanager
def get_conn():
    with _lock:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    daily_withdrawal_limit REAL NOT NULL DEFAULT 25000,
    daily_transfer_limit REAL NOT NULL DEFAULT 50000,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_number TEXT UNIQUE NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(account_id),
    cardholder_name TEXT NOT NULL,
    expiry_month INTEGER NOT NULL,
    expiry_year INTEGER NOT NULL,
    cvv TEXT NOT NULL,
    pin_hash TEXT NOT NULL,
    pin_salt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    network TEXT NOT NULL DEFAULT 'SIMNET',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atms (
    atm_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ONLINE'
);

CREATE TABLE IF NOT EXISTS atm_cash (
    atm_id INTEGER NOT NULL REFERENCES atms(atm_id),
    denomination INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (atm_id, denomination)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id TEXT UNIQUE NOT NULL,
    account_id INTEGER NOT NULL,
    card_id INTEGER,
    atm_code TEXT,
    txn_type TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    balance_after REAL,
    related_account TEXT,
    status TEXT NOT NULL,
    remarks TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    card_number TEXT,
    atm_code TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS cheque_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    atm_code TEXT,
    leaves INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'REQUESTED'
);

CREATE TABLE IF NOT EXISTS daily_usage (
    account_id INTEGER NOT NULL,
    usage_date TEXT NOT NULL,
    withdrawal_used REAL NOT NULL DEFAULT 0,
    transfer_used REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (account_id, usage_date)
);

CREATE TABLE IF NOT EXISTS failure_flags (
    flag_name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        for flag in FAILURE_FLAG_NAMES:
            conn.execute(
                "INSERT OR IGNORE INTO failure_flags(flag_name, enabled) VALUES (?, 0)",
                (flag,),
            )
        cur = conn.execute("SELECT COUNT(*) c FROM atms")
        if cur.fetchone()["c"] == 0:
            seed_atms(conn)


def seed_atms(conn):
    atms = [
        ("ATM-001", "MG Road Branch ATM", "MG Road, Bengaluru"),
        ("ATM-002", "Koramangala Self-Service", "Koramangala, Bengaluru"),
        ("ATM-003", "Airport Terminal ATM", "Kempegowda Airport, Bengaluru"),
        ("ATM-004", "Whitefield Tech Park ATM", "Whitefield, Bengaluru"),
    ]
    for code, name, loc in atms:
        cur = conn.execute(
            "INSERT INTO atms(code, name, location, status) VALUES (?, ?, ?, 'ONLINE')",
            (code, name, loc),
        )
        atm_id = cur.lastrowid
        for denom in DEFAULT_DENOMINATIONS:
            count = 200 if denom <= 500 else 80
            conn.execute(
                "INSERT INTO atm_cash(atm_id, denomination, count) VALUES (?, ?, ?)",
                (atm_id, denom, count),
            )


# ---------------------------------------------------------------- Accounts --
def create_account(customer_name: str, opening_balance: float,
                    withdrawal_limit: float = 25000, transfer_limit: float = 50000) -> int:
    with get_conn() as conn:
        acc_no = security.generate_account_number()
        while conn.execute("SELECT 1 FROM accounts WHERE account_number=?", (acc_no,)).fetchone():
            acc_no = security.generate_account_number()
        cur = conn.execute(
            "INSERT INTO accounts(account_number, customer_name, balance, "
            "daily_withdrawal_limit, daily_transfer_limit, created_at) VALUES (?,?,?,?,?,?)",
            (acc_no, customer_name, opening_balance, withdrawal_limit, transfer_limit, now_iso()),
        )
        return cur.lastrowid


def get_account(account_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()


def get_account_by_number(account_number: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE account_number=?", (account_number,)
        ).fetchone()


def list_accounts() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM accounts ORDER BY account_id DESC").fetchall()


def update_balance(conn, account_id: int, new_balance: float):
    conn.execute("UPDATE accounts SET balance=? WHERE account_id=?", (new_balance, account_id))


# --------------------------------------------------------------------- Cards
def create_card(customer_name: str, opening_balance: float = 10000.0, pin: Optional[str] = None,
                 expiry_years: int = 4, withdrawal_limit: float = 25000,
                 transfer_limit: float = 50000) -> dict:
    with get_conn() as conn:
        acc_no = security.generate_account_number()
        while conn.execute("SELECT 1 FROM accounts WHERE account_number=?", (acc_no,)).fetchone():
            acc_no = security.generate_account_number()
        cur = conn.execute(
            "INSERT INTO accounts(account_number, customer_name, balance, "
            "daily_withdrawal_limit, daily_transfer_limit, created_at) VALUES (?,?,?,?,?,?)",
            (acc_no, customer_name, opening_balance, withdrawal_limit, transfer_limit, now_iso()),
        )
        account_id = cur.lastrowid

        card_number = security.generate_card_number()
        while conn.execute("SELECT 1 FROM cards WHERE card_number=?", (card_number,)).fetchone():
            card_number = security.generate_card_number()
        cvv = security.generate_cvv()
        pin_value = pin or security.generate_pin()
        pin_hash, salt = security.hash_pin(pin_value)
        exp = datetime.date.today()
        expiry_year = exp.year + expiry_years
        expiry_month = exp.month

        conn.execute(
            "INSERT INTO cards(card_number, account_id, cardholder_name, expiry_month, "
            "expiry_year, cvv, pin_hash, pin_salt, status, failed_attempts, network, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,0,?,?)",
            (card_number, account_id, customer_name, expiry_month, expiry_year, cvv,
             pin_hash, salt, "ACTIVE", "SIMNET", now_iso()),
        )
        return {
            "card_number": card_number,
            "account_number": acc_no,
            "cardholder_name": customer_name,
            "expiry_month": expiry_month,
            "expiry_year": expiry_year,
            "cvv": cvv,
            "pin": pin_value,
            "balance": opening_balance,
        }


def list_cards() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT c.*, a.account_number, a.balance FROM cards c "
            "JOIN accounts a ON a.account_id=c.account_id ORDER BY c.card_id DESC"
        ).fetchall()


def get_card_by_number(card_number: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT c.*, a.account_number, a.balance, a.daily_withdrawal_limit, "
            "a.daily_transfer_limit FROM cards c JOIN accounts a ON a.account_id=c.account_id "
            "WHERE c.card_number=?", (card_number,)
        ).fetchone()


def get_card(card_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT c.*, a.account_number, a.balance FROM cards c "
            "JOIN accounts a ON a.account_id=c.account_id WHERE c.card_id=?", (card_id,)
        ).fetchone()


def set_card_status(card_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE cards SET status=?, failed_attempts=0 WHERE card_id=?",
                     (status, card_id))


def set_pin(card_id: int, new_pin: str):
    pin_hash, salt = security.hash_pin(new_pin)
    with get_conn() as conn:
        conn.execute(
            "UPDATE cards SET pin_hash=?, pin_salt=?, failed_attempts=0 WHERE card_id=?",
            (pin_hash, salt, card_id),
        )


def increment_failed_attempts(card_id: int) -> int:
    with get_conn() as conn:
        conn.execute("UPDATE cards SET failed_attempts = failed_attempts + 1 WHERE card_id=?",
                     (card_id,))
        row = conn.execute("SELECT failed_attempts FROM cards WHERE card_id=?",
                            (card_id,)).fetchone()
        attempts = row["failed_attempts"]
        if attempts >= 3:
            conn.execute("UPDATE cards SET status='LOCKED' WHERE card_id=?", (card_id,))
        return attempts


def reset_failed_attempts(card_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE cards SET failed_attempts=0 WHERE card_id=?", (card_id,))


def delete_card(card_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM cards WHERE card_id=?", (card_id,))


# ------------------------------------------------------------------- ATMs --
def list_atms() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM atms ORDER BY code").fetchall()


def get_atm(code: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM atms WHERE code=?", (code,)).fetchone()


def _get_atm_cash_impl(conn, atm_code: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT ac.denomination, ac.count FROM atm_cash ac "
        "JOIN atms a ON a.atm_id=ac.atm_id WHERE a.code=? ORDER BY ac.denomination DESC",
        (atm_code,),
    ).fetchall()


def get_atm_cash(atm_code: str, conn=None) -> list[sqlite3.Row]:
    """Reads current note counts for an ATM. Pass `conn` when already inside a
    `with get_conn()` block to avoid opening a second (deadlocking) connection."""
    if conn is not None:
        return _get_atm_cash_impl(conn, atm_code)
    with get_conn() as c:
        return _get_atm_cash_impl(c, atm_code)


def atm_total_cash(atm_code: str, conn=None) -> float:
    rows = get_atm_cash(atm_code, conn=conn)
    return sum(r["denomination"] * r["count"] for r in rows)


def set_atm_denomination(atm_code: str, denomination: int, count: int):
    with get_conn() as conn:
        atm = conn.execute("SELECT atm_id FROM atms WHERE code=?", (atm_code,)).fetchone()
        if not atm:
            return
        conn.execute(
            "INSERT INTO atm_cash(atm_id, denomination, count) VALUES (?,?,?) "
            "ON CONFLICT(atm_id, denomination) DO UPDATE SET count=excluded.count",
            (atm["atm_id"], denomination, count),
        )


def _refill_atm_impl(conn, atm_code: str, amounts: dict[int, int]):
    atm = conn.execute("SELECT atm_id FROM atms WHERE code=?", (atm_code,)).fetchone()
    if not atm:
        return
    for denom, add_count in amounts.items():
        row = conn.execute(
            "SELECT count FROM atm_cash WHERE atm_id=? AND denomination=?",
            (atm["atm_id"], denom),
        ).fetchone()
        current = row["count"] if row else 0
        conn.execute(
            "INSERT INTO atm_cash(atm_id, denomination, count) VALUES (?,?,?) "
            "ON CONFLICT(atm_id, denomination) DO UPDATE SET count=excluded.count",
            (atm["atm_id"], denom, current + add_count),
        )


def refill_atm(atm_code: str, amounts: dict[int, int], conn=None):
    """Adds notes to an ATM's float. Pass `conn` when already inside a
    `with get_conn()` block to avoid opening a second (deadlocking) connection."""
    if conn is not None:
        _refill_atm_impl(conn, atm_code, amounts)
        return
    with get_conn() as c:
        _refill_atm_impl(c, atm_code, amounts)


def compute_dispense_plan(atm_code: str, amount: int, conn=None) -> Optional[dict[int, int]]:
    """Greedy denomination breakdown constrained by available cash. Returns None if impossible."""
    rows = get_atm_cash(atm_code, conn=conn)
    available = {r["denomination"]: r["count"] for r in rows}
    remaining = amount
    plan: dict[int, int] = {}
    for denom in sorted(available.keys(), reverse=True):
        if remaining <= 0:
            break
        max_notes = available[denom]
        needed = remaining // denom
        use = min(max_notes, needed)
        if use > 0:
            plan[denom] = use
            remaining -= use * denom
    if remaining != 0:
        return None
    return plan


def deduct_atm_cash(conn, atm_code: str, plan: dict[int, int]):
    atm = conn.execute("SELECT atm_id FROM atms WHERE code=?", (atm_code,)).fetchone()
    for denom, count in plan.items():
        conn.execute(
            "UPDATE atm_cash SET count = count - ? WHERE atm_id=? AND denomination=?",
            (count, atm["atm_id"], denom),
        )


def set_atm_status(atm_code: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE atms SET status=? WHERE code=?", (status, atm_code))


# ---------------------------------------------------------- Daily limits --
def get_daily_usage(conn, account_id: int) -> sqlite3.Row:
    today = datetime.date.today().isoformat()
    row = conn.execute(
        "SELECT * FROM daily_usage WHERE account_id=? AND usage_date=?", (account_id, today)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO daily_usage(account_id, usage_date, withdrawal_used, transfer_used) "
            "VALUES (?,?,0,0)", (account_id, today),
        )
        row = conn.execute(
            "SELECT * FROM daily_usage WHERE account_id=? AND usage_date=?", (account_id, today)
        ).fetchone()
    return row


def add_withdrawal_usage(conn, account_id: int, amount: float):
    today = datetime.date.today().isoformat()
    get_daily_usage(conn, account_id)
    conn.execute(
        "UPDATE daily_usage SET withdrawal_used = withdrawal_used + ? "
        "WHERE account_id=? AND usage_date=?", (amount, account_id, today),
    )


def add_transfer_usage(conn, account_id: int, amount: float):
    today = datetime.date.today().isoformat()
    get_daily_usage(conn, account_id)
    conn.execute(
        "UPDATE daily_usage SET transfer_used = transfer_used + ? "
        "WHERE account_id=? AND usage_date=?", (amount, account_id, today),
    )


# ------------------------------------------------------------ Transactions --
def record_transaction(conn, account_id: int, card_id: Optional[int], atm_code: Optional[str],
                        txn_type: str, amount: float, balance_after: Optional[float],
                        status: str, remarks: str = "", related_account: str = "") -> str:
    txn_id = security.generate_txn_id()
    conn.execute(
        "INSERT INTO transactions(txn_id, account_id, card_id, atm_code, txn_type, amount, "
        "balance_after, related_account, status, remarks, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (txn_id, account_id, card_id, atm_code, txn_type, amount, balance_after,
         related_account, status, remarks, now_iso()),
    )
    return txn_id


def list_transactions(account_id: Optional[int] = None, limit: Optional[int] = None,
                       txn_type: Optional[str] = None, status: Optional[str] = None,
                       date_from: Optional[str] = None, date_to: Optional[str] = None,
                       search: Optional[str] = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM transactions WHERE 1=1"
    params: list = []
    if account_id is not None:
        query += " AND account_id=?"
        params.append(account_id)
    if txn_type:
        query += " AND txn_type=?"
        params.append(txn_type)
    if status:
        query += " AND status=?"
        params.append(status)
    if date_from:
        query += " AND date(timestamp) >= date(?)"
        params.append(date_from)
    if date_to:
        query += " AND date(timestamp) <= date(?)"
        params.append(date_to)
    if search:
        query += " AND (txn_id LIKE ? OR remarks LIKE ? OR related_account LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    query += " ORDER BY id DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with get_conn() as conn:
        return conn.execute(query, params).fetchall()


def get_transaction(txn_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone()


# -------------------------------------------------------------- Cheque book --
def request_cheque_book(account_id: int, atm_code: str, leaves: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cheque_requests(account_id, atm_code, leaves, timestamp, status) "
            "VALUES (?,?,?,?, 'REQUESTED')",
            (account_id, atm_code, leaves, now_iso()),
        )
        return cur.lastrowid


def list_cheque_requests(account_id: Optional[int] = None) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if account_id:
            return conn.execute(
                "SELECT * FROM cheque_requests WHERE account_id=? ORDER BY id DESC", (account_id,)
            ).fetchall()
        return conn.execute("SELECT * FROM cheque_requests ORDER BY id DESC").fetchall()


# -------------------------------------------------------------- Security log --
def log_security_event(event_type: str, card_number: str = "", atm_code: str = "",
                        details: str = "", conn=None):
    """Pass `conn` when already inside a `with get_conn()` block to avoid opening
    a second (deadlocking) connection."""
    if conn is not None:
        conn.execute(
            "INSERT INTO security_logs(timestamp, event_type, card_number, atm_code, details) "
            "VALUES (?,?,?,?,?)",
            (now_iso(), event_type, card_number, atm_code, details),
        )
        return
    with get_conn() as c:
        c.execute(
            "INSERT INTO security_logs(timestamp, event_type, card_number, atm_code, details) "
            "VALUES (?,?,?,?,?)",
            (now_iso(), event_type, card_number, atm_code, details),
        )


def list_security_logs(limit: int = 500) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM security_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# ------------------------------------------------------------- Failure flags --
def get_failure_flags() -> dict[str, bool]:
    with get_conn() as conn:
        rows = conn.execute("SELECT flag_name, enabled FROM failure_flags").fetchall()
        return {r["flag_name"]: bool(r["enabled"]) for r in rows}


def set_failure_flag(name: str, enabled: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO failure_flags(flag_name, enabled) VALUES (?, ?) "
            "ON CONFLICT(flag_name) DO UPDATE SET enabled=excluded.enabled",
            (name, int(enabled)),
        )


def reset_failure_flags():
    with get_conn() as conn:
        for flag in FAILURE_FLAG_NAMES:
            conn.execute("UPDATE failure_flags SET enabled=0 WHERE flag_name=?", (flag,))


def is_db_reachable() -> bool:
    """Diagnostics check: verifies the DB file is reachable and queryable."""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


init_db()
