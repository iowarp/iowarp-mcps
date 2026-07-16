"""Generate and load canonical locked-server MCP user contracts.

The committed artifacts in :mod:`clio_kit._mcp_contracts` are captured from a
real MCP ``tools/list`` exchange over stdio.  They bind the agent-facing tool
schemas independently of the abbreviated MCP Registry metadata in
``server.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Final, Sequence, cast

JSON = dict[str, Any]

MCP_USER_CONTRACT_SCHEMA: Final = "clio-kit.mcp-user-contract.v1"
MCP_USER_CONTRACT_INDEX_SCHEMA: Final = "clio-kit.mcp-user-contract-index.v1"
MCP_USER_CONTRACT_CANONICALIZATION: Final = "json-sort-keys-compact-utf8-v1"
MCP_USER_CONTRACT_PROJECTION: Final = "mcp-agent-tool-schema-v1"
MAX_CONTRACT_BYTES: Final = 4 * 1024 * 1024
MAX_PROBE_OUTPUT_BYTES: Final = 16 * 1024 * 1024
MAX_PROBE_LINE_BYTES: Final = 4 * 1024 * 1024
MAX_PROBE_LINES: Final = 4_096
_PROBE_READ_CHUNK_BYTES: Final = 64 * 1024
_PROBE_DIAGNOSTIC_BYTES: Final = 2_000


class ContractGenerationError(RuntimeError):
    """Raised when a live user-contract probe is incomplete or invalid."""


class _ProbeOutputBuffer:
    """Bound stdout data while propagating terminal state out of band."""

    def __init__(self, max_lines: int) -> None:
        self._max_lines = max_lines
        self._lines: deque[bytes] = deque()
        self._failure: ContractGenerationError | None = None
        self._stdout_closed = False
        self._condition = threading.Condition()

    def put_line(self, line: bytes) -> bool:
        """Enqueue one stdout line, returning false when capacity is exhausted."""
        with self._condition:
            if self._failure is not None or self._stdout_closed:
                return False
            if len(self._lines) >= self._max_lines:
                return False
            self._lines.append(line)
            self._condition.notify()
            return True

    def fail(self, error: ContractGenerationError) -> bool:
        """Publish the first fatal error independently of queued stdout data."""
        with self._condition:
            if self._failure is not None:
                return False
            self._failure = error
            self._condition.notify_all()
            return True

    def close_stdout(self) -> None:
        """Publish stdout EOF independently of queued stdout data."""
        with self._condition:
            self._stdout_closed = True
            self._condition.notify_all()

    def failure(self) -> ContractGenerationError | None:
        """Return the first fatal probe error, if one has occurred."""
        with self._condition:
            return self._failure

    def get(self, deadline: float) -> bytes | None:
        """Wait until a line, EOF, failure, or the absolute deadline."""
        with self._condition:
            while True:
                if self._failure is not None:
                    raise self._failure
                if self._lines:
                    return self._lines.popleft()
                if self._stdout_closed:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                self._condition.wait(timeout=remaining)


@dataclass(frozen=True)
class UserContractSpec:
    """Static identity and acceptance policy for one locked user server."""

    contract_id: str
    artifact_name: str
    server_name: str
    distribution_name: str
    entry_command: str
    profile_environment: str
    expected_tools: frozenset[str]


USER_CONTRACT_SPECS: Final = (
    UserContractSpec(
        contract_id="clio-kit-jarvis-user-v3.2",
        artifact_name="jarvis-user-v3.2.json",
        server_name="jarvis",
        distribution_name="jarvis-mcp",
        entry_command="jarvis-mcp",
        profile_environment="JARVIS_MCP_PROFILE",
        expected_tools=frozenset(
            {
                "jarvis_create_pipeline",
                "jarvis_describe",
                "jarvis_add_step",
                "jarvis_edit_step",
                "jarvis_run",
                "jarvis_get_execution",
            }
        ),
    ),
    UserContractSpec(
        contract_id="clio-kit-slurm-user-v3",
        artifact_name="slurm-user-v3.json",
        server_name="slurm",
        distribution_name="slurm-mcp",
        entry_command="slurm-mcp",
        profile_environment="SLURM_MCP_PROFILE",
        expected_tools=frozenset(
            {
                "slurm_submit",
                "slurm_list",
                "slurm_describe",
                "slurm_cluster",
                "slurm_cancel",
            }
        ),
    ),
    UserContractSpec(
        contract_id="clio-kit-spack-user-v2",
        artifact_name="spack-user-v2.json",
        server_name="spack",
        distribution_name="spack-mcp",
        entry_command="spack-mcp",
        profile_environment="SPACK_MCP_PROFILE",
        expected_tools=frozenset({"spack_find", "spack_install", "spack_locate"}),
    ),
    UserContractSpec(
        contract_id="clio-kit-scientific-catalog-user-v1",
        artifact_name="scientific-catalog-user-v1.json",
        server_name="scientific-catalog",
        distribution_name="scientific-catalog-mcp",
        entry_command="scientific-catalog-mcp",
        profile_environment="SCIENTIFIC_CATALOG_PROFILE",
        expected_tools=frozenset(
            {"scientific_dataset_search", "scientific_dataset_describe"}
        ),
    ),
)

# Historical artifacts remain loadable by exact ID after an additive contract
# revision. They are immutable evidence, not probed against the current server.
HISTORICAL_USER_CONTRACT_ARTIFACTS: Final = (
    "jarvis-user-v3.json",
    "jarvis-user-v3.1.json",
)


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON with the stable encoding used by contract digests."""
    try:
        rendered = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ContractGenerationError("MCP contract contains non-JSON data") from exc
    return rendered.encode("utf-8")


