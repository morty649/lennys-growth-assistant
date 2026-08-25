from __future__ import annotations

import re
from typing import Any

SOURCE_TOKEN = re.compile(r"\[\[source:(?P<id>[^\]]+)\]\]")
WORD_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

# Function words and common attribution language do not establish that a passage
# supports a claim. Keeping this list local makes the check deterministic and
# avoids introducing another model call into the grounding boundary.
NON_EVIDENTIAL_WORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing", "during",
    "each", "for", "from", "further", "had", "has", "have", "having", "he", "her",
    "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "more", "most", "my", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "our", "out", "over",
    "own", "same", "say", "says", "said", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "why", "will", "with",
    "would", "you", "your",
}


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


def cited_claims_are_supported(text: str, evidence: list[dict[str, Any]]) -> bool:
    """Require every cited factual claim to overlap materially with its passages.

    Citation validity and citation coverage are separate concerns: a model can cite a
    real passage that does not support what it wrote. This conservative lexical check
    catches that failure without pretending to be a full entailment model. It ignores
    headings and short connective copy, while long-form instructional takeaways can
    remain uncited and are therefore unaffected.
    """
    lookup = {str(source["id"]): source for source in evidence if source.get("id")}
    cited_claims = _cited_factual_claims(text)
    return bool(cited_claims) and all(
        _claim_supported_by_sources(claim, source_ids, lookup)
        for claim, source_ids in cited_claims
    )


def retain_supported_cited_claims(text: str, evidence: list[dict[str, Any]]) -> str:
    """Drop unsupported factual claim segments while retaining structural copy."""
    lookup = {str(source["id"]): source for source in evidence if source.get("id")}
    kept: list[str] = []
    for segment in _claim_segments(text):
        source_ids = [match.group("id") for match in SOURCE_TOKEN.finditer(segment)]
        if (
            not source_ids
            or len(_content_terms(SOURCE_TOKEN.sub("", segment))) < 2
            or _claim_supported_by_sources(segment, source_ids, lookup)
        ):
            kept.append(segment)
    return "\n".join(kept).strip()


def _cited_factual_claims(text: str) -> list[tuple[str, list[str]]]:
    claims: list[tuple[str, list[str]]] = []
    for segment in _claim_segments(text):
        source_ids = [match.group("id") for match in SOURCE_TOKEN.finditer(segment)]
        without_tokens = SOURCE_TOKEN.sub("", segment)
        if source_ids and len(_content_terms(without_tokens)) >= 2:
            claims.append((segment, source_ids))
    return claims


def _claim_segments(text: str) -> list[str]:
    normalized = re.sub(
        r"([.!?])\s*((?:\[\[source:[^\]]+\]\]\s*)+)",
        lambda match: f" {match.group(2).strip()}{match.group(1)} ",
        text,
    )
    return [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+|\n+", normalized)
        if segment.strip() and not segment.strip().startswith("#")
    ]


def _claim_supported_by_sources(
    claim: str,
    source_ids: list[str],
    lookup: dict[str, dict[str, Any]],
) -> bool:
    claim_terms = _content_terms(SOURCE_TOKEN.sub("", claim))
    if not claim_terms:
        return True
    source_terms: set[str] = set()
    for source_id in source_ids:
        source = lookup.get(source_id)
        if source:
            source_terms.update(_content_terms(str(source.get("excerpt") or "")))
    matches = claim_terms & source_terms
    required_matches = 1 if len(claim_terms) == 1 else 2
    required_coverage = 0.50 if len(claim_terms) <= 4 else 0.40
    return len(matches) >= required_matches and len(matches) / len(claim_terms) >= required_coverage


def _content_terms(text: str) -> set[str]:
    return {
        stemmed
        for token in WORD_TOKEN.findall(text.lower())
        if token not in NON_EVIDENTIAL_WORDS
        and len(stemmed := _stem(token)) >= 3
        and stemmed not in NON_EVIDENTIAL_WORDS
    }


def _stem(token: str) -> str:
    token = token.removesuffix("'s")
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) - len(suffix) >= 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


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
