from __future__ import annotations

from typing import Any

import chromadb
import httpx

from app.database import connection
from app.dependencies import settings
from app.indexing import ingestion_state


async def readiness_snapshot() -> dict[str, Any]:
    dependencies: dict[str, Any] = {}
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        dependencies["postgres"] = {"status": "ok"}
    except Exception:
        dependencies["postgres"] = {"status": "error", "reason_code": "postgres_unreachable"}

    if settings.vector_backend == "chroma":
        try:
            chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
            chroma.heartbeat()
            dependencies["chroma"] = {"status": "ok"}
        except Exception:
            dependencies["chroma"] = {"status": "error", "reason_code": "chroma_unreachable"}
    else:
        dependencies["pgvector"] = {
            "status": "ok" if dependencies["postgres"]["status"] == "ok" else "error",
            "embedding": "supabase:gte-small",
        }

    async with httpx.AsyncClient(timeout=2.5, trust_env=False) as client:
        if settings.default_provider == "ollama" or settings.embedding_backend == "ollama":
            dependencies["ollama"] = await _ollama_readiness(client)
        else:
            dependencies["ollama"] = {"status": "disabled"}
        dependencies["agent"] = await _agent_readiness(client)

    required = ["postgres", "agent"]
    required.append("chroma" if settings.vector_backend == "chroma" else "pgvector")
    if settings.default_provider == "ollama" or settings.embedding_backend == "ollama":
        required.append("ollama")
    required_ok = all(dependencies[name]["status"] == "ok" for name in required)
    return {
        "status": "ok" if required_ok else "degraded",
        "dependencies": dependencies,
        "ingestion": ingestion_state.snapshot(),
    }


async def _ollama_readiness(client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        response = await client.get(settings.ollama_base_url.replace("/v1", "/api/tags"))
        response.raise_for_status()
        installed = {item.get("name") for item in response.json().get("models", [])}
        model_ready = settings.ollama_model in installed or f"{settings.ollama_model}:latest" in installed
        embedding_ready = (
            settings.embedding_backend != "ollama"
            or settings.ollama_embed_model in installed
            or f"{settings.ollama_embed_model}:latest" in installed
        )
        return {
            "status": "ok" if model_ready and embedding_ready else "error",
            "model": settings.ollama_model,
            "embedding_model": settings.ollama_embed_model,
            "reason_code": (
                None
                if model_ready and embedding_ready
                else "model_not_installed" if not model_ready else "embedding_model_not_installed"
            ),
            "thinking": settings.local_model_thinking,
        }
    except Exception:
        return {
            "status": "unavailable",
            "model": settings.ollama_model,
            "reason_code": "ollama_unreachable",
        }


async def _agent_readiness(client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        response = await client.get(f"{settings.agent_url.rstrip('/')}/health")
        return {
            "status": "ok" if response.is_success else "error",
            "reason_code": None if response.is_success else "pi_unready",
        }
    except Exception:
        return {"status": "unavailable", "reason_code": "pi_unreachable"}
