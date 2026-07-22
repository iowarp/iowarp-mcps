"""Live wire and packaged-artifact tests for locked MCP user contracts."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from clio_kit import mcp_contracts
from clio_kit import main
from clio_kit.mcp_contracts import (
    ContractGenerationError,
    MAX_PROBE_LINES,
    MCP_USER_CONTRACT_CANONICALIZATION,
    MCP_USER_CONTRACT_PROJECTION,
    USER_CONTRACT_SPECS,
    canonical_contract_projection,
    canonical_json_bytes,
    exchange_mcp_tools_list,
    generate_user_contract_artifacts,
    load_mcp_user_contract,
    mcp_user_contract_digest,
)

JSON = dict[str, Any]
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_contract_artifacts_are_forced_to_lf_in_every_checkout() -> None:
    """Raw artifact hashes must not vary with the checkout platform."""
    attributes = (REPOSITORY_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "src/clio_kit/_mcp_contracts/*.json text eol=lf" in attributes.splitlines()


def test_committed_contracts_match_real_locked_stdio_tools_list() -> None:
    """Committed artifacts must exactly match live FastMCP stdio responses."""
    observed = generate_user_contract_artifacts(REPOSITORY_ROOT, check=True)

    assert [artifact["contract_id"] for artifact in observed] == [
        spec.contract_id for spec in USER_CONTRACT_SPECS
    ]


def test_contract_probe_uses_a_fresh_isolated_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale project venv must never define the committed live contract."""
    captured: list[str] = []

    def fake_exchange(command: list[str], **_: object) -> tuple[dict, dict]:
        captured.extend(command)
        raise RuntimeError("stop after capturing the child command")

    monkeypatch.setattr(mcp_contracts, "exchange_mcp_tools_list", fake_exchange)
    with pytest.raises(RuntimeError, match="stop after capturing"):
        mcp_contracts.probe_user_contract(
            REPOSITORY_ROOT,
            USER_CONTRACT_SPECS[0],
        )

    assert "--isolated" in captured
    assert captured[captured.index("--refresh-package") + 1] == "jarvis-mcp"
    assert captured.index("--isolated") < captured.index("--project")


@pytest.mark.parametrize(
    ("contract_id", "expected_names"),
    [
        (
            "clio-kit-jarvis-user-v3.6",
            {
                "jarvis_create_pipeline",
                "jarvis_describe",
                "jarvis_add_step",
                "jarvis_edit_step",
                "jarvis_run",
                "jarvis_get_execution",
            },
        ),
        (
            "clio-kit-slurm-user-v3",
            {
                "slurm_submit",
                "slurm_list",
                "slurm_describe",
                "slurm_cluster",
                "slurm_cancel",
            },
        ),
        (
            "clio-kit-spack-user-v2.1",
            {"spack_find", "spack_install", "spack_locate"},
        ),
        (
            "clio-kit-scientific-catalog-user-v1.1",
            {"scientific_dataset_search", "scientific_dataset_describe"},
        ),
    ],
)
def test_shipped_contract_digest_covers_exact_user_surface(
    contract_id: str,
    expected_names: set[str],
) -> None:
    """The public digest is reproducible from the shipped wire Tool objects."""
    artifact = load_mcp_user_contract(contract_id)
    tools = [cast(JSON, tool) for tool in cast(list[object], artifact["tools"])]

    assert artifact["canonicalization"] == MCP_USER_CONTRACT_CANONICALIZATION
    assert artifact["projection"] == MCP_USER_CONTRACT_PROJECTION
    assert {tool["name"] for tool in tools} == expected_names
    assert artifact["contract_sha256"] == mcp_user_contract_digest(tools)
    assert (
        artifact["wire_sha256"]
        == hashlib.sha256(canonical_json_bytes({"tools": tools})).hexdigest()
    )


