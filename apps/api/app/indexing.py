from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from typing import Any
from uuid import uuid4

import chromadb
import httpx

from app.config import get_settings
from app.corpus import (
    EVIDENCE_BUILD_VERSION,
    EvidenceUnit,
    build_evidence_units,
    load_topic_map,
    parse_episode,
)
from app.database import connection
from app.security import failure_code

WORD = re.compile(r"[a-z0-9][a-z0-9+#.-]+", re.IGNORECASE)
EMBEDDING_DIMENSIONS = 384
HASH_COLLECTION_NAME = "lenny_evidence_hash_v1"
OLLAMA_COLLECTION_NAME = "lenny_evidence_nomic_v1"


def hash_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Dependency-free feature-hashing embedding used for the guaranteed local baseline."""
    tokens = [token.casefold() for token in WORD.findall(text)]
    features = Counter(tokens)
    features.update(f"{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False))
    vector = [0.0] * dimensions
    for token, count in features.items():
        digest = __import__("hashlib").blake2b(token.encode(), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * (1.0 + math.log(count))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embedding_version() -> str:
    settings = get_settings()
    if settings.embedding_backend == "supabase":
        return "supabase:gte-small:v1"
    if settings.embedding_backend == "ollama":
        return f"ollama:{settings.ollama_embed_model}:v1"
    return "feature-hash-v1"


def embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    if settings.embedding_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase embedding configuration is incomplete")
        endpoint = (
            f"{settings.supabase_url.rstrip('/')}/functions/v1/"
            f"{settings.supabase_embed_function}"
        )
        with httpx.Client(timeout=120.0, trust_env=False) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                },
                json={"inputs": texts},
            )
            response.raise_for_status()
            embeddings = response.json().get("embeddings") or []
        if len(embeddings) != len(texts):
            raise RuntimeError("Supabase returned an unexpected embedding batch size")
        return embeddings
    if settings.embedding_backend != "ollama":
        return [hash_embedding(text) for text in texts]
    endpoint = f"{settings.ollama_base_url.removesuffix('/v1')}/api/embed"
    with httpx.Client(timeout=120.0, trust_env=False) as client:
        response = client.post(
            endpoint,
            json={"model": settings.ollama_embed_model, "input": texts, "truncate": True},
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings") or []
    if len(embeddings) != len(texts):
        raise RuntimeError("Ollama returned an unexpected embedding batch size")
    return embeddings


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def chroma_collection():
    settings = get_settings()
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    collection_name = (
        OLLAMA_COLLECTION_NAME if settings.embedding_backend == "ollama" else HASH_COLLECTION_NAME
    )
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedding": embedding_version()},
    )


class IngestionState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "state": "idle",
            "episodes_total": 0,
            "episodes_processed": 0,
            "evidence_units": 0,
            "error": None,
        }

    def update(self, **values: Any) -> None:
        with self._lock:
            self._data.update(values)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)


ingestion_state = IngestionState()


def _upsert_episode(episode, units: list[EvidenceUnit], topics: list[str]) -> bool:
    metadata = {
        **episode.metadata,
        "evidence_build_version": EVIDENCE_BUILD_VERSION,
        "embedding_version": embedding_version(),
    }
    with connection() as conn:
        existing = conn.execute(
            "SELECT content_hash, metadata FROM episodes WHERE id = %s", (episode.id,)
        ).fetchone()
        existing_metadata = (existing or {}).get("metadata") or {}
        if (
            existing
            and existing["content_hash"] == episode.content_hash
            and existing_metadata.get("evidence_build_version") == EVIDENCE_BUILD_VERSION
            and existing_metadata.get("embedding_version") == embedding_version()
        ):
            unit_count = conn.execute(
                "SELECT COUNT(*) AS count FROM evidence_units WHERE episode_id = %s", (episode.id,)
            ).fetchone()["count"]
            if unit_count:
                return False

        conn.execute(
            """
            INSERT INTO episodes (id, guest, title, youtube_url, source_path, duration_seconds, content_hash, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
              guest = EXCLUDED.guest,
              title = EXCLUDED.title,
              youtube_url = EXCLUDED.youtube_url,
              source_path = EXCLUDED.source_path,
              duration_seconds = EXCLUDED.duration_seconds,
              content_hash = EXCLUDED.content_hash,
              metadata = EXCLUDED.metadata,
              updated_at = NOW()
            """,
            (
                episode.id,
                episode.guest,
                episode.title,
                episode.youtube_url,
                episode.source_path,
                episode.duration_seconds,
                episode.content_hash,
                json.dumps(metadata, default=str),
            ),
        )
        conn.execute("DELETE FROM episode_topics WHERE episode_id = %s", (episode.id,))
        conn.execute("DELETE FROM evidence_units WHERE episode_id = %s", (episode.id,))
        with conn.cursor() as cursor:
            if topics:
                cursor.executemany(
                    "INSERT INTO episode_topics (episode_id, topic) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    [(episode.id, topic) for topic in topics],
                )
            if units:
                cursor.executemany(
                    """
                    INSERT INTO evidence_units (
                      id, episode_id, guest, title, speaker, question, start_seconds, end_seconds,
                      timestamp_label, youtube_url, excerpt, search_document, topics
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            unit.id,
                            unit.episode_id,
                            unit.guest,
                            unit.title,
                            unit.speaker,
                            unit.question,
                            unit.start_seconds,
                            unit.end_seconds,
                            unit.timestamp_label,
                            unit.youtube_url,
                            unit.excerpt,
                            unit.search_document,
                            unit.topics,
                        )
                        for unit in units
                    ],
                )
    return True


