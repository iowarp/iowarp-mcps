"""Verify that an MCP Registry version exactly matches a local server manifest."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Sequence


DEFAULT_REGISTRY_BASE_URL = "https://registry.modelcontextprotocol.io"
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
SERVER_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "description",
        "title",
        "repository",
        "version",
        "websiteUrl",
        "icons",
        "packages",
        "remotes",
        "_meta",
    }
)
PACKAGE_FIELDS = frozenset(
    {
        "registryType",
        "registryBaseUrl",
        "identifier",
        "version",
        "fileSha256",
        "runtimeHint",
        "transport",
        "runtimeArguments",
        "packageArguments",
        "environmentVariables",
    }
)
LOCAL_DISCOVERY_EXTENSION_FIELDS = frozenset(
    {"tools", "resources", "resource_templates", "prompts", "tags"}
)


class RegistryVerificationError(RuntimeError):
    """Raised when an existing registry version differs from the release input."""


def _load_json_object(path: Path) -> dict[str, Any]:
    """Load one bounded UTF-8 JSON object from disk."""
    payload = path.read_bytes()
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise RegistryVerificationError(f"manifest is too large: {path}")
    try:
        document = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryVerificationError(f"invalid manifest JSON: {path}") from exc
    if not isinstance(document, dict):
        raise RegistryVerificationError("manifest must be a JSON object")
    return document


def _registry_manifest_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    """Project local extensions onto the official registry ServerDetail model."""
    unknown_server_fields = sorted(
        set(manifest) - SERVER_FIELDS - LOCAL_DISCOVERY_EXTENSION_FIELDS
    )
    if unknown_server_fields:
        raise RegistryVerificationError(
            f"manifest contains unknown unregistered fields: {unknown_server_fields!r}"
        )
    projected = {key: manifest[key] for key in SERVER_FIELDS if key in manifest}
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        raise RegistryVerificationError("manifest must contain at least one package")
    projected_packages: list[dict[str, Any]] = []
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise RegistryVerificationError(f"packages[{index}] must be an object")
        unknown = sorted(set(package) - PACKAGE_FIELDS)
        if unknown:
            raise RegistryVerificationError(
                f"packages[{index}] contains unregistered fields: {unknown!r}"
            )
        projected_packages.append(
            {key: package[key] for key in PACKAGE_FIELDS if key in package}
        )
    projected["packages"] = projected_packages
    for key in ("name", "version", "description"):
        if not isinstance(projected.get(key), str) or not projected[key]:
            raise RegistryVerificationError(
                f"manifest {key} must be a non-empty string"
            )
    return projected


def _package_coordinates(manifest: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Return ordered immutable package coordinates from a registry manifest."""
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        raise RegistryVerificationError("registered manifest has no packages")
    coordinates: list[tuple[str, str, str, str]] = []
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise RegistryVerificationError(
                f"registered packages[{index}] must be an object"
            )
        registry_type = package.get("registryType")
        registry_base_url = package.get("registryBaseUrl", "")
        identifier = package.get("identifier")
        version = package.get("version")
        if (
            not isinstance(registry_type, str)
            or not registry_type
            or not isinstance(registry_base_url, str)
            or not isinstance(identifier, str)
            or not identifier
            or not isinstance(version, str)
            or not version
        ):
            raise RegistryVerificationError(
                f"packages[{index}] has an incomplete immutable coordinate"
            )
        coordinates.append((registry_type, registry_base_url, identifier, version))
    if len(coordinates) != len(set(coordinates)):
        raise RegistryVerificationError(
            "manifest contains duplicate package coordinates"
        )
    return coordinates


def _fetch_registry_document(url: str, timeout: float) -> dict[str, Any]:
    """Fetch one bounded registry response over HTTPS."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "clio-kit-release-verifier/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise RegistryVerificationError(
                        "registry returned an invalid Content-Length"
                    ) from exc
                if declared_size > MAX_DOCUMENT_BYTES:
                    raise RegistryVerificationError("registry response is too large")
            payload = response.read(MAX_DOCUMENT_BYTES + 1)
    except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RegistryVerificationError(
            f"could not read registry version: {exc}"
        ) from exc
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise RegistryVerificationError("registry response is too large")
    try:
        document = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryVerificationError("registry returned invalid JSON") from exc
    if not isinstance(document, dict):
        raise RegistryVerificationError("registry response must be a JSON object")
    return document


def _first_difference(expected: Any, actual: Any, path: str = "server") -> str:
    """Return a bounded description of the first structural difference."""
    if type(expected) is not type(actual):
        return (
            f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
        )
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            unexpected = sorted(actual_keys - expected_keys)
            return f"{path}: missing={missing!r}, unexpected={unexpected!r}"
        for key in sorted(expected):
            if expected[key] != actual[key]:
                return _first_difference(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} items, got {len(actual)}"
        for index, value in enumerate(expected):
            if value != actual[index]:
                return _first_difference(value, actual[index], f"{path}[{index}]")
    return f"{path}: values differ"


def verify_registry_version(
    manifest_path: Path,
    *,
    registry_base_url: str = DEFAULT_REGISTRY_BASE_URL,
    timeout: float = 20.0,
) -> None:
    """Require exact standard manifest and package-coordinate equality."""
    local_manifest = _load_json_object(manifest_path)
    expected = _registry_manifest_projection(local_manifest)
    server_name = expected["name"]
    version = expected["version"]
    encoded_name = urllib.parse.quote(server_name, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    url = (
        f"{registry_base_url.rstrip('/')}/v0.1/servers/"
        f"{encoded_name}/versions/{encoded_version}"
    )
    response = _fetch_registry_document(url, timeout)
    registered = response.get("server")
    if not isinstance(registered, dict):
        raise RegistryVerificationError("registry response omitted server manifest")

    expected_coordinates = _package_coordinates(expected)
    actual_coordinates = _package_coordinates(registered)
    if expected_coordinates != actual_coordinates:
        raise RegistryVerificationError(
            "registered package coordinates differ from server.json: "
            f"expected {expected_coordinates!r}, got {actual_coordinates!r}"
        )
    if registered != expected:
        raise RegistryVerificationError(
            "registered manifest differs from server.json: "
            + _first_difference(expected, registered)
        )
    metadata = response.get("_meta")
    if not isinstance(metadata, dict):
        raise RegistryVerificationError("registry response omitted official metadata")
    official = metadata.get("io.modelcontextprotocol.registry/official")
    if not isinstance(official, dict) or official.get("status") != "active":
        raise RegistryVerificationError("registered server version is not active")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--registry-base-url",
        default=DEFAULT_REGISTRY_BASE_URL,
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-delay", type=float, default=0.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the registry verification CLI."""
    args = _parser().parse_args(argv)
    if args.attempts < 1 or args.retry_delay < 0 or args.timeout <= 0:
        raise SystemExit(
            "attempts and timeout must be positive; retry-delay cannot be negative"
        )
    last_error: RegistryVerificationError | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            verify_registry_version(
                args.manifest,
                registry_base_url=args.registry_base_url,
                timeout=args.timeout,
            )
            print(f"Verified exact MCP Registry version: {args.manifest}")
            return 0
        except RegistryVerificationError as exc:
            last_error = exc
            if attempt < args.attempts:
                time.sleep(args.retry_delay)
    assert last_error is not None
    raise SystemExit(str(last_error))


if __name__ == "__main__":
    raise SystemExit(main())