def test_previous_jarvis_contracts_remain_loadable_by_exact_identity() -> None:
    """JARVIS contract revisions do not erase released evidence."""
    previous = load_mcp_user_contract("clio-kit-jarvis-user-v3.5")

    assert previous["contract_id"] == "clio-kit-jarvis-user-v3.5"
    assert previous["contract_sha256"] == (
        "9933815ca7ee913d56a7cb1081d7702474bc984efcc97bf16434980172d0469d"
    )
    older = load_mcp_user_contract("clio-kit-jarvis-user-v3.4")
    assert older["contract_id"] == "clio-kit-jarvis-user-v3.4"
    assert older["contract_sha256"] == (
        "52bfe1d416e674d120f200e502ded2197ee27219c26891a22c6c33ba917d5696"
    )
    even_older = load_mcp_user_contract("clio-kit-jarvis-user-v3.3")
    assert even_older["contract_id"] == "clio-kit-jarvis-user-v3.3"
    assert even_older["contract_sha256"] == (
        "0993ee9b2ee9b3c2b021a3967d9221199c3a6be50d726d4b125812e6b1148115"
    )
    earlier = load_mcp_user_contract("clio-kit-jarvis-user-v3.2")
    assert earlier["contract_id"] == "clio-kit-jarvis-user-v3.2"
    assert earlier["contract_sha256"] == (
        "12f6d349c9d44d8ce3594943dcd4018ec9b6e01ebb0e59d468bb1bb783a1ad5d"
    )
    oldest_minor = load_mcp_user_contract("clio-kit-jarvis-user-v3.1")
    assert oldest_minor["contract_id"] == "clio-kit-jarvis-user-v3.1"
    assert oldest_minor["contract_sha256"] == (
        "adc7756025fbcc90b0695bd4eaac00bda5c6cff4eb2f248fd7be263bd90b9b8b"
    )
    oldest = load_mcp_user_contract("clio-kit-jarvis-user-v3")
    assert oldest["contract_id"] == "clio-kit-jarvis-user-v3"


def test_previous_spack_contract_remains_loadable_by_exact_identity() -> None:
    """The Spack 2.1 contract revision does not erase released v2 evidence."""
    previous = load_mcp_user_contract("clio-kit-spack-user-v2")

    assert previous["contract_id"] == "clio-kit-spack-user-v2"
    assert previous["contract_sha256"] == (
        "3c5412148c770f4844e98eb893c4db0d0afdbf13afe967df67bd5f7d25e1f7db"
    )


def test_previous_scientific_catalog_contract_remains_loadable() -> None:
    """The explicit handoff revision does not erase released v1 evidence."""
    previous = load_mcp_user_contract("clio-kit-scientific-catalog-user-v1")

    assert previous["contract_id"] == "clio-kit-scientific-catalog-user-v1"
    assert previous["contract_sha256"] == (
        "a53006f24f4698f659f0a7c8bf61fc7bd7ad23274b06d2eed2ccfca68b9ecb0a"
    )


def test_spack_contract_requires_load_spec_without_exposing_load() -> None:
    """Spack locate returns JARVIS's reload input without a fake load operation."""
    artifact = load_mcp_user_contract("clio-kit-spack-user-v2.1")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    assert set(tools) == {"spack_find", "spack_install", "spack_locate"}
    assert "spack_load" not in tools
    output_schema = cast(JSON, tools["spack_locate"]["outputSchema"])
    properties = cast(JSON, output_schema["properties"])
    assert properties["load_spec"] == {
        "type": "string",
        "description": (
            "Exact runtime identity for JARVIS. Copy this value unchanged from "
            "spack_locate.output.load_spec into one element of "
            "jarvis_run.input.spack_specs."
        ),
    }
    assert "load_spec" in cast(list[str], output_schema["required"])


def test_spack_surface_validator_accepts_described_required_load_spec() -> None:
    """A handoff description must not make the required string schema noncanonical."""

    spec = next(spec for spec in USER_CONTRACT_SPECS if spec.server_name == "spack")
    load_spec_description = (
        "Copy spack_locate.output.load_spec unchanged into one element of "
        "jarvis_run.input.spack_specs."
    )
    tools: list[JSON] = [
        {"name": "spack_find"},
        {"name": "spack_install"},
        {
            "name": "spack_locate",
            "outputSchema": {
                "type": "object",
                "properties": {
                    "load_spec": {
                        "type": "string",
                        "description": load_spec_description,
                    }
                },
                "required": ["load_spec"],
            },
        },
    ]

    mcp_contracts._validate_required_surface(spec, tools)


