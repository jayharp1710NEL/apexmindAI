"""Application settings, loaded from environment (.env).

This is the single source of runtime configuration. Provider API keys live here but
are only ever read by adapters under app/router/adapters/.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-prod"

    # Datastores
    database_url: str = "postgresql+asyncpg://apex:apex@postgres:5432/apexmind"
    redis_url: str = "redis://redis:6379/0"

    # Routing
    default_provider: str = "anthropic"
    routing_config_path: str = "app/router/routing.yaml"

    # Provider keys (read only by adapters)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    local_openai_base_url: str | None = None
    local_openai_api_key: str | None = None

    # Safety
    estop_key: str = "apex:estop"
    approval_timeout_seconds: int = 300
    max_tool_level: int = 4
    audit_log_immutable: bool = True

    # Orchestrator budgets
    max_steps: int = 12
    max_run_seconds: int = 300
    max_run_cost_usd: float = 1.00

    # Sandbox
    # "local"  -> run code in an in-process subprocess sandbox (dev/tests)
    # "worker" -> enqueue to the isolated tool-worker over Redis (production stack)
    tool_exec_mode: str = "local"
    sandbox_timeout_seconds: int = 10
    sandbox_mem_mb: int = 256
    sandbox_max_output_bytes: int = 65536

    # RAG
    embedding_task_type: str = "embeddings"
    rag_top_k: int = 5
    # Max cosine distance for a chunk to count as supporting evidence; above this
    # the answer is "Unverified". Tune per embedding model without code changes.
    rag_max_distance: float = 0.6
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64


settings = Settings()
