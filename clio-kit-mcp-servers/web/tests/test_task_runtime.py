"""Task-backend discovery, identity, and diagnostic tests."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastmcp.exceptions import ToolError
from pytest_httpx import HTTPXMock

from web_mcp.config import Settings
from web_mcp.task_runtime import resolve_task_runtime

_REMOTE = "https://clio-web.test:8089"


def _add_discovery_responses(httpx_mock: HTTPXMock, session: object) -> None:
    """Register the capability and session responses used by discovery tests."""

    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={"task_backend": {"enabled": True}},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_REMOTE}/v1/task-backend/session",
        json=session,
    )


def test_remote_runtime_discovers_stable_agent_queue(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """Unified remote configuration discovers per-agent Docket credentials."""

    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={
            "task_backend": {
                "enabled": True,
                "session_path": "/v1/task-backend/session",
            }
        },
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_REMOTE}/v1/task-backend/session",
        json={
            "scheme": "redis",
            "host": "homelab",
            "port": 8090,
            "database": 0,
            "username": "agent-a",
            "password": "secret",
            "queue_name": "clio-web-prod-agent-a",
        },
    )

    configured = Settings(
        remote_url=_REMOTE,
        remote_token="deployment-token",  # noqa: S106 - test-only credential
        state_dir=str(tmp_path),
    )
    first = resolve_task_runtime(configured)

    assert first.url == "redis://agent-a:secret@homelab:8090/0"
    assert first.queue_name == "clio-web-prod-agent-a"
    request = httpx_mock.get_requests()[1]
    assert request.headers["Authorization"] == "Bearer deployment-token"
    assert request.read().decode()

    httpx_mock.reset()
    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={"task_backend": {"enabled": True}},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_REMOTE}/v1/task-backend/session",
        json={
            "scheme": "redis",
            "host": "homelab",
            "port": 8090,
            "database": 0,
            "username": "agent-a",
            "password": "secret",
            "queue_name": "clio-web-prod-agent-a",
        },
    )
    second = resolve_task_runtime(configured)
    assert second.agent_id == first.agent_id
    assert second.encryption_key == first.encryption_key


def test_remote_runtime_reports_actionable_discovery_failure(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Startup failures state the stage and corrective action for an agent."""

    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={"task_backend": {"enabled": False}},
    )
    with pytest.raises(ToolError) as error:
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))

    message = str(error.value)
    assert "task backend" in message
    assert "Upgrade" in message or "configure" in message


def test_legacy_document_service_does_not_require_valkey_discovery(tmp_path: Path) -> None:
    """Legacy document-only configuration keeps a local in-memory task runtime."""

    runtime = resolve_task_runtime(
        Settings(document_service_url="http://legacy.test", state_dir=str(tmp_path))
    )
    assert runtime.url == "memory://"


def test_explicit_task_backend_skips_remote_discovery(tmp_path: Path) -> None:
    """An operator-provided Docket URL remains a supported explicit override."""

    runtime = resolve_task_runtime(
        Settings(
            task_backend_url="redis://valkey.internal:6379/2",
            task_queue_name="web-fetches",
            state_dir=str(tmp_path),
        )
    )

    assert runtime.url == "redis://valkey.internal:6379/2"
    assert runtime.queue_name == "web-fetches"


def test_secure_remote_runtime_persists_discovered_ca(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A rediss session persists its CA and requires certificate verification."""

    ca_pem = "-----BEGIN CERTIFICATE-----\ntest-ca\n-----END CERTIFICATE-----"
    _add_discovery_responses(
        httpx_mock,
        {
            "scheme": "rediss",
            "host": "valkey.internal",
            "port": 6380,
            "database": 3,
            "username": "agent user",
            "password": "p@ss word",
            "queue_name": "secure-fetches",
            "ca_pem": ca_pem,
        },
    )

    runtime = resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))

    assert runtime.url.startswith("rediss://agent%20user:p%40ss%20word@valkey.internal:6380/3?")
    assert "ssl_cert_reqs=required" in runtime.url
    assert (tmp_path / "valkey-ca.pem").read_text(encoding="utf-8") == ca_pem


@pytest.mark.parametrize(
    ("session", "message"),
    [
        (
            {
                "scheme": "redis",
                "host": "valkey.internal",
                "port": 0,
                "queue_name": "fetches",
            },
            "invalid Valkey endpoint",
        ),
        (
            {
                "scheme": "rediss",
                "host": "valkey.internal",
                "port": 6380,
                "queue_name": "fetches",
            },
            "usable CA certificate",
        ),
        (
            {"scheme": "redis", "host": "valkey.internal", "port": 6379},
            "required field 'queue_name'",
        ),
    ],
)
def test_remote_runtime_rejects_unsafe_or_incomplete_session(
    httpx_mock: HTTPXMock,
    tmp_path: Path,
    session: dict[str, object],
    message: str,
) -> None:
    """Invalid discovered endpoints fail before Docket can contact the wrong service."""

    _add_discovery_responses(httpx_mock, session)

    with pytest.raises(ToolError, match=message):
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))


def test_remote_runtime_preserves_structured_session_error(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Backend session errors retain both the cause and operator remediation."""

    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={"task_backend": {"enabled": True}},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_REMOTE}/v1/task-backend/session",
        status_code=503,
        json={
            "message": "Valkey is unavailable.",
            "remediation": "Check the bundled Valkey process and persistent volume.",
        },
    )

    with pytest.raises(ToolError) as error:
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))

    assert "Valkey is unavailable" in str(error.value)
    assert "Check the bundled Valkey process" in str(error.value)


def test_remote_runtime_explains_non_json_session_error(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A proxy-style non-JSON response still identifies authentication and readiness checks."""

    httpx_mock.add_response(
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
        json={"task_backend": {"enabled": True}},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{_REMOTE}/v1/task-backend/session",
        status_code=502,
        text="upstream unavailable",
    )

    with pytest.raises(ToolError) as error:
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))

    assert "HTTP 502" in str(error.value)
    assert "verify authentication and service readiness" in str(error.value)


def test_remote_runtime_rejects_malformed_session_payload(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """A non-object discovery result yields an actionable compatibility error."""

    _add_discovery_responses(httpx_mock, ["not", "an", "object"])

    with pytest.raises(ToolError, match="malformed task-backend discovery data"):
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))


def test_remote_runtime_wraps_network_failure(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """A capability transport failure names discovery and the corrective checks."""

    httpx_mock.add_exception(
        httpx.ConnectError("connection closed"),
        method="GET",
        url=f"{_REMOTE}/v1/capabilities",
    )

    with pytest.raises(ToolError, match="task-backend discovery.*Fix:"):
        resolve_task_runtime(Settings(remote_url=_REMOTE, state_dir=str(tmp_path)))


def test_remote_runtime_rejects_empty_persistent_identity(tmp_path: Path) -> None:
    """Corrupt empty identity state explains the safe operator recovery action."""

    (tmp_path / "agent-id").write_text("", encoding="utf-8")

    with pytest.raises(ToolError, match="is empty; remove it and restart"):
        resolve_task_runtime(Settings(state_dir=str(tmp_path)))