def test_scientific_catalog_contract_separates_discovery_from_scene_control() -> None:
    """Catalog tools expose exact descriptors without paths or scene inputs."""
    artifact = load_mcp_user_contract("clio-kit-scientific-catalog-user-v1.1")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    assert set(tools) == {"scientific_dataset_search", "scientific_dataset_describe"}
    search_input = cast(JSON, tools["scientific_dataset_search"]["inputSchema"])
    describe_input = cast(JSON, tools["scientific_dataset_describe"]["inputSchema"])
    encoded_inputs = json.dumps(
        {"search": search_input, "describe": describe_input},
        sort_keys=True,
    )
    for prohibited in (
        "file_path",
        "camera",
        "colormap",
        "filter_spec",
        "scheduler",
        "render_recipe",
    ):
        assert prohibited not in encoded_inputs
    describe_output = cast(JSON, tools["scientific_dataset_describe"]["outputSchema"])
    describe_properties = cast(JSON, describe_output["properties"])
    assert "dataset_descriptor" in cast(list[str], describe_output["required"])
    assert (
        describe_properties["dataset_descriptor"]
        == cast(JSON, describe_properties["dataset"])["properties"]["descriptor"]
    )
    assert "jarvis.dataset-descriptor.v1" in json.dumps(describe_output, sort_keys=True)


def test_spack_install_contract_exposes_explicit_concretization_modes() -> None:
    """Agents can choose Spack reuse or fresh concretization without guessing."""
    artifact = load_mcp_user_contract("clio-kit-spack-user-v2.1")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    install_input = cast(JSON, tools["spack_install"]["inputSchema"])
    properties = cast(JSON, install_input["properties"])
    reuse = cast(JSON, properties["reuse"])
    description = cast(str, reuse["description"])
    assert reuse["default"] is True
    assert reuse["type"] == "boolean"
    assert "--reuse" in description
    assert "--fresh" in description