def _upsert_vectors(collection, episode_id: str, units: list[EvidenceUnit]) -> None:
    try:
        collection.delete(where={"episode_id": episode_id})
    except Exception:
        pass
    if not units:
        return
    _upsert_vector_units(collection, units)


def _upsert_vector_units(collection, units: list[EvidenceUnit]) -> None:
    if get_settings().vector_backend == "pgvector":
        for start in range(0, len(units), 16):
            batch = units[start : start + 16]
            embeddings = embed_texts([unit.search_document for unit in batch])
            with connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        "UPDATE evidence_units SET embedding = %s::extensions.vector WHERE id = %s",
                        [(_vector_literal(vector), unit.id) for vector, unit in zip(embeddings, batch, strict=True)],
                    )
        return
    for start in range(0, len(units), 192):
        batch = units[start : start + 192]
        collection.upsert(
            ids=[unit.id for unit in batch],
            embeddings=embed_texts([unit.search_document for unit in batch]),
            documents=[unit.search_document for unit in batch],
            metadatas=[
                {
                    "episode_id": unit.episode_id,
                    "guest": unit.guest,
                    "start_seconds": unit.start_seconds,
                    "end_seconds": unit.end_seconds,
                }
                for unit in batch
            ],
        )


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.9g}" for value in vector) + "]"


def vector_count() -> int:
    if get_settings().vector_backend == "pgvector":
        with connection() as conn:
            return int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM evidence_units WHERE embedding IS NOT NULL"
                ).fetchone()["count"]
            )
    return chroma_collection().count()


def episode_vector_ids(episode_id: str) -> list[str]:
    if get_settings().vector_backend == "pgvector":
        with connection() as conn:
            return [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM evidence_units WHERE episode_id = %s AND embedding IS NOT NULL",
                    (episode_id,),
                ).fetchall()
            ]
    return chroma_collection().get(where={"episode_id": episode_id}, include=[]).get("ids", [])


def delete_episode_vectors(episode_id: str) -> None:
    if get_settings().vector_backend == "pgvector":
        with connection() as conn:
            conn.execute(
                "UPDATE evidence_units SET embedding = NULL WHERE episode_id = %s", (episode_id,)
            )
        return
    chroma_collection().delete(where={"episode_id": episode_id})


def corpus_counts() -> tuple[int, int]:
    with connection() as conn:
        episode_count = conn.execute("SELECT COUNT(*) AS count FROM episodes").fetchone()["count"]
        unit_count = conn.execute("SELECT COUNT(*) AS count FROM evidence_units").fetchone()[
            "count"
        ]
    return episode_count, unit_count


def corpus_manifest() -> dict[str, Any]:
    """Return the versions and counts required to reproduce the active index."""
    episode_count, unit_count = corpus_counts()
    try:
        active_vector_count = vector_count()
    except Exception:
        active_vector_count = 0
    return {
        "evidence_build_version": EVIDENCE_BUILD_VERSION,
        "embedding_version": embedding_version(),
        "episodes": episode_count,
        "evidence_units": unit_count,
        "vectors": active_vector_count,
    }


