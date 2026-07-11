"""Verify that a PyPI release contains the exact locally built artifact bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_BUFFER_BYTES = 1024 * 1024
_MAX_INDEX_RESPONSE_BYTES = 8 * 1024 * 1024
_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_PYPI_FILE_HOST = re.compile(r"(^|\.)pythonhosted\.org$")


class ReleaseVerificationError(RuntimeError):
    """Raised when the remote release differs from the local build."""


@dataclass(frozen=True)
class ArtifactIdentity:
    """Immutable identity for one locally built distribution artifact."""

    name: str
    path: Path
    size: int
    sha256: str


def discover_local_artifacts(dist_dir: Path) -> dict[str, ArtifactIdentity]:
    """Return the exact wheel and sdist identities found in ``dist_dir``."""
    if not dist_dir.is_dir():
        raise ReleaseVerificationError(
            f"distribution directory does not exist: {dist_dir}"
        )
    directory_files = sorted(path for path in dist_dir.iterdir() if path.is_file())
    unexpected = [
        path.name
        for path in directory_files
        if path.name != ".gitignore" and not path.name.endswith((".whl", ".tar.gz"))
    ]
    if unexpected:
        raise ReleaseVerificationError(
            f"distribution directory contains unexpected files: {unexpected}"
        )
    paths = [
        path for path in directory_files if path.name.endswith((".whl", ".tar.gz"))
    ]
    if not paths:
        raise ReleaseVerificationError("distribution directory contains no artifacts")
    wheels = [path for path in paths if path.name.endswith(".whl")]
    sdists = [path for path in paths if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1 or len(paths) != 2:
        raise ReleaseVerificationError(
            "distribution directory must contain exactly one wheel and one sdist"
        )
    artifacts: dict[str, ArtifactIdentity] = {}
    for path in paths:
        name = path.name
        if _ARTIFACT_NAME.fullmatch(name) is None or not name.endswith(
            (".whl", ".tar.gz")
        ):
            raise ReleaseVerificationError(f"unexpected distribution artifact: {name}")
        artifacts[name] = ArtifactIdentity(
            name=name,
            path=path,
            size=path.stat().st_size,
            sha256=_sha256_file(path),
        )
    return artifacts


def verify_release(
    *,
    project: str,
    version: str,
    dist_dir: Path,
    index_base_url: str = "https://pypi.org/pypi",
    timeout_seconds: float = 30.0,
) -> dict[str, ArtifactIdentity]:
    """Download and verify every artifact published for one PyPI release."""
    artifacts = discover_local_artifacts(dist_dir)
    endpoint = (
        f"{index_base_url.rstrip('/')}/"
        f"{urllib.parse.quote(project, safe='')}/"
        f"{urllib.parse.quote(version, safe='')}/json"
    )
    document = _read_json(endpoint, timeout_seconds=timeout_seconds)
    _validate_project_identity(document, project=project, version=version)
    remote_files = _remote_files(document)
    if set(remote_files) != set(artifacts):
        missing = sorted(set(artifacts) - set(remote_files))
        unexpected = sorted(set(remote_files) - set(artifacts))
        raise ReleaseVerificationError(
            f"PyPI artifact set mismatch: missing={missing}, unexpected={unexpected}"
        )

    for name, artifact in artifacts.items():
        remote = remote_files[name]
        remote_size = remote.get("size")
        if isinstance(remote_size, bool) or not isinstance(remote_size, int):
            raise ReleaseVerificationError(f"PyPI omitted a valid size for {name}")
        if remote_size != artifact.size:
            raise ReleaseVerificationError(
                f"PyPI size mismatch for {name}: {remote_size} != {artifact.size}"
            )
        digests = remote.get("digests")
        remote_digest = digests.get("sha256") if isinstance(digests, dict) else None
        if remote_digest != artifact.sha256:
            raise ReleaseVerificationError(
                f"PyPI declared SHA-256 mismatch for {name}: "
                f"{remote_digest!r} != {artifact.sha256}"
            )
        download_url = remote.get("url")
        if not isinstance(download_url, str):
            raise ReleaseVerificationError(f"PyPI omitted the download URL for {name}")
        if not _trusted_pypi_file_url(download_url):
            raise ReleaseVerificationError(
                f"PyPI returned an untrusted artifact URL for {name}: {download_url}"
            )
        downloaded_size, downloaded_digest = _download_identity(
            download_url,
            expected_max_bytes=artifact.size,
            timeout_seconds=timeout_seconds,
        )
        if downloaded_size != artifact.size or downloaded_digest != artifact.sha256:
            raise ReleaseVerificationError(
                f"downloaded PyPI bytes differ for {name}: "
                f"size={downloaded_size}, sha256={downloaded_digest}"
            )
    return artifacts


def _validate_project_identity(
    document: dict[str, Any], *, project: str, version: str
) -> None:
    info = document.get("info")
    if not isinstance(info, dict):
        raise ReleaseVerificationError("PyPI response omitted project metadata")
    remote_name = info.get("name")
    remote_version = info.get("version")
    if not isinstance(remote_name, str) or _canonical_project(remote_name) != (
        _canonical_project(project)
    ):
        raise ReleaseVerificationError(
            f"PyPI project identity mismatch: {remote_name!r} != {project!r}"
        )
    if remote_version != version:
        raise ReleaseVerificationError(
            f"PyPI version identity mismatch: {remote_version!r} != {version!r}"
        )


def _remote_files(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = document.get("urls")
    if not isinstance(values, list):
        raise ReleaseVerificationError("PyPI response omitted release files")
    remote: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict):
            raise ReleaseVerificationError(
                "PyPI returned an invalid release file record"
            )
        typed_value = {str(key): item for key, item in value.items()}
        name = typed_value.get("filename")
        if not isinstance(name, str) or _ARTIFACT_NAME.fullmatch(name) is None:
            raise ReleaseVerificationError("PyPI returned an invalid artifact filename")
        if name in remote:
            raise ReleaseVerificationError(f"PyPI returned duplicate artifact {name}")
        remote[name] = typed_value
    return remote


def _read_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "clio-kit-release-gate/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read(_MAX_INDEX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_INDEX_RESPONSE_BYTES:
        raise ReleaseVerificationError("PyPI index response exceeded its size limit")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"PyPI returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseVerificationError("PyPI response was not a JSON object")
    return {str(key): item for key, item in value.items()}


def _download_identity(
    url: str, *, expected_max_bytes: int, timeout_seconds: float
) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "clio-kit-release-gate/1",
        },
    )
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        final_url = response.geturl()
        if not _trusted_pypi_file_url(final_url):
            raise ReleaseVerificationError(
                f"PyPI artifact redirected to an untrusted URL: {final_url}"
            )
        while chunk := response.read(_BUFFER_BYTES):
            size += len(chunk)
            if size > expected_max_bytes:
                raise ReleaseVerificationError(
                    "downloaded PyPI artifact exceeded its expected size"
                )
            digest.update(chunk)
    return size, digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_BUFFER_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_project(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _trusted_pypi_file_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return (
        parsed.scheme == "https"
        and _PYPI_FILE_HOST.search(parsed.hostname or "") is not None
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def main() -> int:
    """Run the exact-byte PyPI verification command."""
    args = _parser().parse_args()
    if args.attempts < 1 or args.retry_delay_seconds < 0 or args.timeout_seconds <= 0:
        raise SystemExit(
            "attempts and timeout must be positive; retry delay cannot be negative"
        )
    last_error: BaseException | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            artifacts = verify_release(
                project=args.project,
                version=args.version,
                dist_dir=args.dist_dir,
                timeout_seconds=args.timeout_seconds,
            )
            print(
                json.dumps(
                    {
                        "schema_version": "clio-kit.pypi-release-verification.v1",
                        "project": args.project,
                        "version": args.version,
                        "artifacts": [
                            {
                                "filename": artifact.name,
                                "size": artifact.size,
                                "sha256": artifact.sha256,
                            }
                            for artifact in artifacts.values()
                        ],
                        "verified": True,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            return 0
        except (
            ReleaseVerificationError,
            TimeoutError,
            urllib.error.URLError,
        ) as exc:
            last_error = exc
            if attempt < args.attempts:
                print(
                    f"PyPI verification attempt {attempt}/{args.attempts} failed: {exc}",
                    flush=True,
                )
                time.sleep(args.retry_delay_seconds)
    raise SystemExit(f"PyPI exact-byte verification failed: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