def test_jarvis_contract_combines_mutations_and_execution_observation() -> None:
    """JARVIS gives agents one mutation and one durable observation semantic."""
    artifact = load_mcp_user_contract("clio-kit-jarvis-user-v3.6")
    tools = {
        cast(str, tool["name"]): cast(JSON, tool)
        for tool in cast(list[JSON], artifact["tools"])
    }

    assert "jarvis_remove_step" not in tools
    edit_input = cast(JSON, tools["jarvis_edit_step"]["inputSchema"])
    properties = cast(JSON, edit_input["properties"])
    operation = cast(JSON, properties["operation"])
    assert operation["enum"] == ["edit", "remove"]
    assert set(tools) == {
        "jarvis_create_pipeline",
        "jarvis_describe",
        "jarvis_add_step",
        "jarvis_edit_step",
        "jarvis_run",
        "jarvis_get_execution",
    }
    describe = cast(JSON, tools["jarvis_describe"])
    describe_input = cast(JSON, describe["inputSchema"])
    describe_properties = cast(JSON, describe_input["properties"])
    assert describe_properties["target"]["enum"] == [
        "packages",
        "package_search",
        "package",
        "pipeline",
        "step",
    ]
    assert "named application" in cast(str, describe["description"])
    assert "unique short name or fully qualified" in cast(
        str, describe_properties["package_name"]["description"]
    )
    assert describe_properties["page_size"]["default"] == 10
    assert describe_properties["page_size"]["maximum"] == 25
    assert describe_properties["query"]["description"].endswith(
        "target='package_search'."
    )
    describe_output = cast(JSON, describe["outputSchema"])
    describe_result = cast(JSON, describe_output["properties"])["result"]
    describe_variants = cast(list[JSON], cast(JSON, describe_result)["oneOf"])
    package_variant = next(
        variant
        for variant in describe_variants
        if cast(JSON, variant["properties"])["target"]
        == {"const": "package", "type": "string"}
    )
    package_schema = cast(JSON, cast(JSON, package_variant["properties"])["package"])
    package_properties = cast(JSON, package_schema["properties"])
    settings_options = cast(
        list[JSON], cast(JSON, package_properties["settings"])["anyOf"]
    )
    settings = next(option for option in settings_options if "items" in option)
    setting = cast(JSON, settings["items"])
    input_binding = cast(JSON, cast(JSON, setting["properties"])["input_binding"])
    assert input_binding["additionalProperties"] is False
    assert input_binding["required"] == ["schema_version", "kind", "structure"]
    assert input_binding["properties"] == {
        "kind": {"const": "local_file", "type": "string"},
        "schema_version": {
            "const": "jarvis.configuration-input-binding.v1",
            "type": "string",
        },
        "structure": {"const": "regular_file", "type": "string"},
    }
    add_step = cast(JSON, tools["jarvis_add_step"])
    add_input = cast(JSON, add_step["inputSchema"])
    add_properties = cast(JSON, add_input["properties"])
    assert "do_configure" not in add_properties
    assert "cannot be bypassed" in cast(str, add_step["description"])
    config_description = cast(str, cast(JSON, add_properties["config"])["description"])
    assert "canonical setting names exactly" in config_description
    assert "objects or lists" in config_description
    run_input = cast(JSON, tools["jarvis_run"]["inputSchema"])
    assert run_input["additionalProperties"] is False
    run_properties = cast(JSON, run_input["properties"])
    assert "wait" not in run_properties
    assert "without waiting" in cast(str, tools["jarvis_run"]["description"])
    assert "jarvis_get_execution" in cast(str, tools["jarvis_run"]["description"])
    execution_id = cast(JSON, run_properties["execution_id"])
    assert execution_id == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    query_input = cast(JSON, tools["jarvis_get_execution"]["inputSchema"])
    assert query_input["required"] == ["pipeline_id", "execution_id"]
    query_properties = cast(JSON, query_input["properties"])
    assert set(query_properties) == {
        "pipeline_id",
        "execution_id",
        "include_progress",
        "include_service_runtimes",
        "artifacts",
    }
    assert query_properties["include_progress"] == {
        "default": True,
        "type": "boolean",
    }
    assert query_properties["include_service_runtimes"] == {
        "default": False,
        "type": "boolean",
    }
    artifact_query = cast(JSON, query_properties["artifacts"])
    assert artifact_query["default"] is None
    artifact_object = cast(JSON, cast(list[JSON], artifact_query["anyOf"])[0])
    assert artifact_object["additionalProperties"] is False
    artifact_query_properties = cast(JSON, artifact_object["properties"])
    assert set(artifact_query_properties) == {
        "package_id",
        "role",
        "state",
        "artifact_id",
        "page_size",
        "cursor",
    }
    assert artifact_query_properties["page_size"] == {
        "default": 50,
        "description": "Maximum artifacts to return in this page.",
        "maximum": 100,
        "minimum": 1,
        "type": "integer",
    }
    expected_result_schemas = {
        "jarvis_run": "clio-kit.jarvis-run.v1",
        "jarvis_get_execution": "clio-kit.jarvis-execution.v2",
    }
    for tool_name, schema_version in expected_result_schemas.items():
        output = cast(JSON, tools[tool_name]["outputSchema"])
        output_properties = cast(JSON, output["properties"])
        assert output_properties["schema_version"] == {
            "const": schema_version,
            "type": "string",
        }
    for tool_name in ("jarvis_run", "jarvis_get_execution"):
        output = cast(JSON, tools[tool_name]["outputSchema"])
        handle = cast(JSON, cast(JSON, output["properties"])["execution_handle"])
        handle_properties = cast(JSON, handle["properties"])
        assert handle_properties["schema_version"] == {
            "const": "jarvis.execution.handle.v1",
            "type": "string",
        }
        assert set(cast(list[str], handle["required"])) == {
            "schema_version",
            "execution_id",
            "pipeline_id",
            "mode",
            "scheduler_provider",
            "scheduler_native_id",
            "cluster",
        }
    run_output = cast(JSON, tools["jarvis_run"]["outputSchema"])
    run_output_properties = cast(JSON, run_output["properties"])
    run_progress = cast(JSON, run_output_properties["progress"])
    run_progress_properties = cast(JSON, run_progress["properties"])
    assert run_progress_properties["schema_version"] == {
        "const": "jarvis.execution.progress.v1",
        "type": "string",
    }
    assert "progress" in cast(list[str], run_output["required"])
    execution_output = cast(JSON, tools["jarvis_get_execution"]["outputSchema"])
    assert execution_output["additionalProperties"] is False
    execution_output_properties = cast(JSON, execution_output["properties"])
    assert set(cast(list[str], execution_output["required"])) == {
        "schema_version",
        "pipeline_id",
        "execution_id",
        "execution_handle",
        "execution_record",
        "runtime_metadata",
        "progress",
        "artifact_page",
        "service_runtimes",
    }
    progress_options = cast(
        list[JSON], cast(JSON, execution_output_properties["progress"])["anyOf"]
    )
    progress_output = next(
        option for option in progress_options if "properties" in option
    )
    assert progress_output["additionalProperties"] is False
    progress_properties = cast(JSON, progress_output["properties"])
    assert progress_properties["schema_version"] == {
        "const": "jarvis.execution.progress.v1",
        "type": "string",
    }
    packages = cast(JSON, progress_properties["packages"])
    assert packages["maxItems"] == 4096
    package = cast(JSON, packages["items"])
    assert package["additionalProperties"] is False
    package_properties = cast(JSON, package["properties"])
    assert set(package_properties) == {
        "package_id",
        "package_name",
        "event_count",
        "latest",
    }
    assert set(cast(list[str], package["required"])) == set(package_properties)
    assert cast(JSON, package_properties["event_count"])["minimum"] == 0
    latest_options = cast(list[JSON], cast(JSON, package_properties["latest"])["anyOf"])
    latest = next(option for option in latest_options if "properties" in option)
    assert latest["additionalProperties"] is False
    latest_properties = cast(JSON, latest["properties"])
    assert set(latest_properties) == {
        "schema_version",
        "package_name",
        "package_id",
        "execution_id",
        "label",
        "state",
        "current",
        "total",
        "unit",
        "message",
        "sequence",
        "observed_at_epoch",
        "determinate",
        "metadata",
    }
    assert set(cast(list[str], latest["required"])) == {
        "schema_version",
        "package_name",
        "package_id",
        "execution_id",
        "label",
        "state",
        "sequence",
        "observed_at_epoch",
        "determinate",
        "metadata",
    }
    assert latest_properties["schema_version"] == {
        "const": "jarvis.progress.v1",
        "type": "string",
    }
    assert cast(JSON, latest_properties["state"])["enum"] == [
        "pending",
        "starting",
        "running",
        "ready",
        "completed",
        "failed",
        "canceled",
    ]
    assert latest_properties["metadata"] == {
        "additionalProperties": True,
        "type": "object",
    }
    artifact_options = cast(
        list[JSON], cast(JSON, execution_output_properties["artifact_page"])["anyOf"]
    )
    artifact_output = next(
        option for option in artifact_options if "properties" in option
    )
    assert artifact_output["additionalProperties"] is False
    artifact_output_properties = cast(JSON, artifact_output["properties"])
    assert artifact_output_properties["producer_schema_version"] == {
        "const": "jarvis.execution.artifacts.v1",
        "type": "string",
    }
    assert "schema_version" not in cast(JSON, artifact_output_properties["artifacts"])
    item = cast(JSON, artifact_output_properties["artifacts"])["items"]
    artifact_properties = cast(JSON, cast(JSON, item)["properties"])
    assert artifact_properties["schema_version"] == {
        "const": "jarvis.artifact.v1",
        "type": "string",
    }
    assert set(cast(list[str], artifact_output["required"])) == {
        "producer_schema_version",
        "pipeline_id",
        "execution_id",
        "execution_state",
        "terminal",
        "artifacts",
        "matching_artifact_count",
        "returned_artifact_count",
        "next_cursor",
    }
    service_options = cast(
        list[JSON],
        cast(JSON, execution_output_properties["service_runtimes"])["anyOf"],
    )
    service_output = next(
        option for option in service_options if "properties" in option
    )
    assert service_output["additionalProperties"] is False
    service_properties = cast(JSON, service_output["properties"])
    assert service_properties["schema_version"] == {
        "const": "jarvis.execution.service-runtimes.v1",
        "type": "string",
    }
    assert set(cast(list[str], service_output["required"])) == {
        "schema_version",
        "execution_id",
        "pipeline_id",
        "execution_state",
        "terminal",
        "service_runtimes",
    }
    runtime_items = cast(JSON, service_properties["service_runtimes"])["items"]
    runtime_revisions = cast(list[JSON], cast(JSON, runtime_items)["oneOf"])
    runtime_by_schema = {
        cast(
            str, cast(JSON, revision["properties"])["schema_version"]["const"]
        ): revision
        for revision in runtime_revisions
    }
    assert set(runtime_by_schema) == {
        "jarvis.service-runtime.v1",
        "jarvis.service-runtime.v2",
    }
    v1_runtime = runtime_by_schema["jarvis.service-runtime.v1"]
    v1_properties = cast(JSON, v1_runtime["properties"])
    assert v1_properties["schema_version"] == {
        "const": "jarvis.service-runtime.v1",
        "type": "string",
    }
    assert "authorization" not in v1_properties
    assert "authorization" not in cast(list[str], v1_runtime["required"])
    v2_runtime = runtime_by_schema["jarvis.service-runtime.v2"]
    v2_properties = cast(JSON, v2_runtime["properties"])
    assert v2_properties["schema_version"] == {
        "const": "jarvis.service-runtime.v2",
        "type": "string",
    }
    authorization = cast(JSON, v2_properties["authorization"])
    assert authorization["additionalProperties"] is False
    assert authorization["required"] == ["scheme", "token_sha256"]
    authorization_properties = cast(JSON, authorization["properties"])
    assert authorization_properties["scheme"] == {
        "const": "bearer",
        "type": "string",
    }
    assert "token" not in authorization_properties
    assert authorization_properties["token_sha256"] == {
        "maxLength": 64,
        "minLength": 64,
        "pattern": "^[0-9a-f]{64}$",
        "type": "string",
    }
    assert "authorization" in cast(list[str], v2_runtime["required"])
    descriptor = cast(JSON, v2_properties["dataset_descriptor"])
    descriptor_properties = cast(JSON, descriptor["properties"])
    assert descriptor_properties["schema_version"] == {
        "const": "jarvis.dataset-descriptor.v1",
        "type": "string",
    }
    assert "camera" not in descriptor_properties
    assert "colormap" not in descriptor_properties
    assert "filters" not in descriptor_properties


