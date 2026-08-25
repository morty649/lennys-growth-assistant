from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(default="New investigation", min_length=1, max_length=120)
    provider: Literal["ollama", "anthropic"] = "ollama"
    model: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    provider: Literal["ollama", "anthropic"] | None = None
    model: str | None = None


class SessionView(BaseModel):
    id: UUID
    title: str
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime


class MessageView(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    status: str
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatRequest(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=12_000)
    provider: Literal["ollama", "anthropic"] | None = None
    model: str | None = None


class SourceView(BaseModel):
    id: str
    episode_id: str
    guest: str
    title: str
    speaker: str
    start_seconds: int
    end_seconds: int
    timestamp: str
    youtube_url: str
    excerpt: str
    score: float
    route: str


class ToolRunView(BaseModel):
    name: str
    status: str
    duration_ms: float
    input: dict[str, Any] = Field(default_factory=dict)
    origin: Literal["model", "server_fallback"] = "model"
    error_code: str | None = None


class ChatResponse(BaseModel):
    message: MessageView
    sources: list[SourceView]
    tool_runs: list[ToolRunView]
    grounded: bool
    used_fallback: bool = False
    grounding_state: Literal["supported", "insufficient", "not_applicable", "unverified"]
    execution_mode: Literal[
        "model", "direct", "catalog", "evidence_only", "abstention", "no_retrieval"
    ]
    requested_provider: str
    requested_model: str
    actual_provider: str | None = None
    actual_model: str | None = None
    fallback_reason_code: str | None = None
    latency_ms: float = 0.0


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    guest: str | None = None
    topic: str | None = None
    limit: int = Field(default=8, ge=1, le=20)


class CatalogRequest(BaseModel):
    query: str = Field(default="", max_length=1_000)
    limit: int = Field(default=12, ge=1, le=30)


class EntityResolveRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=1_000)


class ArtifactCreate(BaseModel):
    format: Literal["markdown", "html"]
    title: str = Field(min_length=1, max_length=160)
    source_message_id: UUID | None = None
    content: str | None = None


class ArtifactView(BaseModel):
    id: UUID
    session_id: UUID
    source_message_id: UUID | None = None
    format: str
    title: str
    source_content: str
    rendered_content: str
    source_evidence: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime


class IngestStatus(BaseModel):
    state: str
    episodes_total: int = 0
    episodes_processed: int = 0
    evidence_units: int = 0
    error: str | None = None
