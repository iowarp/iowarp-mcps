"""Typed parsers for the MCP runtime cache environment configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping

EmitEvent = Callable[[Mapping[str, object]], None]


def positive_int_config(
    raw: str | None,
    *,
    default: int,
    name: str,
    emit: EmitEvent,
) -> int:
    """Parse a positive integer, emitting the typed fallback reason."""
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "not_an_integer",
                "using_default": default,
            }
        )
        return default
    if value < 1:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "below_minimum",
                "using_default": default,
            }
        )
        return default
    return value


def optional_positive_int_config(
    raw: str | None,
    *,
    name: str,
    emit: EmitEvent,
) -> int | None:
    """Parse an optional positive integer, emitting the typed rejection."""
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "not_an_integer",
                "using_default": None,
            }
        )
        return None
    if value < 1:
        emit(
            {
                "event": "cache_config_rejected",
                "name": name,
                "value": raw,
                "reason": "below_minimum",
                "using_default": None,
            }
        )
        return None
    return value


def bool_config(raw: str | None, *, default: bool) -> bool:
    """Parse a permissive environment boolean or return its default."""
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
