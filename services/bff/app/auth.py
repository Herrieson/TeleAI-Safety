import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


class AuthError(ValueError):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, *, iterations: int) -> str:
    if not password:
        raise AuthError("password must not be empty")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, raw_iterations, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        iterations = int(raw_iterations)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return hmac.compare_digest(digest.hex(), expected)


def create_session_token(*, username: str, role: str, secret: str, ttl_seconds: int) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + ttl_seconds,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_token = _b64url_encode(payload_raw)
    signature = hmac.new(secret.encode("utf-8"), payload_token.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_token}.{_b64url_encode(signature)}"


def decode_session_token(token: str, *, secret: str) -> dict[str, Any]:
    try:
        payload_token, signature_token = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("invalid token format") from exc

    expected_signature = hmac.new(secret.encode("utf-8"), payload_token.encode("utf-8"), hashlib.sha256).digest()
    actual_signature = _b64url_decode(signature_token)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise AuthError("invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_token).decode("utf-8"))
    except Exception as exc:
        raise AuthError("invalid token payload") from exc

    subject = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    exp = payload.get("exp")
    if not subject or not role or not isinstance(exp, int):
        raise AuthError("invalid token claims")
    if exp <= int(time.time()):
        raise AuthError("token expired")
    return payload
