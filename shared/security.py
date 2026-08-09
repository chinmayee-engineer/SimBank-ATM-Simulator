"""
Security helpers for the ATM Simulation System.
All cryptographic operations here are for SIMULATION purposes only and must
never be reused for real financial systems.
"""
import hashlib
import hmac
import os
import random
import secrets
import string
import uuid

PBKDF2_ITERATIONS = 200_000


def _pbkdf2(secret: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex()


def hash_pin(pin: str) -> tuple[str, str]:
    """Return (pin_hash_hex, salt_hex) using salted PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    digest = _pbkdf2(pin, salt)
    return digest, salt.hex()


def verify_pin(pin: str, pin_hash: str, salt_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = _pbkdf2(pin, salt)
    return hmac.compare_digest(candidate, pin_hash)


def luhn_checksum(number: str) -> int:
    digits = [int(d) for d in number]
    odd = digits[-1::-2]
    even = digits[-2::-2]
    total = sum(odd)
    for d in even:
        d2 = d * 2
        total += d2 - 9 if d2 > 9 else d2
    return total % 10


def luhn_check_digit(partial_number: str) -> str:
    check = luhn_checksum(partial_number + "0")
    return str((10 - check) % 10)


# Fictitious BIN ranges clearly reserved for this simulator (not real card networks)
SIM_BIN_PREFIXES = ["600719", "600720", "600721"]


def generate_card_number() -> str:
    prefix = random.choice(SIM_BIN_PREFIXES)
    middle = "".join(secrets.choice(string.digits) for _ in range(9))
    partial = prefix + middle
    return partial + luhn_check_digit(partial)


def generate_cvv() -> str:
    return f"{secrets.randbelow(1000):03d}"


def generate_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


def generate_account_number() -> str:
    return "SIM" + "".join(secrets.choice(string.digits) for _ in range(11))


def generate_txn_id() -> str:
    return "TXN" + uuid.uuid4().hex[:14].upper()


def generate_atm_code(seq: int) -> str:
    return f"ATM-{seq:03d}"


def mask_card_number(card_number: str) -> str:
    if len(card_number) < 4:
        return card_number
    return "•••• •••• •••• " + card_number[-4:]


def format_card_number(card_number: str) -> str:
    return " ".join(card_number[i:i + 4] for i in range(0, len(card_number), 4))