def test_contract_projection_matches_downstream_schema_digest_shape() -> None:
    """The canonical projection uses explicit optional fields and sorted tools."""
    tools: list[JSON] = [
        {"name": "z", "description": "last", "inputSchema": {"type": "object"}},
        {
            "name": "a",
            "inputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True},
        },
    ]

    assert canonical_contract_projection(tools) == {
        "tools": [
            {
                "annotations": {"readOnlyHint": True},
                "description": None,
                "input_schema": {"type": "object"},
                "name": "a",
                "output_schema": None,
                "title": None,
            },
            {
                "annotations": None,
                "description": "last",
                "input_schema": {"type": "object"},
                "name": "z",
                "output_schema": None,
                "title": None,
            },
        ]
    }


def test_contract_cli_lists_and_prints_verified_artifacts() -> None:
    """Operators and downstream release gates can inspect the wheel contract."""
    runner = CliRunner()

    listed = runner.invoke(main, ["mcp-contracts"])
    shown = runner.invoke(main, ["mcp-contract", "clio-kit-spack-user-v2.1"])

    assert listed.exit_code == 0, listed.output
    assert "clio-kit-jarvis-user-v3.6" in listed.output
    assert "clio-kit-jarvis-user-v3.5" in listed.output
    assert "clio-kit-jarvis-user-v3.4" in listed.output
    assert "clio-kit-jarvis-user-v3.3" in listed.output
    assert "clio-kit-jarvis-user-v3.2" in listed.output
    assert "clio-kit-slurm-user-v3" in listed.output
    assert "clio-kit-spack-user-v2.1" in listed.output
    assert "clio-kit-spack-user-v2" in listed.output
    assert "clio-kit-scientific-catalog-user-v1.1" in listed.output
    assert "clio-kit-scientific-catalog-user-v1" in listed.output
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["contract_id"] == "clio-kit-spack-user-v2.1"


