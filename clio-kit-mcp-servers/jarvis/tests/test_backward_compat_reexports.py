"""Every name previously importable from ``jarvis_mcp.server`` still is.

PR #364 review finding 3: the server.py owner-module split (clio-kit
campaign #362, Slice 1) silently narrowed the module's public surface --
``from jarvis_mcp.server import JarvisArtifactDocument`` used to work (the
class was defined directly in server.py) and started raising ImportError
once it moved to ``jarvis_mcp.models.artifact_documents`` without a
compatibility re-export.

``_PRESPLIT_TOP_LEVEL_NAMES`` is the COMPLETE, mechanically-extracted list of
every top-level name (class, function, constant, or plain import) the
pre-split ``server.py`` (commit ea232ac, the contract-pins commit
immediately before the split) defined at module scope -- captured via
``ast.parse`` over that commit's file content, not hand-transcribed. Every
one of those 190 names must still resolve as a ``jarvis_mcp.server``
attribute today, whether it still lives here or now lives in an owner
module and is re-exported.
"""

from __future__ import annotations

from jarvis_mcp import server

# Mechanically extracted (ast.parse over every top-level ClassDef/FunctionDef/
# Assign/AnnAssign/Import/ImportFrom binding) from
# clio-kit-mcp-servers/jarvis/src/jarvis_mcp/server.py at commit ea232ac --
# the full pre-split module surface. Do not hand-edit; regenerate the same
# way if server.py's pre-split ancestor is ever revisited.
_PRESPLIT_TOP_LEVEL_NAMES: tuple[str, ...] = (
    "ADMIN_TOOLS",
    "Annotated",
    "Any",
    "BaseModel",
    "CONFIGURATION_INPUT_BINDING_SCHEMA",
    "ConfigDict",
    "Context",
    "ExecutionArtifactQuery",
    "ExecutionIntent",
    "FastMCP",
    "Field",
    "JarvisArtifactDocument",
    "JarvisArtifactLocationDocument",
    "JarvisConfigurationInputBindingDocument",
    "JarvisDatasetArrayDocument",
    "JarvisDatasetDescriptorDocument",
    "JarvisDatasetFingerprintDocument",
    "JarvisDatasetMemberDocument",
    "JarvisDatasetSourceArtifactDocument",
    "JarvisDescribePackageResult",
    "JarvisDescribePackageSearchResult",
    "JarvisDescribePackagesResult",
    "JarvisDescribePipelineResult",
    "JarvisDescribeResult",
    "JarvisDescribeStepResult",
    "JarvisExecutionArtifactPageDocument",
    "JarvisExecutionHandleDocument",
    "JarvisExecutionRecordDocument",
    "JarvisExecutionResult",
    "JarvisManager",
    "JarvisPackageConditionDocument",
    "JarvisPackageConfigurationRuleDocument",
    "JarvisPackageDeploymentDocument",
    "JarvisPackageDescriptionDocument",
    "JarvisPackageExecutionProfileDocument",
    "JarvisPackageProgressDocument",
    "JarvisPackageReadinessDocument",
    "JarvisPackageSettingDocument",
    "JarvisPackageSummaryDocument",
    "JarvisProgressEventDocument",
    "JarvisProgressSnapshotDocument",
    "JarvisProviderQueryDocument",
    "JarvisProviderResolutionDocument",
    "JarvisRunResult",
    "JarvisRuntimeRequirementDocument",
    "JarvisRuntimeRequirementStatusDocument",
    "JarvisServiceAuthorizationDocument",
    "JarvisServiceRuntimeDocument",
    "JarvisServiceRuntimeSnapshotDocument",
    "JarvisServiceRuntimeV1Document",
    "JarvisServiceRuntimeV2Document",
    "Literal",
    "MCP_METADATA_PROFILE",
    "Mapping",
    "Message",
    "NotRequired",
    "Optional",
    "PACKAGE_DEPLOYMENT_SCHEMA",
    "PACKAGE_DESCRIPTION_SCHEMA",
    "PACKAGE_SEARCH_CURSOR_SCHEMA",
    "PACKAGE_SEARCH_DEFAULT_PAGE_SIZE",
    "PACKAGE_SEARCH_MAX_CURSOR_LENGTH",
    "PACKAGE_SEARCH_MAX_DESCRIPTION_BYTES",
    "PACKAGE_SEARCH_MAX_PAGE_SIZE",
    "PACKAGE_SEARCH_MAX_RESULT_BYTES",
    "PACKAGE_SEARCH_SCHEMA",
    "Path",
    "PurePosixPath",
    "ToolError",
    "TypedDict",
    "USER_TOOLS",
    "ValidationError",
    "_ClosedDocument",
    "_CurrentJarvisManager",
    "_EXECUTION_MODES",
    "_HOST_ENTRY",
    "_JarvisServiceRuntimeDocumentBase",
    "_PACKAGE_SEARCH_CURSOR_TEXT",
    "_PACKAGE_SEARCH_SHA256",
    "_PackageAgentMetadata",
    "_PackageInventoryEntry",
    "_SCHEDULER_EXECUTION_FIELDS",
    "_SCHEDULER_TOKEN",
    "_bounded_package_search_description",
    "_bounded_single_line",
    "_context_has_progress_token",
    "_decode_package_search_cursor",
    "_detect_scheduler_name",
    "_discover_package_inventory",
    "_discover_packages",
    "_encode_package_search_cursor",
    "_execution_intent_to_pipeline_config",
    "_existing_directory_path",
    "_find_package_description",
    "_first_docstring_or_comment",
    "_load_jarvis_manager_class",
    "_manager",
    "_package_agent_metadata",
    "_package_configuration_search_text",
    "_package_description_from_inventory",
    "_package_from_pkg_file",
    "_package_inventory_entry",
    "_package_inventory_revision",
    "_package_search_json_bytes",
    "_package_search_rank",
    "_package_search_terms",
    "_protocol_stdout_to_stderr",
    "_registered_tools",
    "_reject_package_search_duplicate_keys",
    "_search_packages",
    "_setting_accepts_null",
    "_setting_from_menu_item",
    "_setting_is_agent_visible",
    "_spack_command_path",
    "_step_snapshot",
    "_validated_execution_intent",
    "add_jarvis_root_argument",
    "add_spack_command_argument",
    "admin_main",
    "append_pkg",
    "append_pkg_tool",
    "apply_tool_profile",
    "argparse",
    "base64",
    "binascii",
    "build_pipeline_env",
    "build_pipeline_env_tool",
    "cast",
    "configure_jarvis_root",
    "configure_pkg",
    "configure_pkg_tool",
    "configure_spack_command",
    "create_pipeline",
    "create_pipeline_tool",
    "create_pipeline_workflow",
    "dataclass",
    "destroy_pipeline",
    "destroy_pipeline_tool",
    "export_pipeline",
    "export_pipeline_tool",
    "field_validator",
    "get_execution",
    "get_manager",
    "get_pkg_config",
    "get_pkg_config_tool",
    "hashlib",
    "importlib",
    "jarvis_add_step_tool",
    "jarvis_capabilities",
    "jarvis_create_pipeline_tool",
    "jarvis_describe_tool",
    "jarvis_edit_step_tool",
    "jarvis_get_execution_tool",
    "jarvis_run_tool",
    "jm_add_repo",
    "jm_bootstrap_from",
    "jm_bootstrap_list",
    "jm_cd",
    "jm_construct_pkg",
    "jm_create_config",
    "jm_get_repo",
    "jm_graph_build",
    "jm_graph_modify",
    "jm_graph_show",
    "jm_list_pipelines",
    "jm_list_repos",
    "jm_load_config",
    "jm_promote_repo",
    "jm_remove_repo",
    "jm_reset",
    "jm_save_config",
    "jm_set_hostfile",
    "json",
    "load_dotenv",
    "load_pipeline",
    "load_pipeline_tool",
    "main",
    "manager",
    "mcp",
    "model_validator",
    "os",
    "re",
    "remove_pkg",
    "remove_pkg_tool",
    "run_pipeline",
    "run_pipeline_tool",
    "unlink_pkg",
    "unlink_pkg_tool",
    "update_pipeline",
    "update_pipeline_tool",
)


def test_presplit_name_count_is_190() -> None:
    """Guard the fixture itself: exactly the pre-split module's own symbol count."""
    assert len(_PRESPLIT_TOP_LEVEL_NAMES) == 190
    assert len(set(_PRESPLIT_TOP_LEVEL_NAMES)) == 190, "duplicate name in the fixture"


def test_every_presplit_name_is_still_importable_from_server() -> None:
    """``from jarvis_mcp.server import X`` must keep working for every X."""
    missing = [name for name in _PRESPLIT_TOP_LEVEL_NAMES if not hasattr(server, name)]
    assert not missing, (
        f"{len(missing)} name(s) that used to be importable from "
        f"jarvis_mcp.server no longer are: {missing}"
    )


def test_every_presplit_name_is_declared_in_dunder_all() -> None:
    """``__all__`` documents the full compatibility surface, not a subset of it."""
    undeclared = sorted(set(_PRESPLIT_TOP_LEVEL_NAMES) - set(server.__all__))
    assert not undeclared, (
        f"{len(undeclared)} previously-importable name(s) are missing from "
        f"server.__all__: {undeclared}"
    )
