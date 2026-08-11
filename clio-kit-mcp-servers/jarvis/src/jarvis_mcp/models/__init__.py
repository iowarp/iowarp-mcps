"""Wire-facing data models for the jarvis MCP server, grouped by concern.

Split out of ``jarvis_mcp.server`` (clio-kit campaign #362, Slice 1) so the
44 Pydantic/TypedDict/dataclass models that previously lived inline in the
3109-line ``server.py`` have owner modules. Tool registration (the
``@mcp.tool`` surface) stays thin in ``server.py``, importing from here.

Submodules, by concern:

- ``_base``: the shared ``_ClosedDocument`` base (``extra="forbid"``).
- ``compat``: the JARVIS-CD manager compatibility adapter.
- ``packages``: package inventory/description/deployment/settings documents.
- ``describe``: the ``jarvis_describe`` discriminated result union.
- ``execution``: execution handle/record/run-result documents, and the
  ``ExecutionIntent`` request model with its validation/conversion helpers.
- ``progress``: package progress event/snapshot documents.
- ``artifact_documents``: artifact location/document/page documents and the
  ``ExecutionArtifactQuery`` request filter.
- ``datasets``: the JARVIS-owned dataset descriptor documents.
- ``service_runtime``: execution-owned service-runtime documents.
"""
