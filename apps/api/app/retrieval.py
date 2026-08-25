from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from app.config import get_settings
from app.database import connection
from app.indexing import chroma_collection, embed_query, embedding_version

WORD = re.compile(r"[a-z0-9][a-z0-9+#.-]+", re.IGNORECASE)
RRF_K = 60
TOPIC_SYNONYMS = {
    "pmf": "product market fit",
    "product-market fit": "product market fit",
    "ab testing": "ab testing",
    "a/b testing": "ab testing",
    "ai": "ai",
    "artificial intelligence": "ai",
    "plg": "product led growth",
}
GUEST_QUERY_FILLER = {
    "about", "an", "and", "can", "episode", "from", "it", "lenny", "make",
    "me", "of", "podcast", "say", "the", "this", "use", "what", "with",
}
def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in WORD.findall(text) if len(token) > 1}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def match_guest_reference(
    reference: str, episodes: list[dict[str, Any]]
) -> dict[str, Any]:
    """Resolve a noisy guest mention from catalog data without guest-specific rules."""
    words = _normalize(reference).split()
    phrases = {" ".join(words[start:end]) for start in range(len(words)) for end in range(start + 1, min(len(words), start + 3) + 1)}
    grouped: dict[str, set[str]] = defaultdict(set)
    for episode in episodes:
        grouped[str(episode["guest"])].add(str(episode["id"]))

    scored: list[dict[str, Any]] = []
    for guest, episode_ids in grouped.items():
        guest_words = _normalize(guest).split()
        if not guest_words:
            continue
        first, last = guest_words[0], guest_words[-1]
        full = " ".join(guest_words)
        best = 0.0
        for phrase in phrases:
            phrase_words = phrase.split()
            if phrase == full:
                best = max(best, 1.0)
            if len(last) >= 5 and phrase == last:
                best = max(best, 0.94)
            if phrase == first:
                best = max(best, 0.68)
            if len(phrase_words) == 2 and len(guest_words) >= 2:
                first_score = SequenceMatcher(None, phrase_words[0], first).ratio()
                last_score = SequenceMatcher(None, phrase_words[1], last).ratio()
                if (
                    len(phrase_words[1]) == 1
                    and phrase_words[1] == last[:1]
                    and first_score >= 0.60
                ):
                    best = max(best, 0.90 + first_score * 0.05)
                elif first_score >= 0.72 and last_score >= 0.72:
                    best = max(best, (first_score + last_score) / 2)
        if best >= 0.60:
            scored.append({"guest": guest, "episode_ids": sorted(episode_ids), "score": round(best, 4)})

    scored.sort(key=lambda item: (-item["score"], item["guest"].casefold()))
    candidates = scored[:5]
    if not candidates:
        return {"status": "none", "reference": reference, "candidates": []}
    top = candidates[0]["score"]
    runner_up = candidates[1]["score"] if len(candidates) > 1 else 0.0
    if top >= 0.78 and top - runner_up >= 0.10:
        return {"status": "resolved", "reference": reference, "match": candidates[0], "candidates": candidates}
    return {"status": "ambiguous", "reference": reference, "candidates": candidates}


def resolve_guest_reference(reference: str) -> dict[str, Any]:
    with connection() as conn:
        episodes = [dict(row) for row in conn.execute("SELECT id, guest, title FROM episodes").fetchall()]
    return match_guest_reference(reference, episodes)


def clarification_for_resolution(resolution: dict[str, Any]) -> str:
    names = [candidate["guest"] for candidate in resolution.get("candidates", [])[:3]]
    if not names:
        return "I couldn't match that guest to the local podcast catalog. What is the guest's full name?"
    if len(names) == 1:
        return f"Do you mean {names[0]}?"
    return f"Which guest do you mean: {', '.join(names[:-1])}, or {names[-1]}?"


