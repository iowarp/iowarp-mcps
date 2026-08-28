"""Persistent local identity and Docket discovery for FastMCP tasks."""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote, urlencode

import httpx
from fastmcp.exceptions import ToolError
from platformdirs import user_config_path
from pydantic import SecretStr

from web_mcp.config import Settings

if TYPE_CHECKING:
    from fastmcp_tasks import TasksExtension


@dataclass(frozen=True)
class TaskRuntime:
    """Resolved Docket connection and stable local task identity."""

    url: str
    queue_name: str
    agent_id: str
    encryption_key: str


def build_tasks_extension(configured: Settings) -> TasksExtension:
    """Resolve task infrastructure and construct FastMCP's Tasks extension."""

    runtime = resolve_task_runtime(configured)
    os.environ["FASTMCP_TASKS_ENCRYPTION_KEY"] = runtime.encryption_key
    from fastmcp_tasks import TasksExtension
    from fastmcp_tasks.settings import tasks_settings

    tasks_settings.encryption_key = SecretStr(runtime.encryption_key)
    return TasksExtension(
        url=runtime.url,
        name=runtime.queue_name,
        concurrency=configured.task_concurrency,
    )


def resolve_task_runtime(configured: Settings) -> TaskRuntime:
    """Resolve local identity, encryption, and the remote Valkey session."""

    state_dir = _state_dir(configured)
    agent_id = _read_or_create(state_dir / "agent-id", lambda: secrets.token_hex(16))
    encryption_key = os.getenv("FASTMCP_TASKS_ENCRYPTION_KEY") or _read_or_create(
        state_dir / "tasks.key", lambda: secrets.token_urlsafe(48)
    )
    if configured.task_backend_url:
        return TaskRuntime(
            url=configured.task_backend_url,
            queue_name=configured.task_queue_name or f"clio-web-local-{agent_id[:16]}",
            agent_id=agent_id,
            encryption_key=encryption_key,
        )
    # ``document_service_url`` is the legacy conversion-only endpoint.  Only the
    # unified remote deployment contract advertises and provisions Docket.
    if not configured.remote_url:
        return TaskRuntime(
            url="memory://",
            queue_name=configured.task_queue_name or f"clio-web-local-{agent_id[:16]}",
            agent_id=agent_id,
            encryption_key=encryption_key,
        )
    session = _discover(configured, agent_id)
    return TaskRuntime(
        url=_docket_url(session, state_dir),
        queue_name=_required_string(session, "queue_name"),
        agent_id=agent_id,
        encryption_key=encryption_key,
    )


def _discover(configured: Settings, agent_id: str) -> dict[str, Any]:
    base = str(configured.effective_document_service_url).rstrip("/")
    timeout = httpx.Timeout(configured.read_timeout_s, connect=configured.connect_timeout_s)
    headers: dict[str, str] = {}
    if configured.remote_token:
        headers["Authorization"] = f"Bearer {configured.remote_token}"
    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            capabilities = client.get(f"{base}/v1/capabilities")
            capabilities.raise_for_status()
            capability_payload = capabilities.json()
            backend = capability_payload.get("task_backend")
            if not isinstance(backend, dict) or not backend.get("enabled"):
                raise ToolError(
                    "The configured CLIO Web Search service does not advertise a FastMCP task "
                    "backend. Upgrade it to 0.3.0 or configure WEB_TASK_BACKEND_URL explicitly."
                )
            session_path = str(backend.get("session_path") or "/v1/task-backend/session")
            response = client.post(f"{base}{session_path}", json={"agent_id": agent_id})
            if response.is_error:
                raise ToolError(_http_failure(response, "task-backend discovery"))
            payload = response.json()
    except ToolError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(
            "Could not initialize durable fetch tasks from CLIO Web Search. "
            f"Stage: task-backend discovery. Cause: {type(exc).__name__}. "
            "Fix: verify --remote-url, service readiness, and network access, then restart the "
            "Web MCP."
        ) from exc
    if not isinstance(payload, dict):
        raise ToolError(
            "CLIO Web Search returned malformed task-backend discovery data. Upgrade or repair "
            "the service before retrying."
        )
    return cast(dict[str, Any], payload)


def _docket_url(session: dict[str, Any], state_dir: Path) -> str:
    scheme = _required_string(session, "scheme")
    host = _required_string(session, "host")
    port = int(session.get("port", 0))
    database = int(session.get("database", 0))
    if scheme not in {"redis", "rediss"} or not (1 <= port <= 65535):
        raise ToolError(
            "CLIO Web Search returned an invalid Valkey endpoint. Repair its advertised task "
            "backend host, port, and scheme."
        )
    username = session.get("username")
    password = session.get("password")
    userinfo = ""
    if isinstance(username, str) and isinstance(password, str):
        userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    query: dict[str, str] = {}
    ca_pem = session.get("ca_pem")
    if scheme == "rediss":
        if not isinstance(ca_pem, str) or "BEGIN CERTIFICATE" not in ca_pem:
            raise ToolError(
                "Secure task discovery did not include a usable CA certificate. Repair the "
                "CLIO Web Search TLS configuration."
            )
        ca_path = state_dir / "valkey-ca.pem"
        _write_private(ca_path, ca_pem)
        query["ssl_ca_certs"] = str(ca_path)
        query["ssl_cert_reqs"] = "required"
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{scheme}://{userinfo}{host}:{port}/{database}{suffix}"


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ToolError(f"Task-backend discovery omitted required field {key!r}.")
    return value


def _http_failure(response: httpx.Response, stage: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if isinstance(payload, dict):
        message = payload.get("message")
        remediation = payload.get("remediation")
        if isinstance(message, str):
            fix = remediation if isinstance(remediation, str) else "Check the service logs."
            return f"{message} Stage: {stage}. Fix: {fix}"
    return (
        f"CLIO Web Search rejected {stage} with HTTP {response.status_code}. "
        "Fix: verify authentication and service readiness, then retry."
    )


def _state_dir(configured: Settings) -> Path:
    path = (
        Path(configured.state_dir).expanduser()
        if configured.state_dir
        else user_config_path("clio-kit", "IOWarp") / "web-mcp"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_or_create(path: Path, factory: Callable[[], str]) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        value = str(factory())
        _write_private(path, value)
    except OSError as exc:
        raise ToolError(f"Could not read persistent Web MCP state at {path}: {exc}") from exc
    if not value:
        raise ToolError(f"Persistent Web MCP state at {path} is empty; remove it and restart.")
    return value


def _write_private(path: Path, value: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        path.chmod(0o600)
    except OSError as exc:
        raise ToolError(f"Could not persist private Web MCP state at {path}: {exc}") from exc
