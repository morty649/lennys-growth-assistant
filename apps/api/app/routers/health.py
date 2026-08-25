from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import settings
from app.readiness import readiness_snapshot

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, Any]:
    return await readiness_snapshot()


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "lenny-growth-api"}


@router.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    return await readiness_snapshot()


@router.get("/api/providers")
@router.get("/api/config")
async def config() -> dict[str, Any]:
    readiness = await readiness_snapshot()
    dependencies = readiness["dependencies"]
    ollama_ready = dependencies.get("ollama", {}).get("status") == "ok"
    providers = [
        {
            "id": "ollama",
            "label": "Ollama · local",
            "model": settings.ollama_model,
            "kind": "local",
            "enabled": ollama_ready,
            "availability": "ready" if ollama_ready else "unavailable",
            "reason": dependencies.get("ollama", {}).get("reason_code"),
            "thinking": settings.local_model_thinking,
        },
        {
            "id": "groq",
            "label": "GPT-OSS · Groq",
            "model": settings.groq_model,
            "kind": "cloud",
            "enabled": bool(settings.enable_groq and settings.groq_api_key),
            "availability": (
                "configured_unverified"
                if settings.enable_groq and settings.groq_api_key
                else "unavailable"
            ),
            "reason": (
                None
                if settings.enable_groq and settings.groq_api_key
                else "Groq is disabled or GROQ_API_KEY is missing"
            ),
        },
        {
            "id": "anthropic",
            "label": "Claude · cloud",
            "model": settings.anthropic_model,
            "kind": "cloud",
            "enabled": bool(settings.anthropic_api_key),
            "availability": (
                "configured_unverified" if settings.anthropic_api_key else "unavailable"
            ),
            "reason": (
                None if settings.anthropic_api_key else "Add ANTHROPIC_API_KEY to .env"
            ),
        },
    ]
    return {
        "default_provider": settings.default_provider,
        "providers": providers,
        "deployment_mode": settings.deployment_mode,
    }
