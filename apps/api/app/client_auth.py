from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Header, HTTPException

from app.config import get_settings
from app.database import LOCAL_USER_ID, ensure_user

_DEFAULT_SECRET = "local-dev-anonymous-token-change-me"
_rate_lock = threading.Lock()
_chat_windows: dict[UUID, deque[float]] = defaultdict(deque)


def validate_auth_configuration() -> None:
    settings = get_settings()
    if settings.auth_mode == "anonymous" and (
        not settings.anonymous_token_secret
        or settings.anonymous_token_secret == _DEFAULT_SECRET
        or len(settings.anonymous_token_secret) < 32
    ):
        raise RuntimeError("ANONYMOUS_TOKEN_SECRET must be a unique value of at least 32 characters")


def _sign(payload: str) -> str:
    digest = hmac.new(
        get_settings().anonymous_token_secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue_client_token() -> tuple[str, datetime | None]:
    settings = get_settings()
    if settings.auth_mode != "anonymous":
        ensure_user(LOCAL_USER_ID, "Local user")
        return "local", None
    user_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=settings.anonymous_token_ttl_days)
    nonce = secrets.token_urlsafe(12)
    payload = f"{user_id}.{int(expires_at.timestamp())}.{nonce}"
    ensure_user(user_id, "Anonymous visitor")
    return f"{payload}.{_sign(payload)}", expires_at


def current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    settings = get_settings()
    if settings.auth_mode != "anonymous":
        return LOCAL_USER_ID
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Anonymous client token required")
    token = authorization.removeprefix("Bearer ").strip()
    parts = token.split(".")
    if len(parts) != 4:
        raise HTTPException(status_code=401, detail="Invalid anonymous client token")
    user_text, expires_text, nonce, supplied_signature = parts
    payload = f"{user_text}.{expires_text}.{nonce}"
    if not hmac.compare_digest(_sign(payload), supplied_signature):
        raise HTTPException(status_code=401, detail="Invalid anonymous client token")
    try:
        user_id = UUID(user_text)
        expires_at = int(expires_text)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid anonymous client token") from exc
    if expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Anonymous client token expired")
    return user_id


def enforce_chat_rate_limit(user_id: UUID) -> None:
    settings = get_settings()
    if settings.auth_mode != "anonymous":
        return
    now = time.monotonic()
    cutoff = now - settings.chat_rate_window_seconds
    with _rate_lock:
        window = _chat_windows[user_id]
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= settings.chat_rate_limit:
            raise HTTPException(status_code=429, detail="Demo message limit reached; try again later")
        window.append(now)
