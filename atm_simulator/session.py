"""
Session + transaction-processing controller for the ATM Simulator.
Keeps banking / failure-simulation logic separate from the Qt UI layer.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

from shared import db, security


class ATMError(Exception):
    """Raised for any simulated ATM failure. `code` maps to an i18n key."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message


@dataclass
class Session:
    atm_code: str = "ATM-001"
    language: str = "en"
    card_row: Optional[object] = None      # sqlite3.Row for the authenticated card
    authenticated: bool = False
    last_txn_id: Optional[str] = None
    admin_mode: bool = False


def flags() -> dict:
    return db.get_failure_flags()


def check_global_failures(exclude: Optional[set] = None):
    """Raise ATMError if a systemic failure flag (db/network/timeout) is active."""
    exclude = exclude or set()
    f = flags()
    if "database" not in exclude and f.get("database"):
        raise ATMError("database_error")
    if "network" not in exclude and f.get("network"):
        raise ATMError("network_error")
    if "transaction_timeout" not in exclude and f.get("transaction_timeout"):
        raise ATMError("timeout_error")


def insert_card(card_number: str) -> object:
    """Validates card insertion, respecting card_reader / invalid_card / card_retained flags."""
    f = flags()
    if f.get("card_reader"):
        db.log_security_event("CARD_READER_FAILURE", card_number, "", "Simulated failure")
        raise ATMError("card_reader_error")
    if f.get("database"):
        raise ATMError("database_error")

    if f.get("invalid_card"):
        db.log_security_event("INVALID_CARD", card_number, "", "Simulated invalid card")
        raise ATMError("invalid_card_error")

    card = db.get_card_by_number(card_number)
    if not card:
        db.log_security_event("INVALID_CARD", card_number, "", "Card not found in system")
        raise ATMError("invalid_card_error")

    if f.get("card_retained"):
        db.set_card_status(card["card_id"], "RETAINED")
        db.log_security_event("CARD_RETAINED", card_number, "", "Simulated retention on insert")
        raise ATMError("card_retained_error")

    if card["status"] == "RETAINED":
        raise ATMError("card_retained_error")
    if card["status"] == "LOCKED":
        raise ATMError("card_locked_msg", "Card is locked. Please contact your bank.")
    if card["status"] == "INACTIVE":
        raise ATMError("invalid_card_error", "Card is inactive.")

    return card


def authenticate_pin(card_row, pin_entered: str) -> tuple[bool, int]:
    """Returns (success, attempts_used). Locks & retains the card on the 3rd failure."""
    ok = security.verify_pin(pin_entered, card_row["pin_hash"], card_row["pin_salt"])
    if ok:
        db.reset_failed_attempts(card_row["card_id"])
        db.log_security_event("PIN_AUTH_SUCCESS", card_row["card_number"], "", "")
        return True, 0
    attempts = db.increment_failed_attempts(card_row["card_id"])
    db.log_security_event("PIN_AUTH_FAILED", card_row["card_number"], "",
                           f"Attempt {attempts}/3")
    if attempts >= 3:
        db.set_card_status(card_row["card_id"], "RETAINED")
        db.log_security_event("CARD_RETAINED", card_row["card_number"], "",
                               "3 failed PIN attempts")
    return False, attempts


def perform_withdrawal(atm_code: str, card_row, amount: float) -> dict:
    check_global_failures()
    f = flags()
    account_id = card_row["account_id"]
    account = db.get_account(account_id)

    with db.get_conn() as conn:
        usage = db.get_daily_usage(conn, account_id)
        if amount <= 0:
            raise ATMError("invalid_amount", "Enter a valid amount.")
        if amount > account["balance"]:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "WITHDRAWAL", amount, account["balance"], "FAILED",
                                   remarks="Insufficient funds")
            raise ATMError("insufficient_funds")
        if usage["withdrawal_used"] + amount > account["daily_withdrawal_limit"]:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "WITHDRAWAL", amount, account["balance"], "FAILED",
                                   remarks="Daily withdrawal limit exceeded")
            raise ATMError("daily_limit_exceeded")

        cash_total = db.atm_total_cash(atm_code, conn=conn)
        if f.get("out_of_cash") or cash_total <= 0:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "WITHDRAWAL", amount, account["balance"], "FAILED",
                                   remarks="ATM out of cash")
            raise ATMError("out_of_cash_error")

        plan = db.compute_dispense_plan(atm_code, int(amount), conn=conn)
        if plan is None:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "WITHDRAWAL", amount, account["balance"], "FAILED",
                                   remarks="Cannot dispense requested denominations")
            raise ATMError("insufficient_atm_cash")

        if f.get("cash_dispenser"):
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "WITHDRAWAL", amount, account["balance"], "FAILED",
                                   remarks="Simulated cash dispenser failure")
            db.log_security_event("CASH_DISPENSER_FAILURE", card_row["card_number"], atm_code, "",
                                   conn=conn)
            raise ATMError("cash_dispenser_error")

        new_balance = account["balance"] - amount
        db.update_balance(conn, account_id, new_balance)
        db.deduct_atm_cash(conn, atm_code, plan)
        db.add_withdrawal_usage(conn, account_id, amount)
        txn_id = db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                        "WITHDRAWAL", amount, new_balance, "SUCCESS",
                                        remarks="Cash withdrawal")

    remaining_cash = db.atm_total_cash(atm_code)
    low_cash = f.get("low_cash") or remaining_cash < 5000
    return {"txn_id": txn_id, "balance": new_balance, "plan": plan, "low_cash": low_cash}