@pytest.mark.parametrize(
    ("stream_name", "max_output_bytes", "max_line_bytes", "expected_error"),
    [
        ("stdout", 512, 4_096, "stdout byte limit exceeded"),
        ("stdout", 4_096, 512, "stdout line limit exceeded"),
        ("stderr", 512, 4_096, "stderr byte limit exceeded"),
        ("stderr", 4_096, 512, "stderr line limit exceeded"),
    ],
)
def test_contract_probe_kills_hostile_stream_on_live_overflow(
    tmp_path: Path,
    stream_name: str,
    max_output_bytes: int,
    max_line_bytes: int,
    expected_error: str,
) -> None:
    """Probe pipes are fixed-chunk bounded and kill a producer before it continues."""
    sentinel = tmp_path / f"{stream_name}-{max_output_bytes}-continued"
    script = (
        "import pathlib,sys,time; "
        f"stream=sys.{stream_name}.buffer; "
        "stream.write(b'x'*2048); stream.flush(); "
        "time.sleep(10); pathlib.Path(sys.argv[1]).write_text('continued')"
    )
    started = time.monotonic()

    with pytest.raises(ContractGenerationError, match=expected_error):
        exchange_mcp_tools_list(
            [sys.executable, "-c", script, str(sentinel)],
            contract_id=f"hostile-{stream_name}",
            timeout_seconds=8,
            max_output_bytes=max_output_bytes,
            max_line_bytes=max_line_bytes,
        )

    assert time.monotonic() - started < 5
    time.sleep(0.1)
    assert not sentinel.exists()


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_contract_probe_reports_line_count_overflow_immediately(
    tmp_path: Path,
    stream_name: str,
) -> None:
    """A full stdout queue cannot hide stdout or stderr line-count failures."""
    sentinel = tmp_path / f"{stream_name}-line-count-continued"
    script = (
        "import pathlib,sys,time; "
        f"stream=sys.{stream_name}.buffer; "
        "stream.write(b'x\\n'*int(sys.argv[2])); stream.flush(); "
        "time.sleep(10); pathlib.Path(sys.argv[1]).write_text('continued')"
    )
    started = time.monotonic()

    with pytest.raises(
        ContractGenerationError,
        match=rf"{stream_name} line-count limit exceeded",
    ):
        exchange_mcp_tools_list(
            [
                sys.executable,
                "-c",
                script,
                str(sentinel),
                str(MAX_PROBE_LINES + 1),
            ],
            contract_id=f"hostile-{stream_name}-line-count",
            timeout_seconds=8,
        )

    assert time.monotonic() - started < 5
    time.sleep(0.1)
    assert not sentinel.exists()


def test_contract_probe_reports_bounded_stderr_when_child_exits_early() -> None:
    """A startup failure retains its exit status and useful stderr diagnostic."""
    script = (
        "import sys; "
        "sys.stderr.write('locked server startup failed\\n'); "
        "sys.stderr.flush(); "
        "raise SystemExit(23)"
    )

    with pytest.raises(
        ContractGenerationError,
        match=r"child exit=23; stderr: locked server startup failed",
    ):
        exchange_mcp_tools_list(
            [sys.executable, "-c", script],
            contract_id="early-exit",
            timeout_seconds=5,
        )
