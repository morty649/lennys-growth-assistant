from __future__ import annotations

import re
from typing import Any

SOURCE_TOKEN = re.compile(r"\[\[source:(?P<id>[^\]]+)\]\]")


def fallback_answer(evidence: list[dict[str, Any]], reason_code: str) -> str:
    if not evidence:
        return (
            "I could not find enough transcript evidence to answer that reliably. "
            "Try naming a guest, episode, or narrower topic."
        )
    lines = ["I couldn’t verify a grounded synthesis, so here are the closest transcript passages:", ""]
    for source in evidence[:3]:
        excerpt = re.sub(r"\s+", " ", source["excerpt"]).strip()
        if len(excerpt) > 420:
            excerpt = excerpt[:417].rsplit(" ", 1)[0] + "…"
        lines.append(f"- **{source['guest']}**: {excerpt} [[source:{source['id']}]]")
    lines.extend(["", f"Result mode: evidence only · {reason_code.replace('_', ' ')}."])
    return "\n".join(lines)


def collect_evidence(tool_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collected: dict[str, dict[str, Any]] = {}
    for tool_run in tool_runs:
        result = tool_run.get("result") or {}
        evidence = result.get("evidence") if isinstance(result, dict) else None
        if isinstance(evidence, list):
            for source in evidence:
                if isinstance(source, dict) and source.get("id"):
                    collected[source["id"]] = source
    return list(collected.values())


def clean_citations(text: str, evidence: list[dict[str, Any]]) -> tuple[str, set[str]]:
    allowed = {source["id"] for source in evidence}
    valid: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        source_id = match.group("id")
        if source_id in allowed:
            valid.add(source_id)
            return match.group(0)
        return ""

    return SOURCE_TOKEN.sub(replace, text), valid


def only_cited_evidence(
    evidence: list[dict[str, Any]], cited_ids: set[str]
) -> list[dict[str, Any]]:
    return [source for source in evidence if source["id"] in cited_ids]


def claims_have_citations(text: str) -> bool:
    normalized = re.sub(
        r"([.!?])\s*((?:\[\[source:[^\]]+\]\]\s*)+)",
        lambda match: f" {match.group(2).strip()}{match.group(1)} ",
        text,
    )
    claims = []
    for segment in re.split(r"(?<=[.!?])\s+|\n+", normalized):
        stripped = segment.strip()
        if not stripped or stripped.startswith("#"):
            continue
        without_tokens = SOURCE_TOKEN.sub("", stripped)
        if len(re.findall(r"\b[\w'-]+\b", without_tokens)) >= 8:
            claims.append(stripped)
    return bool(claims) and all(SOURCE_TOKEN.search(claim) for claim in claims)


def retain_cited_claims(text: str) -> str:
    normalized = re.sub(
        r"([.!?])\s*((?:\[\[source:[^\]]+\]\]\s*)+)",
        lambda match: f" {match.group(2).strip()}{match.group(1)} ",
        text,
    )
    kept: list[str] = []
    for segment in re.split(r"(?<=[.!?])\s+|\n+", normalized):
        stripped = segment.strip()
        if not stripped:
            continue
        word_count = len(re.findall(r"\b[\w'-]+\b", SOURCE_TOKEN.sub("", stripped)))
        if word_count < 8 or SOURCE_TOKEN.search(stripped):
            kept.append(stripped)
    return "\n".join(kept).strip()


def evidence_is_sufficient(evidence: list[dict[str, Any]]) -> bool:
    return bool(evidence) and float(evidence[0].get("score") or 0.0) >= 0.30


def render_citations(text: str, evidence: list[dict[str, Any]]) -> str:
    lookup = {source["id"]: source for source in evidence}

    def replace(match: re.Match[str]) -> str:
        source = lookup.get(match.group("id"))
        if not source:
            return ""
        label = f"{source['guest']} · {source['timestamp']}"
        return f"[{label}]({source['youtube_url']})"

    return SOURCE_TOKEN.sub(replace, text)