def perform_deposit(atm_code: str, card_row, denom_counts: dict[int, int]) -> dict:
    check_global_failures()
    f = flags()
    amount = sum(denom * count for denom, count in denom_counts.items())
    if amount <= 0:
        raise ATMError("invalid_amount", "Enter a valid deposit amount.")
    account_id = card_row["account_id"]
    account = db.get_account(account_id)

    if f.get("cash_dispenser"):  # acts as the cash/bill acceptor module too
        with db.get_conn() as conn:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "DEPOSIT", amount, account["balance"], "FAILED",
                                   remarks="Simulated cash acceptor failure")
        raise ATMError("cash_dispenser_error")

    with db.get_conn() as conn:
        new_balance = account["balance"] + amount
        db.update_balance(conn, account_id, new_balance)
        db.refill_atm(atm_code, denom_counts, conn=conn)
        txn_id = db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                        "DEPOSIT", amount, new_balance, "SUCCESS",
                                        remarks="Cash deposit")
    return {"txn_id": txn_id, "balance": new_balance, "amount": amount}


def perform_transfer(atm_code: str, card_row, recipient_account_number: str, amount: float) -> dict:
    check_global_failures()
    account_id = card_row["account_id"]
    account = db.get_account(account_id)

    if amount <= 0:
        raise ATMError("invalid_amount")

    recipient = db.get_account_by_number(recipient_account_number.strip())
    if not recipient:
        raise ATMError("account_not_found")
    if recipient["account_id"] == account_id:
        raise ATMError("invalid_amount", "Cannot transfer to your own account.")

    with db.get_conn() as conn:
        usage = db.get_daily_usage(conn, account_id)
        if amount > account["balance"]:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "TRANSFER_OUT", amount, account["balance"], "FAILED",
                                   remarks="Insufficient funds",
                                   related_account=recipient["account_number"])
            raise ATMError("insufficient_funds")
        if usage["transfer_used"] + amount > account["daily_transfer_limit"]:
            db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                   "TRANSFER_OUT", amount, account["balance"], "FAILED",
                                   remarks="Daily transfer limit exceeded",
                                   related_account=recipient["account_number"])
            raise ATMError("daily_limit_exceeded")

        new_sender_balance = account["balance"] - amount
        new_recipient_balance = recipient["balance"] + amount
        db.update_balance(conn, account_id, new_sender_balance)
        db.update_balance(conn, recipient["account_id"], new_recipient_balance)
        db.add_transfer_usage(conn, account_id, amount)
        txn_id = db.record_transaction(conn, account_id, card_row["card_id"], atm_code,
                                        "TRANSFER_OUT", amount, new_sender_balance, "SUCCESS",
                                        remarks=f"Transfer to {recipient['account_number']}",
                                        related_account=recipient["account_number"])
        db.record_transaction(conn, recipient["account_id"], None, atm_code,
                               "TRANSFER_IN", amount, new_recipient_balance, "SUCCESS",
                               remarks=f"Transfer from {account['account_number']}",
                               related_account=account["account_number"])
    return {"txn_id": txn_id, "balance": new_sender_balance, "recipient": recipient["account_number"]}


def perform_balance_inquiry(atm_code: str, card_row) -> dict:
    check_global_failures()
    account = db.get_account(card_row["account_id"])
    with db.get_conn() as conn:
        txn_id = db.record_transaction(conn, account["account_id"], card_row["card_id"], atm_code,
                                        "BALANCE_INQUIRY", 0, account["balance"], "SUCCESS",
                                        remarks="Balance inquiry")
    return {"txn_id": txn_id, "balance": account["balance"]}


def perform_pin_change(card_row, old_pin: str, new_pin: str) -> None:
    check_global_failures()
    ok, attempts = authenticate_pin(card_row, old_pin)
    if not ok:
        remaining = max(0, 3 - attempts)
        if remaining == 0:
            raise ATMError("card_retained_error")
        raise ATMError("incorrect_pin_remaining", f"{remaining}")
    db.set_pin(card_row["card_id"], new_pin)
    db.log_security_event("PIN_CHANGED", card_row["card_number"], "", "Changed via ATM")


def perform_cheque_request(atm_code: str, card_row, leaves: int) -> int:
    check_global_failures()
    return db.request_cheque_book(card_row["account_id"], atm_code, leaves)