def _remove_stale_episodes(active_episode_ids: set[str], collection=None) -> None:
    """Reconcile DB and vector state when source transcript folders are removed."""
    with connection() as conn:
        rows = conn.execute("SELECT id FROM episodes").fetchall()
        stale_ids = [row["id"] for row in rows if row["id"] not in active_episode_ids]
        for episode_id in stale_ids:
            if get_settings().vector_backend != "pgvector" and collection is not None:
                collection.delete(where={"episode_id": episode_id})
            conn.execute("DELETE FROM episodes WHERE id = %s", (episode_id,))


def run_ingestion(limit: int | None = None, force: bool = False) -> None:
    settings = get_settings()
    paths = sorted(settings.episodes_dir.glob("*/transcript.md"))
    if limit:
        paths = paths[:limit]
    ingestion_state.update(
        state="running",
        episodes_total=len(paths),
        episodes_processed=0,
        evidence_units=0,
        error=None,
    )
    run_id = uuid4()
    with connection() as conn:
        conn.execute("INSERT INTO ingestion_runs (id, state) VALUES (%s, 'running')", (run_id,))

    try:
        topic_map = load_topic_map(settings.topics_dir)
        collection = chroma_collection() if settings.vector_backend != "pgvector" else None
        total_units = 0
        pending_vectors: list[EvidenceUnit] = []
        for index, path in enumerate(paths, start=1):
            episode = parse_episode(path)
            topics = topic_map.get(episode.id, [])
            if force:
                with connection() as conn:
                    conn.execute("DELETE FROM evidence_units WHERE episode_id = %s", (episode.id,))
            units = build_evidence_units(episode, topics)
            episode_changed = _upsert_episode(episode, units, topics)
            vector_ids = []
            if not episode_changed and not force:
                vector_ids = episode_vector_ids(episode.id)
            if episode_changed or force or len(vector_ids) != len(units):
                delete_episode_vectors(episode.id)
                pending_vectors.extend(units)
            if len(pending_vectors) >= 768:
                _upsert_vector_units(collection, pending_vectors)
                pending_vectors = []
            total_units += len(units)
            ingestion_state.update(episodes_processed=index, evidence_units=total_units)

        if pending_vectors:
            _upsert_vector_units(collection, pending_vectors)

        if limit is None:
            _remove_stale_episodes({path.parent.name for path in paths}, collection)

        ingestion_state.update(state="complete")
        with connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_runs SET state = 'complete', episodes_processed = %s,
                evidence_units = %s, completed_at = NOW() WHERE id = %s
                """,
                (len(paths), total_units, run_id),
            )
    except Exception as exc:
        error_code = failure_code(exc)
        ingestion_state.update(state="failed", error=error_code)
        with connection() as conn:
            conn.execute(
                "UPDATE ingestion_runs SET state = 'failed', error = %s, completed_at = NOW() WHERE id = %s",
                (error_code, run_id),
            )
        raise


def maybe_start_ingestion() -> None:
    settings = get_settings()
    if not settings.auto_ingest:
        return
    try:
        episode_count, unit_count = corpus_counts()
    except Exception as exc:
        ingestion_state.update(state="failed", error=failure_code(exc))
        return
    expected_episode_count = len(list(settings.episodes_dir.glob("*/transcript.md")))
    with connection() as conn:
        current_version_count = conn.execute(
            "SELECT COUNT(*) AS count FROM episodes WHERE metadata->>'evidence_build_version' = %s",
            (EVIDENCE_BUILD_VERSION,),
        ).fetchone()["count"]
    try:
        active_vector_count = vector_count()
    except Exception:
        active_vector_count = -1
    if (
        episode_count == expected_episode_count
        and current_version_count == expected_episode_count
        and unit_count > 0
        and active_vector_count == unit_count
    ):
        ingestion_state.update(
            state="complete",
            episodes_total=episode_count,
            episodes_processed=episode_count,
            evidence_units=unit_count,
        )
        return
    thread = threading.Thread(target=run_ingestion, name="corpus-ingestion", daemon=True)
    thread.start()
