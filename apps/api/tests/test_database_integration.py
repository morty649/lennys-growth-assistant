from __future__ import annotations

import os
from uuid import uuid4

import pytest


@pytest.mark.postgres_integration
def test_postgres_persists_messages_and_isolates_profile_sessions(monkeypatch) -> None:
    if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip("set RUN_POSTGRES_INTEGRATION=1 with a disposable DATABASE_URL")

    from app import database
    from app.config import get_settings

    database_url = os.environ.get("POSTGRES_INTEGRATION_URL")
    if not database_url:
        pytest.fail("POSTGRES_INTEGRATION_URL is required for the PostgreSQL integration test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    first_user = uuid4()
    second_user = uuid4()
    first_session_id = None
    second_session_id = None
    try:
        database.initialize_database()
        database.ensure_user(first_user, "Integration user one")
        database.ensure_user(second_user, "Integration user two")
        first_session = database.create_session(
            "First private session", "ollama", "qwen3:8b", first_user
        )
        second_session = database.create_session(
            "Second private session", "groq", "openai/gpt-oss-120b", second_user
        )
        first_session_id = first_session["id"]
        second_session_id = second_session["id"]

        database.add_message(first_session_id, "user", "private first-user question")
        database.add_message(first_session_id, "assistant", "private first-user answer")

        assert database.get_session(first_session_id, first_user) is not None
        assert database.get_session(first_session_id, second_user) is None
        assert [row["id"] for row in database.list_sessions(first_user)] == [first_session_id]
        assert [row["id"] for row in database.list_sessions(second_user)] == [second_session_id]
        assert [row["content"] for row in database.list_messages(first_session_id)] == [
            "private first-user question",
            "private first-user answer",
        ]
    finally:
        if first_session_id or second_session_id:
            with database.connection() as conn:
                conn.execute(
                    "DELETE FROM chat_sessions WHERE id = ANY(%s)",
                    ([value for value in (first_session_id, second_session_id) if value],),
                )
                conn.execute("DELETE FROM users WHERE id = ANY(%s)", ([first_user, second_user],))
        get_settings.cache_clear()