def canonical_contract_projection(tools: Sequence[JSON]) -> JSON:
    """Project raw MCP Tool objects onto the stable agent-facing schema fields."""
    projected: list[JSON] = []
    seen: set[str] = set()
    for raw_tool in tools:
        name = raw_tool.get("name")
        input_schema = raw_tool.get("inputSchema")
        if not isinstance(name, str) or not name.strip():
            raise ContractGenerationError("tools/list returned a tool without a name")
        if name in seen:
            raise ContractGenerationError(f"tools/list returned duplicate tool: {name}")
        if not isinstance(input_schema, dict):
            raise ContractGenerationError(
                f"tools/list returned an invalid inputSchema for {name}"
            )
        for optional_string in ("title", "description"):
            value = raw_tool.get(optional_string)
            if value is not None and not isinstance(value, str):
                raise ContractGenerationError(
                    f"tools/list returned an invalid {optional_string} for {name}"
                )
        for optional_object in ("outputSchema", "annotations"):
            value = raw_tool.get(optional_object)
            if value is not None and not isinstance(value, dict):
                raise ContractGenerationError(
                    f"tools/list returned an invalid {optional_object} for {name}"
                )
        seen.add(name)
        projected.append(
            {
                "annotations": raw_tool.get("annotations"),
                "description": raw_tool.get("description"),
                "input_schema": input_schema,
                "name": name,
                "output_schema": raw_tool.get("outputSchema"),
                "title": raw_tool.get("title"),
            }
        )
    projected.sort(key=lambda tool: cast(str, tool["name"]))
    projection: JSON = {"tools": projected}
    canonical_json_bytes(projection)
    return projection


def mcp_user_contract_digest(tools: Sequence[JSON]) -> str:
    """Return the stable SHA-256 of an MCP user tool collection."""
    projection = canonical_contract_projection(tools)
    return hashlib.sha256(canonical_json_bytes(projection)).hexdigest()


