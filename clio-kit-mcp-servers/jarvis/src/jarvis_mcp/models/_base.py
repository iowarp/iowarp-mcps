"""Shared base for every closed (``extra="forbid"``) agent-visible document."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _ClosedDocument(BaseModel):
    """Base for agent-visible documents with no undeclared fields."""

    model_config = ConfigDict(extra="forbid")
