from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    deployment_mode: str = "local"
    web_origin: str = "http://localhost:3000"
    database_url: str = "postgresql://lenny:lenny_local_password@localhost:5432/lenny_growth"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    corpus_root: Path = Field(default=Path("../.."))
    auto_ingest: bool = True
    embedding_backend: str = "ollama"
    vector_backend: str = "chroma"
    ollama_embed_model: str = "nomic-embed-text"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_embed_function: str = "embed"

    auth_mode: str = "local"
    anonymous_token_secret: str = "local-dev-anonymous-token-change-me"
    anonymous_token_ttl_days: int = 30
    chat_rate_limit: int = 20
    chat_rate_window_seconds: int = 3600

    agent_url: str = "http://localhost:8787"
    internal_tool_token: str = "local-dev-tool-token-change-me"
    default_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:8b"
    local_model_thinking: str = "off"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_api_key: str = ""
    enable_groq: bool = False
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str = ""

    request_timeout_seconds: float = 600.0
    retrieval_limit: int = 8
    candidate_limit: int = 30

    @property
    def episodes_dir(self) -> Path:
        return self.corpus_root / "episodes"

    @property
    def topics_dir(self) -> Path:
        return self.corpus_root / "index"

    @property
    def web_origins(self) -> list[str]:
        return [origin.strip() for origin in self.web_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
