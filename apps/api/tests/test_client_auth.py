from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import HTTPException

from app import client_auth


def test_local_auth_preserves_the_local_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_auth.get_settings(), "auth_mode", "local")
    assert client_auth.current_user_id(None) == UUID("00000000-0000-4000-8000-000000000001")


def test_anonymous_token_is_signed_and_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = client_auth.get_settings()
    monkeypatch.setattr(settings, "auth_mode", "anonymous")
    monkeypatch.setattr(settings, "anonymous_token_secret", "test-secret-with-more-than-thirty-two-characters")
    monkeypatch.setattr(client_auth, "ensure_user", lambda *_args, **_kwargs: None)
    token, expires_at = client_auth.issue_client_token()
    user_id = client_auth.current_user_id(f"Bearer {token}")
    assert isinstance(user_id, UUID)
    assert expires_at is not None

    with pytest.raises(HTTPException) as error:
        client_auth.current_user_id(f"Bearer {token[:-1]}x")
    assert error.value.status_code == 401
