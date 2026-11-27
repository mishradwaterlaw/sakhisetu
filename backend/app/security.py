"""Field-level encryption, deterministic blind indexing, JWT tokens, and RBAC."""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.config import get_settings


def _get_fernet() -> Fernet:
    raw = get_settings().sakhi_encryption_key.encode("utf-8")
    # Derive a valid 32-byte urlsafe key if a dev placeholder was supplied
    try:
        return Fernet(raw)
    except Exception:
        digest = hashlib.sha256(raw).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_pii(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_pii(ciphertext: str | None) -> str | None:
    if ciphertext is None:
        return None
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return "[UNDECRYPTABLE]"


def blind_index(value: str) -> str:
    """Deterministic keyed SHA-256 hash for looking up encrypted phone numbers without table scans."""
    salt = get_settings().sakhi_blind_index_salt.encode("utf-8")
    normalized = "".join(ch for ch in value.strip() if ch.isdigit() or ch == "+")
    return hmac.new(salt, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts at rest and decrypts on read."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return encrypt_pii(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return decrypt_pii(value)


def create_access_token(
    subject_id: str,
    role: str,
    shg_id: str | None = None,
    party_id: str | None = None,
    expires_hours: int = 24,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject_id,
        "role": role,
        "shg_id": shg_id,
        "party_id": party_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
    }
    return jwt.encode(payload, get_settings().sakhi_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, get_settings().sakhi_jwt_secret, algorithms=["HS256"])
