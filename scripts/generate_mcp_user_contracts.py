#!/usr/bin/env python3
"""Generate or verify locked JARVIS, SLURM, and Spack user-contract artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from clio_kit.mcp_contracts import (
    ContractGenerationError,
    generate_user_contract_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed artifacts differ from the live stdio surface.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the contract generator CLI."""
    args = _parser().parse_args(argv)
    try:
        artifacts = generate_user_contract_artifacts(
            args.repository_root,
            check=args.check,
        )
    except ContractGenerationError as exc:
        raise SystemExit(str(exc)) from exc
    action = "Verified" if args.check else "Generated"
    for artifact in artifacts:
        print(f"{action} {artifact['contract_id']}: {artifact['contract_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