def decompose_query(query: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", query).strip()
    if len(cleaned) < 90 and not re.search(r"\b(compare|versus|vs\.?|both)\b", cleaned, re.I):
        return [cleaned]
    parts = re.split(
        r"\s+(?:versus|vs\.?|and then|compared with|compare with)\s+|[?;]+", cleaned, flags=re.I
    )
    parts = [part.strip(" ,.") for part in parts if len(part.strip()) >= 12]
    return parts[:4] or [cleaned]


def resolve_constraints(
    query: str, guest: str | None, topic: str | None
) -> tuple[str | None, str | None]:
    normalized_query = f" {_normalize(query)} "
    with connection() as conn:
        guests = [
            row["guest"] for row in conn.execute("SELECT DISTINCT guest FROM episodes").fetchall()
        ]
        topics = [
            row["topic"]
            for row in conn.execute("SELECT DISTINCT topic FROM episode_topics").fetchall()
        ]

    resolved_guest = guest
    if not resolved_guest:
        matches: list[tuple[int, str]] = []
        for candidate in guests:
            normalized_guest = _normalize(candidate)
            last_name = normalized_guest.split()[-1] if normalized_guest.split() else ""
            if f" {normalized_guest} " in normalized_query:
                matches.append((len(normalized_guest), candidate))
            elif len(last_name) >= 5 and f" {last_name} " in normalized_query:
                matches.append((len(last_name), candidate))
        if matches:
            resolved_guest = max(matches)[1]

    resolved_topic = topic
    if not resolved_topic:
        for phrase, canonical in TOPIC_SYNONYMS.items():
            if f" {_normalize(phrase)} " in normalized_query:
                resolved_topic = canonical
                break
    if not resolved_topic:
        matches = [
            candidate for candidate in topics if f" {_normalize(candidate)} " in normalized_query
        ]
        if matches:
            resolved_topic = max(matches, key=len)
    return resolved_guest, resolved_topic


def resolve_guests(query: str) -> list[str]:
    normalized_query = f" {_normalize(query)} "
    with connection() as conn:
        guests = [
            row["guest"] for row in conn.execute("SELECT DISTINCT guest FROM episodes").fetchall()
        ]
    matches: list[tuple[int, str]] = []
    for candidate in guests:
        normalized_guest = _normalize(candidate)
        last_name = normalized_guest.split()[-1] if normalized_guest.split() else ""
        if f" {normalized_guest} " in normalized_query:
            matches.append((len(normalized_guest), candidate))
        elif len(last_name) >= 5 and f" {last_name} " in normalized_query:
            matches.append((len(last_name), candidate))
    ordered = sorted(matches, key=lambda item: (-item[0], item[1]))
    return list(dict.fromkeys(candidate for _, candidate in ordered))


def corpus_catalog(query: str = "", limit: int = 12) -> dict[str, Any]:
    """Return a compact, searchable tree of the corpus without transcript retrieval."""
    query_tokens = _tokens(query)
    with connection() as conn:
        episodes = list(
            conn.execute(
                "SELECT id, guest, title FROM episodes ORDER BY lower(guest), lower(title)"
            ).fetchall()
        )
        topics = [
            row["topic"]
            for row in conn.execute(
                "SELECT topic, lower(topic) AS topic_sort "
                "FROM episode_topics GROUP BY topic ORDER BY topic_sort"
            ).fetchall()
        ]

    def overlap(value: str) -> int:
        return len(query_tokens & _tokens(value))

    matching_topics = sorted(
        (topic for topic in topics if overlap(topic)),
        key=lambda topic: (-overlap(topic), topic.casefold()),
    )[:limit]
    matching_episodes = sorted(
        (episode for episode in episodes if overlap(f"{episode['guest']} {episode['title']}")),
        key=lambda episode: (
            -overlap(f"{episode['guest']} {episode['title']}"),
            episode["guest"].casefold(),
        ),
    )[:limit]
    return {
        "corpus": "Lenny's Podcast transcripts",
        "tree": {
            "indexes/by-topic": {
                "count": len(topics),
                "matches": matching_topics,
                "examples": topics[: min(10, limit)],
            },
            "episodes/by-guest": {
                "count": len(episodes),
                "matches": [dict(episode) for episode in matching_episodes],
                "examples": [dict(episode) for episode in episodes[: min(10, limit)]],
            },
        },
        "guidance": (
            "Use a guest, episode title, or topic to narrow transcript research. "
            "The examples are a preview, not the complete catalog."
        ),
    }


def _topic_episode_ids(topic: str | None) -> set[str]:
    if not topic:
        return set()
    with connection() as conn:
        rows = conn.execute(
            "SELECT episode_id FROM episode_topics WHERE topic = %s OR topic ILIKE %s",
            (topic, f"%{topic}%"),
        ).fetchall()
    return {row["episode_id"] for row in rows}


def _lexical_candidates(
    query: str, guest: str | None, limit: int, episode_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    params: list[Any] = [query, query]
    guest_clause = ""
    if guest:
        guest_clause = "AND (lower(guest) = lower(%s) OR lower(guest) LIKE lower(%s))"
        params.extend((guest, f"{guest} %"))
    episode_clause = ""
    if episode_ids:
        episode_clause = "AND episode_id = ANY(%s)"
        params.append(sorted(episode_ids))
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, ts_rank_cd(search_tsv, plainto_tsquery('english', %s)) AS lexical_score
            FROM evidence_units
            WHERE search_tsv @@ plainto_tsquery('english', %s)
            {guest_clause} {episode_clause}
            ORDER BY lexical_score DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
        if rows:
            return list(rows)
        fallback_params: list[Any] = [f"%{query[:180]}%"]
        if guest:
            fallback_params.extend((guest, f"{guest} %"))
        if episode_ids:
            fallback_params.append(sorted(episode_ids))
        fallback_params.append(limit)
        return list(
            conn.execute(
                f"""
                SELECT id, 0.01 AS lexical_score FROM evidence_units
                WHERE search_document ILIKE %s {guest_clause} {episode_clause}
                LIMIT %s
                """,
                fallback_params,
            ).fetchall()
        )


def _dense_candidates(query: str, guest: str | None, limit: int) -> list[dict[str, Any]]:
    try:
        collection = chroma_collection()
        guest_aliases: list[str | None] = [None]
        if guest:
            with connection() as conn:
                guest_aliases = [
                    row["guest"]
                    for row in conn.execute(
                        """
                        SELECT DISTINCT guest FROM episodes
                        WHERE lower(guest) = lower(%s) OR lower(guest) LIKE lower(%s)
                        """,
                        (guest, f"{guest} %"),
                    ).fetchall()
                ] or [guest]
        candidates: dict[str, float] = {}
        for guest_alias in guest_aliases:
            options: dict[str, Any] = {
                "query_embeddings": [embed_query(query)],
                "n_results": limit,
                "include": ["distances", "metadatas"],
            }
            if guest_alias:
                options["where"] = {"guest": guest_alias}
            result = collection.query(**options)
            ids = (result.get("ids") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            for unit_id, distance in zip(ids, distances, strict=False):
                score = max(0.0, 1.0 - float(distance))
                candidates[unit_id] = max(candidates.get(unit_id, 0.0), score)
        return [
            {"id": unit_id, "dense_score": score}
            for unit_id, score in sorted(
                candidates.items(), key=lambda item: item[1], reverse=True
            )
        ]
    except Exception:
        return []


def _load_units(ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, episode_id, guest, title, speaker, start_seconds, end_seconds,
                   timestamp_label, youtube_url, excerpt, topics
            FROM evidence_units WHERE id = ANY(%s)
            """,
            (ids,),
        ).fetchall()
    return {row["id"]: dict(row) for row in rows}


def search_transcripts(
    query: str,
    *,
    guest: str | None = None,
    topic: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    limit = limit or settings.retrieval_limit
    resolution = resolve_guest_reference(guest or query)
    if guest and resolution["status"] != "resolved":
        return {
            "query": query,
            "route": "clarification",
            "resolved_guest": None,
            "resolved_guests": [],
            "resolved_topic": None,
            "entity_resolution": resolution,
            "needs_clarification": True,
            "clarification": clarification_for_resolution(resolution),
            "evidence": [],
        }
    if not guest and resolution["status"] == "ambiguous":
        return {
            "query": query,
            "route": "clarification",
            "resolved_guest": None,
            "resolved_guests": [],
            "resolved_topic": None,
            "entity_resolution": resolution,
            "needs_clarification": True,
            "clarification": clarification_for_resolution(resolution),
            "evidence": [],
        }
    matched = resolution.get("match") if resolution["status"] == "resolved" else None
    catalog_guest = matched["guest"] if matched else None
    episode_scope = set(matched["episode_ids"]) if matched else set()
    retrieval_query = query
    if episode_scope and catalog_guest:
        remaining = _tokens(query) - _tokens(catalog_guest) - GUEST_QUERY_FILLER
        if not remaining:
            with connection() as conn:
                titles = [
                    row["title"]
                    for row in conn.execute(
                        "SELECT title FROM episodes WHERE id = ANY(%s)",
                        (sorted(episode_scope),),
                    ).fetchall()
                ]
            retrieval_query = " ".join(titles) or query
    resolved_guest, resolved_topic = resolve_constraints(query, catalog_guest, None)
    if topic:
        with connection() as conn:
            known_topics = [row["topic"] for row in conn.execute("SELECT DISTINCT topic FROM episode_topics").fetchall()]
        normalized_topic = _normalize(topic)
        topic_matches = [candidate for candidate in known_topics if _normalize(candidate) == normalized_topic]
        resolved_topic = topic_matches[0] if topic_matches else resolved_topic
    resolved_guests = [resolved_guest] if resolved_guest else resolve_guests(query)
    if len(resolved_guests) > 1:
        resolved_guest = None
    topic_episodes = _topic_episode_ids(resolved_topic)
    route = (
        "multi-guest"
        if len(resolved_guests) > 1
        else "guest+topic"
        if resolved_guest and resolved_topic
        else "guest"
        if resolved_guest
        else "topic"
        if resolved_topic
        else "global"
    )
    subqueries = decompose_query(retrieval_query)
    fused_scores: defaultdict[str, float] = defaultdict(float)
    diagnostics: defaultdict[str, dict[str, float]] = defaultdict(dict)

    for subquery in subqueries:
        lexical = _lexical_candidates(subquery, resolved_guest, settings.candidate_limit, episode_scope)
        dense = _dense_candidates(subquery, resolved_guest, settings.candidate_limit)
        for rank, candidate in enumerate(lexical, start=1):
            unit_id = candidate["id"]
            fused_scores[unit_id] += 1.0 / (RRF_K + rank)
            diagnostics[unit_id]["lexical"] = float(candidate.get("lexical_score") or 0.0)
        for rank, candidate in enumerate(dense, start=1):
            unit_id = candidate["id"]
            fused_scores[unit_id] += 1.0 / (RRF_K + rank)
            diagnostics[unit_id]["dense"] = float(candidate.get("dense_score") or 0.0)

    units = _load_units(list(fused_scores))
    query_tokens = _tokens(retrieval_query)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for unit_id, fused in fused_scores.items():
        unit = units.get(unit_id)
        if not unit:
            continue
        if episode_scope and unit["episode_id"] not in episode_scope:
            continue
        excerpt_tokens = _tokens(unit["excerpt"])
        overlap = len(query_tokens & excerpt_tokens) / max(1, len(query_tokens))
        topic_boost = 0.08 if unit["episode_id"] in topic_episodes else 0.0
        unit_guest = unit["guest"].casefold()
        resolved_guest_keys = {item.casefold() for item in resolved_guests}
        guest_boost = (
            0.12
            if resolved_guest_keys
            and any(
                unit_guest == key or unit_guest.startswith(f"{key} ")
                for key in resolved_guest_keys
            )
            else 0.0
        )
        score = fused * 10.0 + overlap * 0.55 + topic_boost + guest_boost
        diagnostics[unit_id]["fused"] = fused
        diagnostics[unit_id]["overlap"] = overlap
        diagnostics[unit_id]["rerank"] = score
        ranked.append((score, unit))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict[str, Any]] = []
    episode_counts: defaultdict[str, int] = defaultdict(int)
    candidate_episodes = {unit["episode_id"] for _, unit in ranked}
    max_per_episode = (
        4 if route == "guest" and len(candidate_episodes) > 1 else limit if route == "guest" else 3
    )
    if len(resolved_guests) > 1:
        for expected_guest in resolved_guests:
            match = next(
                (
                    item
                    for item in ranked
                    if item[1]["guest"].casefold() == expected_guest.casefold()
                    or item[1]["guest"].casefold().startswith(f"{expected_guest.casefold()} ")
                ),
                None,
            )
            if match and all(existing["id"] != match[1]["id"] for existing in selected):
                score, unit = match
                episode_counts[unit["episode_id"]] += 1
                selected.append(
                    {
                        "id": unit["id"], "episode_id": unit["episode_id"],
                        "guest": unit["guest"], "title": unit["title"],
                        "speaker": unit["speaker"], "start_seconds": unit["start_seconds"],
                        "end_seconds": unit["end_seconds"], "timestamp": unit["timestamp_label"],
                        "youtube_url": unit["youtube_url"], "excerpt": unit["excerpt"],
                        "score": round(score, 6), "route": route,
                        "diagnostics": diagnostics[unit["id"]],
                    }
                )
    for score, unit in ranked:
        if any(existing["id"] == unit["id"] for existing in selected):
            continue
        if episode_counts[unit["episode_id"]] >= max_per_episode:
            continue
        episode_counts[unit["episode_id"]] += 1
        selected.append(
            {
                "id": unit["id"],
                "episode_id": unit["episode_id"],
                "guest": unit["guest"],
                "title": unit["title"],
                "speaker": unit["speaker"],
                "start_seconds": unit["start_seconds"],
                "end_seconds": unit["end_seconds"],
                "timestamp": unit["timestamp_label"],
                "youtube_url": unit["youtube_url"],
                "excerpt": unit["excerpt"],
                "score": round(score, 6),
                "route": route,
                "diagnostics": diagnostics[unit["id"]],
            }
        )
        if len(selected) >= limit:
            break

    return {
        "query": query,
        "retrieval_query": retrieval_query,
        "subqueries": subqueries,
        "route": route,
        "resolved_guest": resolved_guest,
        "resolved_guests": resolved_guests,
        "resolved_topic": resolved_topic,
        "resolved_episode_ids": sorted(episode_scope),
        "entity_resolution": resolution,
        "needs_clarification": False,
        "evidence": selected,
        "candidate_ids": list(fused_scores),
        "pre_rerank_ids": [unit_id for unit_id, _ in sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)],
        "post_rerank_ids": [unit["id"] for _, unit in ranked],
        "embedding_version": embedding_version(),
    }


def get_source(source_id: str) -> dict[str, Any] | None:
    units = _load_units([source_id])
    unit = units.get(source_id)
    if not unit:
        return None
    unit["score"] = 1.0
    unit["route"] = "source"
    unit["timestamp"] = unit.pop("timestamp_label")
    return unit


def get_source_context(source_id: str, radius: int = 1) -> dict[str, Any] | None:
    source = get_source(source_id)
    if not source:
        return None
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id FROM evidence_units
            WHERE episode_id = %s
            ORDER BY ABS(start_seconds - %s), start_seconds
            LIMIT %s
            """,
            (source["episode_id"], source["start_seconds"], radius * 2 + 1),
        ).fetchall()
    evidence = [item for row in rows if (item := get_source(row["id"]))]
    evidence.sort(key=lambda item: item["start_seconds"])
    return {"source": source, "evidence": evidence}
