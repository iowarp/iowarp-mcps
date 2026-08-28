"""Configuration for the Web MCP server."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from ``WEB_``-prefixed environment variables."""

    model_config = SettingsConfigDict(env_prefix="WEB_", env_file=".env", extra="ignore")

    search_provider: Literal["ddg", "searxng", "brave", "tavily"] = "ddg"
    searxng_base_url: str | None = None
    document_service_url: str | None = None
    remote_url: str | None = None
    remote_token: str | None = None
    brave_api_key: str | None = None
    tavily_api_key: str | None = None

    max_bytes: int = 5 * 1024 * 1024
    max_document_bytes: int = 50 * 1024 * 1024
    connect_timeout_s: float = 5.0
    read_timeout_s: float = 30.0
    conversion_poll_s: float = 1.0
    progress_heartbeat_s: float = 5.0

    artifacts_root: str | None = None
    allow_private_hosts: bool = False

    state_dir: str | None = None
    task_backend_url: str | None = None
    task_queue_name: str | None = None
    task_concurrency: int = 10

    @model_validator(mode="after")
    def select_unified_remote_provider(self) -> Settings:
        """Use the remote deployment's SearXNG unless a provider was explicit."""

        if self.remote_url and "search_provider" not in self.model_fields_set:
            self.search_provider = "searxng"
        return self

    @property
    def effective_document_service_url(self) -> str | None:
        """Return the unified remote URL or legacy document-service URL."""

        return self.remote_url or self.document_service_url

    @property
    def effective_searxng_url(self) -> str | None:
        """Return the unified remote URL or legacy SearXNG URL."""

        return self.remote_url or self.searxng_base_url
