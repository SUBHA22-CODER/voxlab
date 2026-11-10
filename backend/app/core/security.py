import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, UTC

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


# --- Password hashing (PBKDF2-SHA256, no native deps) ---

_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# --- JWT ---

def create_access_token(subject: str) -> tuple[str, str]:
    """Create a JWT. Returns (token, jti); the jti enables revocation."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    jti = os.urandom(16).hex()
    payload = {"sub": subject, "exp": expire, "jti": jti}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256"), jti


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def decode_access_token_full(token: str) -> dict | None:
    """Return the full payload or None if invalid/expired."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# --- Credential encryption (Fernet) ---


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        # Derive a stable key from the secret key for local dev.
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.secret_key.encode()).digest()
        ).decode()
    return Fernet(key)


def encrypt_credentials(data: dict | None) -> str | None:
    """Encrypt agent auth configuration before storing it."""
    if not data:
        return None
    import json

    blob = json.dumps(data).encode()
    return _fernet().encrypt(blob).decode()


def decrypt_credentials(blob: str | None) -> dict | None:
    if not blob:
        return None
    import json

    try:
        return json.loads(_fernet().decrypt(blob.encode()))
    except (InvalidToken, ValueError):
        return None
