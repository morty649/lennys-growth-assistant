from __future__ import annotations

import re
from collections.abc import Iterable

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)(api[-_ ]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\b(?:gsk|sk-ant|sk-proj)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(postgres(?:ql)?://[^:\s/]+:)[^@\s]+(@)"),
)


def redact_text(value: object, configured_secrets: Iterable[str] = ()) -> str:
    text = str(value)
    for secret in configured_secrets:
        if secret and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            text = pattern.sub(r"\1[REDACTED]\2", text)
        elif pattern.groups == 1:
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text[:500]


def failure_code(error: Exception) -> str:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    if "timeout" in name or "timeout" in message:
        return "provider_timeout"
    if "rate" in message and "limit" in message:
        return "provider_rate_limited"
    if "not configured" in message or "api_key" in message:
        return "provider_not_configured"
    if "connect" in message or "unreachable" in message:
        return "agent_unreachable"
    if "citation" in message:
        return "missing_valid_citations"
    return "agent_run_failed"
