import argparse
import os
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, cast

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import Field, ValidationError

from .capabilities.jarvis_handler import (
    create_pipeline,
    load_pipeline,
    export_pipeline,
    append_pkg,
    configure_pkg,
    unlink_pkg,
    remove_pkg,
    run_pipeline,
    get_execution,
    destroy_pipeline,
    get_pkg_config,
    update_pipeline,
    build_pipeline_env,
)
from .models.compat import _CurrentJarvisManager, _load_jarvis_manager_class
from .models.describe import JarvisDescribeResult
from .models.execution import (
    ExecutionIntent,
    JarvisExecutionResult,
    JarvisRunResult,
    _detect_scheduler_name,
    _execution_intent_to_pipeline_config,
    _validated_execution_intent,
)
from .models.artifact_documents import ExecutionArtifactQuery
from .models.progress import (
    JarvisPackageProgressDocument,
    JarvisProgressEventDocument,
    JarvisProgressSnapshotDocument,
)
from .models.service_runtime import JarvisServiceRuntimeSnapshotDocument
from .package_discovery import (
    PACKAGE_SEARCH_DEFAULT_PAGE_SIZE,
    PACKAGE_SEARCH_MAX_CURSOR_LENGTH,
    PACKAGE_SEARCH_MAX_PAGE_SIZE,
    PACKAGE_SEARCH_MAX_RESULT_BYTES,
    _PackageAgentMetadata,
    _discover_packages,
    _find_package_description,
    _first_docstring_or_comment,
    _package_agent_metadata,
    _package_configuration_search_text,
    _package_from_pkg_file,
    _search_packages,
    _setting_from_menu_item,
    _step_snapshot,
)

# Re-exported so ``jarvis_mcp.server.X`` keeps working for external callers and
# this package's own test suite after the models/package_discovery owner-module
# split (clio-kit campaign #362, Slice 1) -- these names are not otherwise
# referenced below, but dropping the import would silently break every
# ``from jarvis_mcp.server import X`` / ``patch("jarvis_mcp.server.X")`` site
# that predates the split.
__all__ = [
    "main",
    "admin_main",
    "mcp",
    "ExecutionArtifactQuery",
    "ExecutionIntent",
    "JarvisExecutionResult",
    "JarvisPackageProgressDocument",
    "JarvisProgressEventDocument",
    "JarvisProgressSnapshotDocument",
    "JarvisRunResult",
    "JarvisServiceRuntimeSnapshotDocument",
    "PACKAGE_SEARCH_MAX_RESULT_BYTES",
    "_CurrentJarvisManager",
    "_PackageAgentMetadata",
    "_detect_scheduler_name",
    "_execution_intent_to_pipeline_config",
    "_find_package_description",
    "_first_docstring_or_comment",
    "_package_agent_metadata",
    "_package_configuration_search_text",
    "_package_from_pkg_file",
    "_setting_from_menu_item",
    "_step_snapshot",
]


# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "jarvis",
    instructions=(
        "Manages JARVIS data pipelines for scientific computing. "
        "Create, configure, monitor, and manage data processing pipelines."
    ),
    list_page_size=10,
)
MCP_METADATA_PROFILE = "user"


# Resolve the JARVIS manager lazily so MCP metadata discovery does not require a
# functional JARVIS-CD installation. Admin tools still fail clearly at call time
# if the installed JARVIS version lacks the needed manager API.
JarvisManager = _load_jarvis_manager_class()
manager: Any | None = None
_manager: Any | None = None


def get_manager() -> Any:
    """Return the process-local JARVIS manager singleton."""
    global _manager
    if manager is not None:
        return manager
    if _manager is None:
        _manager = JarvisManager.get_instance()
    return _manager


USER_TOOLS = {
    "jarvis_create_pipeline",
    "jarvis_describe",
    "jarvis_add_step",
    "jarvis_edit_step",
    "jarvis_run",
    "jarvis_get_execution",
}

ADMIN_TOOLS = {
    "update_pipeline",
    "build_pipeline_env",
    "create_pipeline",
    "load_pipeline",
    "export_pipeline",
    "get_pkg_config",
    "append_pkg",
    "configure_pkg",
    "unlink_pkg",
    "remove_pkg",
    "run_pipeline",
    "jm_list_pipelines",
    "jm_list_repos",
    "jm_get_repo",
    "jm_create_config",
    "jm_load_config",
    "jm_save_config",
    "jm_set_hostfile",
    "jm_bootstrap_from",
    "jm_bootstrap_list",
    "jm_reset",
    "jm_cd",
    "jm_add_repo",
    "jm_remove_repo",
    "jm_promote_repo",
    "jm_construct_pkg",
    "jm_graph_show",
    "jm_graph_build",
    "jm_graph_modify",
    "destroy_pipeline",
}


