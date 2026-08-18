"""Tests for the Settings configuration model."""

from __future__ import annotations

import pytest

from web_mcp.server import Settings


class TestSettingsDefaults:
    """Default values for a freshly constructed Settings object."""

    def test_default_search_provider_is_keyless_ddg(self) -> None:
        cfg = Settings()
        assert cfg.search_provider == "ddg"

    def test_default_keys_are_none(self) -> None:
        cfg = Settings()
        assert cfg.brave_api_key is None
        assert cfg.tavily_api_key is None
        assert cfg.searxng_base_url is None

    def test_default_max_bytes_is_5_mib(self) -> None:
        cfg = Settings()
        assert cfg.max_bytes == 5 * 1024 * 1024

    def test_default_timeouts(self) -> None:
        cfg = Settings()
        assert cfg.connect_timeout_s == 5.0
        assert cfg.read_timeout_s == 30.0

    def test_default_artifacts_root_is_none(self) -> None:
        cfg = Settings()
        assert cfg.artifacts_root is None

    def test_unified_remote_selects_searxng_automatically(self) -> None:
        cfg = Settings(remote_url="http://homelab:8089")
        assert cfg.search_provider == "searxng"

    def test_unified_remote_preserves_explicit_provider(self) -> None:
        cfg = Settings(remote_url="http://homelab:8089", search_provider="ddg")
        assert cfg.search_provider == "ddg"


class TestSettingsOverride:
    """Configuration is driven by explicit values, not ambient env."""

    def test_override_via_constructor(self) -> None:
        cfg = Settings(
            search_provider="brave",
            brave_api_key="secret",
            searxng_base_url="http://10.0.0.102:8088",
            max_bytes=123,
            connect_timeout_s=1.5,
            read_timeout_s=9.0,
            artifacts_root="custom/web/root",
        )
        assert cfg.search_provider == "brave"
        assert cfg.brave_api_key == "secret"
        assert cfg.searxng_base_url == "http://10.0.0.102:8088"
        assert cfg.max_bytes == 123
        assert cfg.connect_timeout_s == 1.5
        assert cfg.read_timeout_s == 9.0
        assert cfg.artifacts_root == "custom/web/root"

    def test_override_via_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
        monkeypatch.setenv("WEB_SEARXNG_BASE_URL", "http://10.0.0.102:8088")
        monkeypatch.setenv("WEB_MAX_BYTES", "2048")
        cfg = Settings()
        assert cfg.search_provider == "tavily"
        assert cfg.searxng_base_url == "http://10.0.0.102:8088"
        assert cfg.max_bytes == 2048