def probe_user_contract(
    repository_root: Path,
    spec: UserContractSpec,
    *,
    timeout_seconds: float = 180.0,
) -> JSON:
    """Capture one locked server's actual user ``tools/list`` stdio response."""
    server_directory = (
        repository_root / "clio-kit-mcp-servers" / spec.server_name
    ).resolve(strict=True)
    uv = shutil.which("uv")
    if uv is None:
        raise ContractGenerationError("uv is required to probe MCP user contracts")
    environment = os.environ.copy()
    environment[spec.profile_environment] = "user"
    environment["MCP_TRANSPORT"] = "stdio"
    initialize, tools_list = exchange_mcp_tools_list(
        [
            uv,
            "run",
            "--isolated",
            "--refresh-package",
            spec.distribution_name,
            "--project",
            str(server_directory),
            "--no-dev",
            "--no-editable",
            "--frozen",
            spec.entry_command,
        ],
        environment=environment,
        contract_id=spec.contract_id,
        timeout_seconds=timeout_seconds,
    )
    initialize_result = initialize.get("result")
    tools_result = tools_list.get("result")
    if not isinstance(initialize_result, dict) or initialize.get("error") is not None:
        raise ContractGenerationError(f"{spec.contract_id} initialize failed")
    if not isinstance(tools_result, dict) or tools_list.get("error") is not None:
        raise ContractGenerationError(f"{spec.contract_id} tools/list failed")
    if tools_result.get("nextCursor") is not None:
        raise ContractGenerationError(
            f"{spec.contract_id} tools/list unexpectedly requires pagination"
        )
    raw_tools = tools_result.get("tools")
    if not isinstance(raw_tools, list) or not all(
        isinstance(tool, dict) for tool in raw_tools
    ):
        raise ContractGenerationError(
            f"{spec.contract_id} tools/list returned invalid tools"
        )
    tools = [cast(JSON, tool) for tool in raw_tools]
    canonical_contract_projection(tools)
    _validate_required_surface(spec, tools)
    protocol_version = initialize_result.get("protocolVersion")
    if not isinstance(protocol_version, str) or not protocol_version:
        raise ContractGenerationError(
            f"{spec.contract_id} initialize omitted protocolVersion"
        )
    tools.sort(key=lambda tool: cast(str, tool["name"]))
    projection = canonical_contract_projection(tools)
    artifact: JSON = {
        "schema_version": MCP_USER_CONTRACT_SCHEMA,
        "contract_id": spec.contract_id,
        "server_name": spec.server_name,
        "profile": "user",
        "source": {
            "method": "tools/list",
            "protocol_version": protocol_version,
            "transport": "stdio",
        },
        "canonicalization": MCP_USER_CONTRACT_CANONICALIZATION,
        "projection": MCP_USER_CONTRACT_PROJECTION,
        "contract_sha256": hashlib.sha256(canonical_json_bytes(projection)).hexdigest(),
        "wire_sha256": hashlib.sha256(
            canonical_json_bytes({"tools": tools})
        ).hexdigest(),
        "tool_names": [cast(str, tool["name"]) for tool in tools],
        "tools": tools,
    }
    return artifact


