"""Tests for exact-byte PyPI release verification."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch
from urllib.request import Request

import pytest


def _load_release_module() -> ModuleType:
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_pypi_release.py"
    spec = importlib.util.spec_from_file_location(
        "clio_kit_verify_pypi_release", script
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load release verifier: {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_RELEASE_MODULE = _load_release_module()
ReleaseVerificationError = _RELEASE_MODULE.ReleaseVerificationError
verify_release = _RELEASE_MODULE.verify_release


class _Response:
    def __init__(self, payload: bytes, *, url: str = "https://pypi.org/pypi") -> None:
        self._payload = payload
        self._offset = 0
        self._url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload) - self._offset
        payload = self._payload[self._offset : self._offset + size]
        self._offset += len(payload)
        return payload

    def geturl(self) -> str:
        return self._url


def _release_document(artifacts: dict[str, bytes]) -> dict[str, Any]:
    return {
        "info": {"name": "clio-kit", "version": "2.3.0"},
        "urls": [
            {
                "filename": name,
                "size": len(payload),
                "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
                "url": f"https://files.pythonhosted.org/packages/{name}",
            }
            for name, payload in artifacts.items()
        ],
    }


def test_verify_release_downloads_and_matches_exact_bytes(tmp_path: Path) -> None:
    local = {
        "clio_kit-2.3.0-py3-none-any.whl": b"exact-wheel-bytes",
        "clio_kit-2.3.0.tar.gz": b"exact-sdist-bytes",
    }
    for name, payload in local.items():
        (tmp_path / name).write_bytes(payload)
    document = json.dumps(_release_document(local)).encode()

    def urlopen(request: Request, *, timeout: float) -> _Response:
        assert timeout == 3.0
        url = request.full_url
        if url.endswith("/json"):
            return _Response(document)
        return _Response(local[url.rsplit("/", 1)[-1]], url=url)

    with patch.object(_RELEASE_MODULE.urllib.request, "urlopen", urlopen):
        verified = verify_release(
            project="clio-kit",
            version="2.3.0",
            dist_dir=tmp_path,
            timeout_seconds=3.0,
        )

    assert set(verified) == {
        "clio_kit-2.3.0-py3-none-any.whl",
        "clio_kit-2.3.0.tar.gz",
    }


def test_verify_release_rejects_downloaded_byte_mismatch(tmp_path: Path) -> None:
    local = {
        "clio_kit-2.3.0-py3-none-any.whl": b"expected-wheel",
        "clio_kit-2.3.0.tar.gz": b"expected-sdist",
    }
    for name, payload in local.items():
        (tmp_path / name).write_bytes(payload)
    document = json.dumps(_release_document(local)).encode()

    def urlopen(request: Request, *, timeout: float) -> _Response:
        del timeout
        url = request.full_url
        if url.endswith("/json"):
            return _Response(document)
        name = url.rsplit("/", 1)[-1]
        return _Response(
            b"wrong" if name.endswith(".tar.gz") else local[name],
            url=url,
        )

    with (
        patch.object(_RELEASE_MODULE.urllib.request, "urlopen", urlopen),
        pytest.raises(ReleaseVerificationError, match="differ"),
    ):
        verify_release(project="clio-kit", version="2.3.0", dist_dir=tmp_path)


def test_verify_release_rejects_unexpected_remote_artifacts(tmp_path: Path) -> None:
    local = {
        "clio_kit-2.3.0-py3-none-any.whl": b"expected-wheel",
        "clio_kit-2.3.0.tar.gz": b"expected-sdist",
    }
    for name, payload in local.items():
        (tmp_path / name).write_bytes(payload)
    document = _release_document(local)
    document["urls"].append(
        {
            "filename": "clio_kit-2.3.0-extra.whl",
            "size": 1,
            "digests": {"sha256": hashlib.sha256(b"x").hexdigest()},
            "url": "https://files.pythonhosted.org/packages/extra.whl",
        }
    )

    def urlopen(_request: Request, *, timeout: float) -> _Response:
        del timeout
        return _Response(json.dumps(document).encode())

    with (
        patch.object(_RELEASE_MODULE.urllib.request, "urlopen", urlopen),
        pytest.raises(ReleaseVerificationError, match="unexpected"),
    ):
        verify_release(project="clio-kit", version="2.3.0", dist_dir=tmp_path)


def test_verify_release_requires_one_wheel_and_one_sdist(tmp_path: Path) -> None:
    (tmp_path / "clio_kit-2.3.0-py3-none-any.whl").write_bytes(b"wheel")

    with pytest.raises(ReleaseVerificationError, match="one wheel and one sdist"):
        verify_release(project="clio-kit", version="2.3.0", dist_dir=tmp_path)