# ─── RESOURCE ────────────────────────────────────────────────────────────────


@mcp.resource("jarvis://capabilities")
def jarvis_capabilities() -> dict:
    """JARVIS data pipeline capabilities."""
    return {
        "pipeline_types": ["streaming", "batch", "real-time"],
        "operations": ["create", "configure", "deploy", "monitor", "destroy"],
    }


# ─── PROMPT ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def create_pipeline_workflow(name: str) -> list[Message]:
    """Guided workflow for creating and deploying a JARVIS pipeline."""
    return [
        Message(
            f"I need to create a new JARVIS pipeline called '{name}'. "
            "Help me configure it, set up the processing stages, deploy it, "
            "and verify it's running correctly."
        ),
    ]


# ─── PIPELINE TOOLS ─────────────────────────────────────────────────────────────


@mcp.tool(
    name="update_pipeline",
    title="Reapply Pipeline",
    description="Re-apply environment and configuration to every package in a pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def update_pipeline_tool(pipeline_id: str) -> dict:
    """Re-apply environment and configuration to every package in a Jarvis pipeline."""
    return await update_pipeline(pipeline_id)


@mcp.tool(
    name="build_pipeline_env",
    title="Build Environment",
    description="Rebuild a pipeline's env.yaml, capturing CMAKE_PREFIX_PATH and PATH.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def build_pipeline_env_tool(pipeline_id: str) -> dict:
    """Build the pipeline execution environment for a given pipeline."""
    return await build_pipeline_env(pipeline_id)


@mcp.tool(
    name="create_pipeline",
    title="Create Pipeline",
    description="Create a new Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def create_pipeline_tool(pipeline_id: str) -> dict:
    """Create a new pipeline environment for data-centric workflows."""
    return await create_pipeline(pipeline_id)


@mcp.tool(
    name="load_pipeline",
    title="Load Pipeline",
    description="Load an existing Jarvis-CD pipeline environment.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def load_pipeline_tool(pipeline_id: Optional[str] = None) -> dict:
    """Load an existing pipeline environment by ID, or the current one if not specified."""
    return await load_pipeline(pipeline_id)


@mcp.tool(
    name="export_pipeline",
    title="Export Pipeline",
    description="Export a structured snapshot of a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def export_pipeline_tool(pipeline_id: str, include_yaml: bool = True) -> dict:
    """Export pipeline metadata, packages, configs, and optional source YAML."""
    return await export_pipeline(pipeline_id, include_yaml=include_yaml)


@mcp.tool(
    name="get_pkg_config",
    title="Get Package Config",
    description="Retrieve the configuration of a specific package in a pipeline.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def get_pkg_config_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Retrieve the configuration of a specific package in a pipeline."""
    return await get_pkg_config(pipeline_id, pkg_id)


@mcp.tool(
    name="append_pkg",
    title="Append Package",
    description="Append a package to a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def append_pkg_tool(
    pipeline_id: str,
    pkg_type: str,
    pkg_id: Optional[str] = None,
    do_configure: bool = True,
    extra_args: Optional[dict] = None,
) -> dict:
    """Add a package to a pipeline for execution or analysis."""
    return await append_pkg(
        pipeline_id,
        pkg_type,
        pkg_id=pkg_id,
        do_configure=do_configure,
        **(extra_args or {}),
    )


@mcp.tool(
    name="configure_pkg",
    title="Configure Package",
    description="Configure a package in a Jarvis-CD pipeline.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def configure_pkg_tool(
    pipeline_id: str, pkg_id: str, extra_args: Optional[dict] = None
) -> dict:
    """Configure a package in a pipeline with new settings."""
    return await configure_pkg(pipeline_id, pkg_id, **(extra_args or {}))


@mcp.tool(
    name="unlink_pkg",
    title="Unlink Package",
    description="Unlink a package from a pipeline (preserve files).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def unlink_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Unlink a package from a pipeline without deleting its files."""
    return await unlink_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="remove_pkg",
    title="Remove Package",
    description=(
        "Delete a package through JARVIS-CD's destructive removal API. Fails "
        "explicitly when the installed JARVIS-CD only supports non-destructive unlinking."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def remove_pkg_tool(pipeline_id: str, pkg_id: str) -> dict:
    """Delete a package only when JARVIS-CD provides destructive removal semantics."""
    return await remove_pkg(pipeline_id, pkg_id)


@mcp.tool(
    name="run_pipeline",
    title="Run Pipeline",
    description="Execute a Jarvis-CD pipeline end-to-end.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
async def run_pipeline_tool(pipeline_id: str) -> dict:
    """Execute the pipeline, running all configured steps."""
    return await run_pipeline(pipeline_id)


@mcp.tool(
    name="jarvis_create_pipeline",
    title="Create Jarvis Run",
    description=(
        "Create a JARVIS pipeline. Optionally pass execution intent such as "
        "local, cluster, or hostfile mode; backend details are resolved where "
        "the MCP server runs."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_create_pipeline_tool(
    pipeline_id: str, execution: ExecutionIntent | None = None
) -> dict:
    """Create a new JARVIS pipeline, optionally seeding execution intent."""
    initial_config = (
        _execution_intent_to_pipeline_config(execution)
        if execution is not None
        else None
    )
    return await create_pipeline(pipeline_id, initial_config=initial_config)


@mcp.tool(
    name="jarvis_describe",
    title="Describe",
    description=(
        "Describe JARVIS packages, one package, a pipeline, or one pipeline step. "
        "For a named application, first use target='package' with its unique short name "
        "or fully qualified package name. Use target='package_search' for bounded "
        "discovery, then describe the selected canonical name. A package description "
        "returns package-owned configuration metadata and, when supported, a versioned "
        "deployment contract covering execution profiles, runtime requirements, "
        "readiness, and configuration rules. Package settings include only semantic "
        "parameters explicitly marked agent-visible. A setting may include a versioned "
        "input_binding descriptor for a declared local input that must be staged; "
        "callers must not infer file semantics from setting names or prose. Installer, "
        "scheduler, and other implementation controls remain owned by their dedicated "
        "contracts. "
        "target='packages' is an exhaustive legacy inventory with every agent-visible "
        "package setting and can be large; use it only when the complete installed "
        "catalog is explicitly required."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_describe_tool(
    target: Annotated[
        Literal["packages", "package_search", "package", "pipeline", "step"],
        Field(
            description=(
                "Object to describe. Prefer package for a named application and "
                "package_search for discovery; packages is exhaustive and unbounded."
            )
        ),
    ],
    pipeline_id: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description="Pipeline identifier for target='pipeline' or target='step'.",
        ),
    ] = None,
    step_id: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description="Pipeline step identifier for target='step'.",
        ),
    ] = None,
    package_name: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=512,
            description=(
                "Case-insensitive unique short name or fully qualified package name for "
                "target='package'. Ambiguous short names fail with canonical candidates."
            ),
        ),
    ] = None,
    query: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=256,
            description=(
                "Natural-language or package-name query required for "
                "target='package_search'."
            ),
        ),
    ] = None,
    page_size: Annotated[
        int,
        Field(
            ge=1,
            le=PACKAGE_SEARCH_MAX_PAGE_SIZE,
            description=(
                "Maximum summary matches returned by target='package_search'; "
                f"bounded to {PACKAGE_SEARCH_MAX_PAGE_SIZE}."
            ),
        ),
    ] = PACKAGE_SEARCH_DEFAULT_PAGE_SIZE,
    cursor: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=PACKAGE_SEARCH_MAX_CURSOR_LENGTH,
            description=(
                "Opaque next-page cursor returned by an earlier package_search with "
                "the identical query."
            ),
        ),
    ] = None,
    include_yaml: Annotated[
        bool,
        Field(
            description=(
                "Include stored pipeline YAML only for target='pipeline'; ignored for "
                "package and package discovery targets."
            )
        ),
    ] = True,
) -> JarvisDescribeResult:
    """Describe user-level JARVIS objects without exposing repository administration."""
    normalized = target.strip().lower()
    if normalized == "packages":
        return cast(
            JarvisDescribeResult,
            {"target": "packages", "packages": _discover_packages()},
        )
    if normalized == "package_search":
        if query is None or not query.strip():
            raise ToolError("query is required when target='package_search'")
        return cast(
            JarvisDescribeResult,
            _search_packages(query=query, page_size=page_size, cursor=cursor),
        )
    if normalized == "package":
        if not package_name:
            raise ToolError("package_name is required when target='package'")
        package = _find_package_description(package_name)
        if package is None:
            raise ToolError(f"package not found: {package_name}")
        return cast(
            JarvisDescribeResult,
            {"target": "package", "package": package},
        )
    if normalized == "pipeline":
        if not pipeline_id:
            raise ToolError("pipeline_id is required when target='pipeline'")
        snapshot = await export_pipeline(pipeline_id, include_yaml=include_yaml)
        return cast(
            JarvisDescribeResult,
            {"target": "pipeline", "pipeline": snapshot},
        )
    if normalized == "step":
        if not pipeline_id or not step_id:
            raise ToolError("pipeline_id and step_id are required when target='step'")
        snapshot = await export_pipeline(pipeline_id, include_yaml=False)
        step = _step_snapshot(snapshot, step_id)
        if step is None:
            raise ToolError(f"step not found in pipeline {pipeline_id}: {step_id}")
        config = await get_pkg_config(pipeline_id, step_id)
        return cast(
            JarvisDescribeResult,
            {"target": "step", "step": step, "config": config},
        )
    raise ToolError(
        "target must be one of: packages, package_search, package, pipeline, step"
    )


@mcp.tool(
    name="jarvis_add_step",
    title="Add Step",
    description=(
        "Add and configure a package-backed step in a JARVIS pipeline. First use "
        "jarvis_describe(target='package') for the selected package; config keys "
        "must use its canonical setting names exactly, except for aliases explicitly "
        "listed there. Explicit null is accepted only when that setting reports "
        "nullable=true; omit a setting to use its declared default. Only settings marked "
        "agent-visible by the package are accepted here. User-level step configuration "
        "is always validated and cannot be bypassed."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_add_step_tool(
    pipeline_id: str,
    package_name: str,
    step_id: Optional[str] = None,
    config: Annotated[
        Optional[dict[str, Any]],
        Field(
            description=(
                "Package-owned configuration. Use canonical setting names exactly as "
                "returned by jarvis_describe(target='package'); only aliases listed "
                "there are also accepted, and settings must not be renamed or placed "
                "under invented nesting. JSON documents may be passed directly as "
                "objects or lists under their exact setting name; clio-kit serializes "
                "them canonically before JARVIS package validation. Explicit null is "
                "accepted only for a setting that reports nullable=true. Omit config or "
                "an individual setting to use the package-owned default."
            )
        ),
    ] = None,
) -> dict:
    """Add and configure one package step without a user-level validation bypass."""
    return await append_pkg(
        pipeline_id,
        package_name,
        pkg_id=step_id,
        do_configure=True,
        agent_visible_only=True,
        **(config or {}),
    )


@mcp.tool(
    name="jarvis_edit_step",
    title="Edit Step",
    description=(
        "Edit or remove a step in a JARVIS pipeline. Use operation='edit' with "
        "config, or operation='remove' without config."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_edit_step_tool(
    pipeline_id: str,
    step_id: str,
    config: Optional[dict[str, Any]] = None,
    operation: Literal["edit", "remove"] = "edit",
) -> dict:
    """Edit or remove one pipeline step with explicit conditional arguments."""
    if operation == "edit":
        if config is None:
            raise ToolError("config is required when operation='edit'")
        return await configure_pkg(
            pipeline_id,
            step_id,
            agent_visible_only=True,
            **config,
        )
    if config not in (None, {}):
        raise ToolError("config is not accepted when operation='remove'")
    return await unlink_pkg(pipeline_id, step_id)


@mcp.tool(
    name="jarvis_run",
    title="Start Execution",
    description=(
        "Start a configured JARVIS pipeline and return its durable execution "
        "handle without waiting for workload completion. Optional execution intent "
        "selects local, cluster, or hostfile mode without exposing scheduler "
        "internals. For each runtime resolved with Spack, copy "
        "spack_locate.output.load_spec unchanged into one element of "
        "jarvis_run.input.spack_specs; do not derive an executable path from the Spack "
        "prefix. JARVIS resolves those specs into a filtered environment and persists "
        "it before direct or scheduler execution. Use "
        "jarvis_get_execution with the returned pipeline_id and execution_id to "
        "query lifecycle, progress, artifacts, and execution-owned service runtimes."
    ),
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline", "user"},
)
async def jarvis_run_tool(
    pipeline_id: str,
    execution: ExecutionIntent | None = None,
    submit: bool = True,
    execution_id: str | None = None,
    spack_specs: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Runtime identities supplied by Spack. Copy each "
                "spack_locate.output.load_spec unchanged into this list; do not pass "
                "spack_locate.output.prefix or an inferred executable path. JARVIS "
                "persists the resolved environment for the execution."
            )
        ),
    ] = None,
    ctx: Context | None = None,
) -> JarvisRunResult:
    """Start a pipeline without waiting after persisting its Spack environment."""
    mode = "auto"
    if execution is not None:
        intent = _validated_execution_intent(execution)
        requested_mode = intent.mode
        mode = {
            "cluster": "scheduler",
            "local": "direct",
            "hostfile": "direct",
        }.get(requested_mode, requested_mode)
        run_arguments_config = _execution_intent_to_pipeline_config(intent)
    else:
        run_arguments_config = None

    async def report_progress(
        current: float,
        total: float | None,
        message: str,
    ) -> None:
        if ctx is not None:
            await ctx.report_progress(current, total, message)

    run_arguments: dict[str, Any] = {
        "mode": mode,
        "submit": submit,
        "wait": False,
        "execution_id": execution_id,
        "spack_specs": spack_specs,
        "pipeline_config": run_arguments_config,
    }
    if _context_has_progress_token(ctx):
        run_arguments["progress_reporter"] = report_progress
    return cast(JarvisRunResult, await run_pipeline(pipeline_id, **run_arguments))


@mcp.tool(
    name="jarvis_get_execution",
    title="Get Execution",
    description=(
        "Query one JARVIS execution handle, durable lifecycle record, and "
        "runtime metadata. Progress is included by default and can be omitted. "
        "Set include_service_runtimes=true to include execution-owned network "
        "services; authenticated services expose only a non-secret bearer token "
        "SHA-256 fingerprint. "
        "Set artifacts to {} or filters to include one bounded artifact page; "
        "omit artifacts to avoid querying the artifact manifest."
    ),
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline", "execution", "user"},
)
async def jarvis_get_execution_tool(
    pipeline_id: str,
    execution_id: str,
    include_progress: bool = True,
    include_service_runtimes: bool = False,
    artifacts: ExecutionArtifactQuery | None = None,
) -> JarvisExecutionResult:
    """Query a selectable JARVIS-owned execution view in one locked load."""
    document = await get_execution(
        pipeline_id,
        execution_id,
        include_progress=include_progress,
        include_service_runtimes=include_service_runtimes,
        artifacts=artifacts.model_dump() if artifacts is not None else None,
    )
    try:
        return JarvisExecutionResult.model_validate(document)
    except ValidationError:
        raise ToolError(
            "JARVIS execution result failed closed output validation"
        ) from None


def _context_has_progress_token(ctx: Context | None) -> bool:
    """Return whether this MCP request explicitly negotiated live progress."""
    if ctx is None:
        return False
    request_context = ctx.request_context
    return (
        request_context is not None
        and request_context.meta is not None
        and request_context.meta.get("progressToken") is not None
    )


@mcp.tool(
    name="destroy_pipeline",
    title="Destroy Pipeline",
    description="Destroy a pipeline environment and clean up files.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "pipeline"},
)
async def destroy_pipeline_tool(pipeline_id: str) -> dict:
    """Destroy a pipeline and clean up all associated files and resources."""
    return await destroy_pipeline(pipeline_id)


@mcp.tool(
    name="jm_create_config",
    title="Initialize Config",
    description="Initialize JarvisManager config directories.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_create_config(
    config_dir: str, private_dir: str, shared_dir: Optional[str] = None
) -> list:
    """Initialize manager directories and persist configuration."""
    try:
        with _protocol_stdout_to_stderr():
            manager = get_manager()
            manager.create(config_dir, private_dir, shared_dir)
            manager.save()
        return [{"type": "text", "text": "Jarvis configuration initialized."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_load_config",
    title="Load Config",
    description="Load existing JarvisManager configuration.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_load_config() -> list:
    """Load manager configuration from saved state."""
    try:
        manager = get_manager()
        manager.load()
        return [{"type": "text", "text": "Configuration loaded."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_save_config",
    title="Save Config",
    description="Save current JarvisManager configuration.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_save_config() -> list:
    """Save current configuration state to disk."""
    try:
        manager = get_manager()
        manager.save()
        return [{"type": "text", "text": "Configuration saved."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_set_hostfile",
    title="Set Hostfile",
    description="Set hostfile path for JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_set_hostfile(path: str) -> list:
    """Set and save the path to the hostfile for deployments."""
    try:
        manager = get_manager()
        manager.set_hostfile(path)
        manager.save()
        return [{"type": "text", "text": f"Hostfile set to '{path}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_from",
    title="Bootstrap Machine",
    description="Bootstrap Jarvis config from a machine template.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_from(machine: str) -> list:
    """Bootstrap configuration based on a predefined machine template."""
    try:
        manager = get_manager()
        manager.bootstrap_from(machine)
        return [{"type": "text", "text": f"Bootstrapped from '{machine}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_bootstrap_list",
    title="List Templates",
    description="List available bootstrap machine templates.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_bootstrap_list() -> list:
    """List all bootstrap templates available."""
    try:
        manager = get_manager()
        return [{"type": "text", "text": m} for m in manager.bootstrap_list()]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_reset",
    title="Reset Manager",
    description="Reset JarvisManager (destroy all pipelines and data).",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_reset() -> list:
    """Reset manager to a clean state by destroying all pipelines and config."""
    try:
        manager = get_manager()
        manager.reset()
        return [{"type": "text", "text": "All pipelines and data reset."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_pipelines",
    title="List Pipelines",
    description="List all existing Jarvis pipelines.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_list_pipelines() -> dict[str, Any]:
    """List all current pipelines under management."""
    try:
        manager = get_manager()
        pipelines = [str(pipeline) for pipeline in manager.list_pipelines()]
        return {"pipelines": pipelines, "count": len(pipelines)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_cd",
    title="Switch Pipeline",
    description="Change current Jarvis pipeline context.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_cd(pipeline_id: str) -> list:
    """Set the working pipeline context."""
    try:
        manager = get_manager()
        manager.cd(pipeline_id)
        manager.save()
        return [{"type": "text", "text": f"Current pipeline set to '{pipeline_id}'"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_list_repos",
    title="List Repos",
    description="List all Jarvis repositories.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_list_repos() -> dict[str, Any]:
    """List all registered repositories."""
    try:
        manager = get_manager()
        repos = [str(repo) for repo in manager.list_repos()]
        return {"repos": repos, "count": len(repos)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_add_repo",
    title="Add Repo",
    description="Add a repository to JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "management"},
)
def jm_add_repo(path: str, force: bool = False) -> list:
    """Add a repository path to the manager."""
    try:
        manager = get_manager()
        manager.add_repo(path, force)
        manager.save()
        return [{"type": "text", "text": f"Repo added: {path}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_remove_repo",
    title="Remove Repo",
    description="Remove a repository from JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_remove_repo(repo_name: str) -> list:
    """Remove a repository from configuration."""
    try:
        manager = get_manager()
        manager.remove_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo removed: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_promote_repo",
    title="Promote Repo",
    description="Promote a repository in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "management"},
)
def jm_promote_repo(repo_name: str) -> list:
    """Promote a repository to higher priority."""
    try:
        manager = get_manager()
        manager.promote_repo(repo_name)
        manager.save()
        return [{"type": "text", "text": f"Repo promoted: {repo_name}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_get_repo",
    title="Get Repo",
    description="Get repository info from JarvisManager.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
async def jm_get_repo(repo_name: str) -> dict[str, Any]:
    """Get detailed information about a repository."""
    try:
        manager = get_manager()
        repo = manager.get_repo(repo_name)
        return {"repo": repo if isinstance(repo, dict) else str(repo)}
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_construct_pkg",
    title="Construct Package",
    description="Construct a package skeleton in JarvisManager.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_construct_pkg(pkg_type: str) -> list:
    """Generate a new package skeleton by type."""
    try:
        manager = get_manager()
        obj = manager.construct_pkg(pkg_type)
        return [{"type": "text", "text": f"Constructed pkg: {obj.__class__.__name__}"}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_show",
    title="Show Graph",
    description="Print the current resource graph frames.",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    tags={"jarvis", "monitoring"},
)
def jm_graph_show() -> list:
    """Print the resource graph to the console."""
    try:
        manager = get_manager()
        manager.resource_graph_show()
        return [{"type": "text", "text": "Resource graph printed to console."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_build",
    title="Build Graph",
    description="Build or rebuild the resource graph with a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_build(net_sleep: float) -> list:
    """Construct or rebuild the graph with a given sleep delay."""
    try:
        manager = get_manager()
        manager.resource_graph_build(net_sleep)
        return [{"type": "text", "text": "Resource graph built."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


@mcp.tool(
    name="jm_graph_modify",
    title="Modify Graph",
    description="Modify the resource graph using a net sleep interval.",
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    tags={"jarvis", "pipeline"},
)
def jm_graph_modify(net_sleep: float) -> list:
    """Modify the current resource graph with a delay between operations."""
    try:
        manager = get_manager()
        manager.resource_graph_modify(net_sleep)
        return [{"type": "text", "text": "Resource graph modified."}]
    except Exception as e:
        raise ToolError(f"Error: {e}")


def _protocol_stdout_to_stderr() -> Any:
    from contextlib import redirect_stdout
    import sys

    return redirect_stdout(sys.stderr)


def add_spack_command_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared validated Spack executable option to a CLI parser."""
    parser.add_argument(
        "--spack-command",
        type=_spack_command_path,
        default=None,
        help="Absolute or user-relative path to the audited Spack executable.",
    )


def add_jarvis_root_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared validated JARVIS root option to a CLI parser."""
    parser.add_argument(
        "--jarvis-root",
        type=_existing_directory_path,
        default=None,
        help="Existing directory to use as the isolated JARVIS_ROOT.",
    )


def configure_jarvis_root(jarvis_root: str | None) -> None:
    """Apply an explicitly validated JARVIS root before serving requests."""
    if jarvis_root is not None:
        os.environ["JARVIS_ROOT"] = jarvis_root


def configure_spack_command(spack_command: str | None) -> None:
    """Apply an explicitly validated Spack command for later JARVIS runs."""
    if spack_command is not None:
        os.environ["JARVIS_MCP_SPACK_COMMAND"] = spack_command


def _spack_command_path(value: str) -> str:
    """Resolve and validate an operator-supplied Spack executable path."""
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise argparse.ArgumentTypeError(
            f"Spack command does not exist: {candidate}"
        ) from exc
    if not resolved.is_file():
        raise argparse.ArgumentTypeError(f"Spack command is not a file: {resolved}")
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(f"Spack command is not executable: {resolved}")
    return str(resolved)


def _existing_directory_path(value: str) -> str:
    """Resolve and validate an operator-supplied existing directory."""
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise argparse.ArgumentTypeError(
            f"JARVIS root does not exist: {candidate}"
        ) from exc
    if not resolved.is_dir():
        raise argparse.ArgumentTypeError(f"JARVIS root is not a directory: {resolved}")
    return str(resolved)


def main() -> None:
    """Main entry point for the Jarvis MCP server."""
    parser = argparse.ArgumentParser(description="Jarvis MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument(
        "--profile",
        choices=["all", "user", "admin"],
        default=None,
        help=(
            "Tool surface to expose. 'user' exposes pipeline authoring and read-only "
            "discovery tools. 'admin' exposes manager and destructive operations. "
            "'all' preserves the full legacy surface."
        ),
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    add_jarvis_root_argument(parser)
    add_spack_command_argument(parser)
    args = parser.parse_args()
    configure_jarvis_root(args.jarvis_root)
    configure_spack_command(args.spack_command)
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    profile = args.profile or os.getenv("JARVIS_MCP_PROFILE", "user")
    apply_tool_profile(profile)
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


def admin_main() -> None:
    """Main entry point for the Jarvis admin MCP server."""
    os.environ.setdefault("JARVIS_MCP_PROFILE", "admin")
    main()


def apply_tool_profile(profile: str) -> None:
    """Restrict the registered tool set for user or admin MCP modes."""
    normalized = profile.strip().lower()
    if normalized == "all":
        return
    if normalized == "user":
        allowed = USER_TOOLS
    elif normalized == "admin":
        allowed = ADMIN_TOOLS
    else:
        raise ValueError("profile must be one of: all, user, admin")
    for tool in _registered_tools():
        if tool.name not in allowed:
            mcp.local_provider.remove_tool(tool.name)


def _registered_tools() -> list:
    components = getattr(mcp.local_provider, "_components", {})
    return [
        component
        for key, component in components.items()
        if isinstance(key, str) and key.startswith("tool:")
    ]


if __name__ == "__main__":
    main()