def exchange_mcp_tools_list(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    contract_id: str = "MCP server",
    timeout_seconds: float = 180.0,
    max_output_bytes: int = MAX_PROBE_OUTPUT_BYTES,
    max_line_bytes: int = MAX_PROBE_LINE_BYTES,
) -> tuple[JSON, JSON]:
    """Return initialize and tools/list responses with live stream bounds."""
    if timeout_seconds <= 0 or max_output_bytes <= 0 or max_line_bytes <= 0:
        raise ValueError("probe timeout and stream bounds must be positive")
    requests = _tools_list_requests()
    output_lines = _ProbeOutputBuffer(MAX_PROBE_LINES)
    deadline = time.monotonic() + timeout_seconds
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment or os.environ.copy(),
        )
    except OSError as exc:
        raise ContractGenerationError(f"could not probe {contract_id}: {exc}") from exc
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    stdin = process.stdin
    stdout = process.stdout
    stderr = process.stderr
    stderr_tail = bytearray()

    def fail_probe(message: str) -> None:
        error = ContractGenerationError(message)
        if output_lines.fail(error) and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def emit_stdout(line: bytes) -> None:
        if not output_lines.put_line(line) and output_lines.failure() is None:
            fail_probe(f"{contract_id} stdout line-count limit exceeded")

    def retain_stderr(chunk: bytes) -> None:
        stderr_tail.extend(chunk)
        overflow = len(stderr_tail) - _PROBE_DIAGNOSTIC_BYTES
        if overflow > 0:
            del stderr_tail[:overflow]

    stdout_reader = threading.Thread(
        target=_read_bounded_stream,
        kwargs={
            "stream": stdout,
            "stream_name": "stdout",
            "contract_id": contract_id,
            "max_output_bytes": max_output_bytes,
            "max_line_bytes": max_line_bytes,
            "on_line": emit_stdout,
            "on_chunk": None,
            "on_failure": fail_probe,
            "on_eof": output_lines.close_stdout,
        },
        name=f"{contract_id}-stdout",
        daemon=True,
    )
    stderr_reader = threading.Thread(
        target=_read_bounded_stream,
        kwargs={
            "stream": stderr,
            "stream_name": "stderr",
            "contract_id": contract_id,
            "max_output_bytes": max_output_bytes,
            "max_line_bytes": max_line_bytes,
            "on_line": None,
            "on_chunk": retain_stderr,
            "on_failure": fail_probe,
            "on_eof": None,
        },
        name=f"{contract_id}-stderr",
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()

    def wait_for_response(response_id: str) -> JSON:
        """Wait for one response and retain a failed child's bounded stderr."""
        try:
            return _wait_for_response(
                output_lines,
                response_id=response_id,
                deadline=deadline,
                contract_id=contract_id,
            )
        except ContractGenerationError as exc:
            if "closed stdout before response" not in str(exc):
                raise
            returncode: int | None
            try:
                returncode = process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                returncode = process.poll()
            stderr_reader.join(timeout=1.0)
            diagnostic = bytes(stderr_tail).decode("utf-8", errors="replace").strip()
            rendered_exit = "still running" if returncode is None else str(returncode)
            rendered_stderr = diagnostic or "<empty>"
            raise ContractGenerationError(
                f"{exc}; child exit={rendered_exit}; stderr: {rendered_stderr}"
            ) from exc

    try:
        stdin.write(canonical_json_bytes(requests[0]) + b"\n")
        stdin.flush()
        initialize = wait_for_response("initialize")
        for request in requests[1:]:
            stdin.write(canonical_json_bytes(request) + b"\n")
        stdin.flush()
        tools_list = wait_for_response("tools-list")
        stdin.close()
        remaining = max(0.1, deadline - time.monotonic())
        returncode = process.wait(timeout=remaining)
        stdout_reader.join(timeout=1.0)
        stderr_reader.join(timeout=1.0)
        failure = output_lines.failure()
        if failure is not None:
            raise failure
        if stdout_reader.is_alive() or stderr_reader.is_alive():
            raise ContractGenerationError(
                f"{contract_id} stream readers did not terminate"
            )
        if returncode != 0:
            diagnostic = bytes(stderr_tail).decode("utf-8", errors="replace")
            raise ContractGenerationError(
                f"{contract_id} exited with {returncode}: {diagnostic}"
            )
        return initialize, tools_list
    except (BrokenPipeError, OSError, subprocess.TimeoutExpired) as exc:
        failure = output_lines.failure()
        if failure is not None:
            raise failure from exc
        raise ContractGenerationError(
            f"could not complete {contract_id} stdio exchange: {exc}"
        ) from exc
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if not stdin.closed:
            stdin.close()
        stdout_reader.join(timeout=1.0)
        stderr_reader.join(timeout=1.0)
        stdout.close()
        stderr.close()


def _tools_list_requests() -> tuple[JSON, ...]:
    return (
        {
            "jsonrpc": "2.0",
            "id": "initialize",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "clio-kit-contract-generator",
                    "version": "1.0",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {},
        },
    )


def _read_bounded_stream(
    *,
    stream: BinaryIO,
    stream_name: str,
    contract_id: str,
    max_output_bytes: int,
    max_line_bytes: int,
    on_line: Callable[[bytes], None] | None,
    on_chunk: Callable[[bytes], None] | None,
    on_failure: Callable[[str], None],
    on_eof: Callable[[], None] | None,
) -> None:
    """Read one child pipe in fixed chunks and enforce limits while it runs."""
    total_bytes = 0
    line_count = 0
    pending = bytearray()
    try:
        while chunk := os.read(stream.fileno(), _PROBE_READ_CHUNK_BYTES):
            total_bytes += len(chunk)
            if total_bytes > max_output_bytes:
                on_failure(
                    f"{contract_id} {stream_name} byte limit exceeded "
                    f"({max_output_bytes} bytes)"
                )
                return
            if on_chunk is not None:
                on_chunk(chunk)
            parts = chunk.split(b"\n")
            pending.extend(parts[0])
            if len(pending) > max_line_bytes:
                on_failure(
                    f"{contract_id} {stream_name} line limit exceeded "
                    f"({max_line_bytes} bytes)"
                )
                return
            for part in parts[1:]:
                line_count += 1
                if line_count > MAX_PROBE_LINES:
                    on_failure(f"{contract_id} {stream_name} line-count limit exceeded")
                    return
                if on_line is not None:
                    on_line(bytes(pending))
                pending.clear()
                pending.extend(part)
                if len(pending) > max_line_bytes:
                    on_failure(
                        f"{contract_id} {stream_name} line limit exceeded "
                        f"({max_line_bytes} bytes)"
                    )
                    return
        if pending:
            line_count += 1
            if line_count > MAX_PROBE_LINES:
                on_failure(f"{contract_id} {stream_name} line-count limit exceeded")
                return
            if on_line is not None:
                on_line(bytes(pending))
    except OSError as exc:
        on_failure(f"could not read {contract_id} {stream_name}: {exc}")
    finally:
        if on_eof is not None:
            on_eof()


def _wait_for_response(
    output_lines: _ProbeOutputBuffer,
    *,
    response_id: str,
    deadline: float,
    contract_id: str,
) -> JSON:
    while True:
        try:
            line = output_lines.get(deadline)
        except TimeoutError as exc:
            raise ContractGenerationError(
                f"timed out waiting for {contract_id} response {response_id}"
            ) from exc
        if line is None:
            raise ContractGenerationError(
                f"{contract_id} closed stdout before response {response_id}"
            )
        try:
            decoded = json.loads(
                line.decode("utf-8", errors="strict"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(decoded, dict) and decoded.get("id") == response_id:
            return cast(JSON, decoded)


def generate_user_contract_artifacts(
    repository_root: Path,
    *,
    check: bool = False,
) -> list[JSON]:
    """Generate or verify every canonical locked-server contract artifact."""
    root = repository_root.resolve(strict=True)
    output_directory = root / "src" / "clio_kit" / "_mcp_contracts"
    artifacts = [probe_user_contract(root, spec) for spec in USER_CONTRACT_SPECS]
    artifact_payloads = [_formatted_json_bytes(artifact) for artifact in artifacts]
    historical: list[tuple[Path, bytes, JSON]] = []
    for artifact_name in HISTORICAL_USER_CONTRACT_ARTIFACTS:
        path = output_directory / artifact_name
        payload, artifact = _load_bounded_json_document(path)
        tools_value = artifact.get("tools")
        if not isinstance(tools_value, list) or not all(
            isinstance(tool, dict) for tool in tools_value
        ):
            raise ContractGenerationError(
                f"historical MCP user contract has invalid tools: {path}"
            )
        tools = cast(list[JSON], tools_value)
        observed_contract = mcp_user_contract_digest(tools)
        observed_wire = hashlib.sha256(
            canonical_json_bytes({"tools": tools})
        ).hexdigest()
        if (
            artifact.get("schema_version") != MCP_USER_CONTRACT_SCHEMA
            or artifact.get("profile") != "user"
            or not isinstance(artifact.get("contract_id"), str)
            or not isinstance(artifact.get("server_name"), str)
            or artifact.get("contract_sha256") != observed_contract
            or artifact.get("wire_sha256") != observed_wire
        ):
            raise ContractGenerationError(
                f"historical MCP user contract is invalid: {path}"
            )
        historical.append((path, payload, artifact))
    index: JSON = {
        "schema_version": MCP_USER_CONTRACT_INDEX_SCHEMA,
        "contracts": [
            {
                "artifact": spec.artifact_name,
                "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                "contract_id": spec.contract_id,
                "contract_sha256": artifact["contract_sha256"],
                "profile": "user",
                "server_name": spec.server_name,
                "wire_sha256": artifact["wire_sha256"],
            }
            for spec, artifact, payload in zip(
                USER_CONTRACT_SPECS,
                artifacts,
                artifact_payloads,
                strict=True,
            )
        ]
        + [
            {
                "artifact": path.name,
                "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                "contract_id": artifact["contract_id"],
                "contract_sha256": artifact["contract_sha256"],
                "profile": "user",
                "server_name": artifact["server_name"],
                "wire_sha256": artifact["wire_sha256"],
            }
            for path, payload, artifact in historical
        ],
    }
    expected = {
        output_directory / spec.artifact_name: payload
        for spec, payload in zip(USER_CONTRACT_SPECS, artifact_payloads, strict=True)
    }
    expected.update({path: payload for path, payload, _artifact in historical})
    expected[output_directory / "index.json"] = _formatted_json_bytes(index)
    for path, payload in expected.items():
        if check:
            try:
                observed = path.read_bytes()
            except OSError as exc:
                raise ContractGenerationError(
                    f"missing committed MCP user contract: {path}"
                ) from exc
            if observed != payload:
                raise ContractGenerationError(
                    f"committed MCP user contract is stale: {path}"
                )
        else:
            _write_atomic(path, payload)
    if output_directory.exists():
        stale = sorted(
            path.name
            for path in output_directory.glob("*.json")
            if path not in expected
        )
        if stale:
            raise ContractGenerationError(
                f"unexpected stale MCP user contract artifacts: {stale!r}"
            )
    return artifacts


def load_mcp_user_contract_index() -> JSON:
    """Load and validate the contract index shipped in the root wheel."""
    path = _contract_data_directory() / "index.json"
    index = _load_bounded_json_object(path)
    if index.get("schema_version") != MCP_USER_CONTRACT_INDEX_SCHEMA:
        raise ValueError(f"unsupported MCP user contract index: {path}")
    contracts = index.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        raise ValueError(f"MCP user contract index has no entries: {path}")
    seen: set[str] = set()
    for entry in contracts:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid MCP user contract index entry: {path}")
        contract_id = entry.get("contract_id")
        artifact_name = entry.get("artifact")
        if (
            not isinstance(contract_id, str)
            or not contract_id
            or contract_id in seen
            or not isinstance(artifact_name, str)
            or Path(artifact_name).name != artifact_name
            or not artifact_name.endswith(".json")
            or not _is_sha256(entry.get("artifact_sha256"))
            or not _is_sha256(entry.get("contract_sha256"))
            or not _is_sha256(entry.get("wire_sha256"))
            or entry.get("profile") != "user"
            or not isinstance(entry.get("server_name"), str)
        ):
            raise ValueError(f"invalid MCP user contract index entry: {path}")
        seen.add(contract_id)
    return index


def load_mcp_user_contract(contract_id: str) -> JSON:
    """Load one shipped contract by exact identifier and verify its digest."""
    index = load_mcp_user_contract_index()
    entries = cast(list[object], index["contracts"])
    matching = [
        cast(JSON, entry)
        for entry in entries
        if isinstance(entry, dict) and entry.get("contract_id") == contract_id
    ]
    if len(matching) != 1:
        raise ValueError(f"unknown MCP user contract: {contract_id}")
    entry = matching[0]
    artifact_name = entry.get("artifact")
    if (
        not isinstance(artifact_name, str)
        or Path(artifact_name).name != artifact_name
        or not artifact_name.endswith(".json")
    ):
        raise ValueError(f"invalid MCP user contract artifact: {artifact_name!r}")
    artifact_path = _contract_data_directory() / artifact_name
    artifact_payload, artifact = _load_bounded_json_document(artifact_path)
    if (
        entry.get("artifact_sha256") != hashlib.sha256(artifact_payload).hexdigest()
        or artifact.get("canonicalization") != MCP_USER_CONTRACT_CANONICALIZATION
        or artifact.get("projection") != MCP_USER_CONTRACT_PROJECTION
        or artifact.get("schema_version") != MCP_USER_CONTRACT_SCHEMA
        or artifact.get("contract_id") != contract_id
        or artifact.get("server_name") != entry.get("server_name")
        or artifact.get("profile") != entry.get("profile")
    ):
        raise ValueError(f"invalid MCP user contract identity: {contract_id}")
    raw_tools = artifact.get("tools")
    if not isinstance(raw_tools, list) or not all(
        isinstance(tool, dict) for tool in raw_tools
    ):
        raise ValueError(f"invalid MCP user contract tools: {contract_id}")
    tools = [cast(JSON, tool) for tool in raw_tools]
    observed_digest = mcp_user_contract_digest(tools)
    observed_wire_digest = hashlib.sha256(
        canonical_json_bytes({"tools": tools})
    ).hexdigest()
    tool_names = [cast(str, tool.get("name")) for tool in tools]
    if (
        artifact.get("contract_sha256") != observed_digest
        or entry.get("contract_sha256") != observed_digest
        or artifact.get("wire_sha256") != observed_wire_digest
        or entry.get("wire_sha256") != observed_wire_digest
        or artifact.get("tool_names") != tool_names
    ):
        raise ValueError(f"MCP user contract digest mismatch: {contract_id}")
    return artifact


def _validate_required_surface(spec: UserContractSpec, tools: Sequence[JSON]) -> None:
    names = {cast(str, tool["name"]) for tool in tools}
    if names != spec.expected_tools:
        raise ContractGenerationError(
            f"{spec.contract_id} tool names changed: expected "
            f"{sorted(spec.expected_tools)!r}, got {sorted(names)!r}"
        )
    by_name = {cast(str, tool["name"]): tool for tool in tools}
    if spec.server_name == "spack":
        locate_output = by_name["spack_locate"].get("outputSchema")
        if not isinstance(locate_output, dict):
            raise ContractGenerationError("spack_locate must publish outputSchema")
        properties = locate_output.get("properties")
        required = locate_output.get("required")
        if (
            not isinstance(properties, dict)
            or properties.get("load_spec") != {"type": "string"}
            or not isinstance(required, list)
            or "load_spec" not in required
        ):
            raise ContractGenerationError(
                "spack_locate must require the canonical load_spec result"
            )
    if spec.server_name == "jarvis":
        edit_input = by_name["jarvis_edit_step"].get("inputSchema")
        properties = (
            edit_input.get("properties") if isinstance(edit_input, dict) else None
        )
        operation = (
            properties.get("operation") if isinstance(properties, dict) else None
        )
        if not isinstance(operation, dict) or operation.get("enum") != [
            "edit",
            "remove",
        ]:
            raise ContractGenerationError(
                "jarvis_edit_step must combine edit and remove operations"
            )


def _formatted_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractGenerationError("MCP contract contains non-JSON data") from exc


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _contract_data_directory() -> Path:
    return Path(__file__).resolve().with_name("_mcp_contracts")


def _load_bounded_json_object(path: Path) -> JSON:
    _, decoded = _load_bounded_json_document(path)
    return decoded


def _load_bounded_json_document(path: Path) -> tuple[bytes, JSON]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"could not read MCP user contract: {path}") from exc
    if len(payload) > MAX_CONTRACT_BYTES:
        raise ValueError(f"MCP user contract exceeds size limit: {path}")
    try:
        decoded = json.loads(
            payload.decode("utf-8", errors="strict"),
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid MCP user contract JSON: {path}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"MCP user contract must be an object: {path}")
    return payload, cast(JSON, decoded)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")
