from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    resolved_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'complete',
    provider TEXT,
    model TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS messages_session_created_idx ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    guest TEXT NOT NULL,
    title TEXT NOT NULL,
    youtube_url TEXT NOT NULL DEFAULT '',
    source_path TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS episode_topics (
    episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    PRIMARY KEY (episode_id, topic)
);
CREATE INDEX IF NOT EXISTS episode_topics_topic_idx ON episode_topics(topic);

CREATE TABLE IF NOT EXISTS evidence_units (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    guest TEXT NOT NULL,
    title TEXT NOT NULL,
    speaker TEXT NOT NULL,
    question TEXT NOT NULL DEFAULT '',
    start_seconds INTEGER NOT NULL,
    end_seconds INTEGER NOT NULL,
    timestamp_label TEXT NOT NULL,
    youtube_url TEXT NOT NULL DEFAULT '',
    excerpt TEXT NOT NULL,
    search_document TEXT NOT NULL,
    topics TEXT[] NOT NULL DEFAULT '{}',
    search_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', search_document)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS evidence_units_tsv_idx ON evidence_units USING GIN(search_tsv);
CREATE INDEX IF NOT EXISTS evidence_units_episode_idx ON evidence_units(episode_id, start_seconds);
CREATE INDEX IF NOT EXISTS evidence_units_guest_idx ON evidence_units(guest);

CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    source_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    format TEXT NOT NULL,
    title TEXT NOT NULL,
    source_content TEXT NOT NULL,
    rendered_content TEXT NOT NULL,
    source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS source_evidence JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS validation JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS tool_runs (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms DOUBLE PRECISION NOT NULL,
    input_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    origin TEXT NOT NULL DEFAULT 'model',
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE tool_runs ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'model';
ALTER TABLE tool_runs ADD COLUMN IF NOT EXISTS error_code TEXT;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY,
    state TEXT NOT NULL,
    episodes_processed INTEGER NOT NULL DEFAULT 0,
    evidence_units INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
"""

LOCAL_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


@contextmanager
def connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    conn = psycopg.connect(get_settings().database_url, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def wait_for_database(attempts: int = 30, delay: float = 1.0) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with connection() as conn:
                conn.execute("SELECT 1")
            return
        except Exception as exc:  # pragma: no cover - timing dependent
            last_error = exc
            time.sleep(delay)
    raise RuntimeError(f"PostgreSQL did not become ready: {last_error}")


def initialize_database() -> None:
    wait_for_database()
    with connection() as conn:
        conn.execute(SCHEMA_SQL)
        if get_settings().vector_backend == "pgvector":
            conn.execute(CLOUD_VECTOR_SQL)
        ensure_user(LOCAL_USER_ID, "Local user", conn=conn)


CLOUD_VECTOR_SQL = """
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
ALTER TABLE evidence_units ADD COLUMN IF NOT EXISTS embedding extensions.vector(384);
CREATE INDEX IF NOT EXISTS evidence_units_embedding_hnsw_idx
ON evidence_units USING hnsw (embedding extensions.vector_cosine_ops)
WHERE embedding IS NOT NULL;
"""


def ensure_user(
    user_id: UUID,
    display_name: str,
    *,
    conn: psycopg.Connection[dict[str, Any]] | None = None,
) -> None:
    if conn is not None:
        conn.execute(
            "INSERT INTO users (id, display_name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (user_id, display_name),
        )
        return
    with connection() as active:
        ensure_user(user_id, display_name, conn=active)


def create_session(title: str, provider: str, model: str, user_id: UUID = LOCAL_USER_ID) -> dict[str, Any]:
    session_id = uuid4()
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO chat_sessions (id, user_id, title, provider, model)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, provider, model, created_at, updated_at
            """,
            (session_id, user_id, title, provider, model),
        ).fetchone()


def list_sessions(user_id: UUID = LOCAL_USER_ID) -> list[dict[str, Any]]:
    with connection() as conn:
        return list(
            conn.execute(
                """
                SELECT id, title, provider, model, created_at, updated_at
                FROM chat_sessions WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        )


def get_session(session_id: UUID, user_id: UUID = LOCAL_USER_ID) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT id, title, provider, model, resolved_context, created_at, updated_at
            FROM chat_sessions WHERE id = %s AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()


def update_session(
    session_id: UUID, updates: dict[str, Any], user_id: UUID = LOCAL_USER_ID
) -> dict[str, Any] | None:
    allowed = {
        key: value
        for key, value in updates.items()
        if key in {"title", "provider", "model", "resolved_context"} and value is not None
    }
    if not allowed:
        return get_session(session_id, user_id)
    assignments: list[str] = []
    values: list[Any] = []
    for key, value in allowed.items():
        assignments.append(f"{key} = %s::jsonb" if key == "resolved_context" else f"{key} = %s")
        values.append(json.dumps(value) if key == "resolved_context" else value)
    assignment_sql = ", ".join(assignments)
    values.extend((session_id, user_id))
    with connection() as conn:
        return conn.execute(
            f"""
            UPDATE chat_sessions SET {assignment_sql}, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, title, provider, model, resolved_context, created_at, updated_at
            """,
            values,
        ).fetchone()


def delete_session(session_id: UUID, user_id: UUID = LOCAL_USER_ID) -> bool:
    with connection() as conn:
        result = conn.execute(
            "DELETE FROM chat_sessions WHERE id = %s AND user_id = %s",
            (session_id, user_id),
        )
        return result.rowcount > 0


def add_message(
    session_id: UUID,
    role: str,
    content: str,
    *,
    status: str = "complete",
    provider: str | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message_id = uuid4()
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, status, provider, model, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, session_id, role, content, status, provider, model, metadata, created_at
            """,
            (
                message_id,
                session_id,
                role,
                content,
                status,
                provider,
                model,
                json.dumps(metadata or {}),
            ),
        ).fetchone()
        conn.execute("UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s", (session_id,))
        return row


def list_messages(session_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM (
              SELECT id, session_id, role, content, status, provider, model, metadata, created_at
              FROM messages WHERE session_id = %s
              ORDER BY created_at DESC LIMIT %s
            ) AS newest
            ORDER BY created_at ASC
            """,
            (session_id, limit),
        ).fetchall()
        return list(rows)


def get_message(session_id: UUID, message_id: UUID) -> dict[str, Any] | None:
    with connection() as conn:
        return conn.execute(
            """
            SELECT id, session_id, role, content, status, provider, model, metadata, created_at
            FROM messages WHERE session_id = %s AND id = %s
            """,
            (session_id, message_id),
        ).fetchone()


def add_tool_run(
    session_id: UUID,
    message_id: UUID | None,
    name: str,
    status: str,
    duration_ms: float,
    input_summary: dict[str, Any],
    *,
    origin: str = "model",
    error_code: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO tool_runs (
              id, session_id, message_id, tool_name, status, duration_ms, input_summary,
              origin, error_code
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                uuid4(), session_id, message_id, name, status, duration_ms,
                json.dumps(input_summary), origin, error_code,
            ),
        )


def create_artifact_record(
    session_id: UUID,
    source_message_id: UUID | None,
    format_name: str,
    title: str,
    source_content: str,
    rendered_content: str,
    source_evidence: list[dict[str, Any]],
    validation: dict[str, Any],
) -> dict[str, Any]:
    with connection() as conn:
        return conn.execute(
            """
            INSERT INTO artifacts (
              id, session_id, source_message_id, format, title, source_content,
              rendered_content, source_evidence, validation
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id, session_id, source_message_id, format, title, source_content,
                      rendered_content, source_evidence, validation, version, created_at
            """,
            (
                uuid4(),
                session_id,
                source_message_id,
                format_name,
                title,
                source_content,
                rendered_content,
                json.dumps(source_evidence),
                json.dumps(validation),
            ),
        ).fetchone()


def list_artifacts(session_id: UUID) -> list[dict[str, Any]]:
    with connection() as conn:
        return list(
            conn.execute(
                """
                SELECT id, session_id, source_message_id, format, title, source_content,
                       rendered_content, source_evidence, validation, version, created_at
                FROM artifacts WHERE session_id = %s ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
        )
