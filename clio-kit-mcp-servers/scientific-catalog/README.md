# Scientific Catalog MCP

This server exposes an operator-maintained catalog of scientific datasets through two compact,
read-only tools: `scientific_dataset_search` and `scientific_dataset_describe`. It is designed to
run on a cluster through clio-relay's generic remote-MCP federation.

The catalog contains intrinsic identity and discovery metadata only. It may name and describe a
dataset, list its arrays and bounded members, and record fingerprints and provenance. It cannot
contain camera positions, colormaps, filters, thresholds, render recipes, scheduler commands, or
demo behavior. JARVIS consumes the returned `jarvis.dataset-descriptor.v1`; visualization choices
remain runtime commands.

`scientific_dataset_describe` keeps the human-facing catalog record under `dataset` and also
returns its exact descriptor as the top-level `dataset_descriptor` field. Pass that named value
unchanged as `jarvis_add_step.config.dataset_descriptor`; do not pass the surrounding `dataset`
record. `descriptor_sha256` identifies the same descriptor bytes after canonical JSON encoding.

Run from the containing clio-kit installation:

```console
clio-kit mcp-server scientific-catalog -- \
  --catalog-file /absolute/site/path/scientific-catalog.json
```

The catalog file uses `clio-kit.scientific-dataset-catalog.v1`:

```json
{
  "schema_version": "clio-kit.scientific-dataset-catalog.v1",
  "site_id": "example-cluster",
  "revision": "2026-07-15",
  "datasets": [
    {
      "dataset_id": "example-volume",
      "title": "Example volume",
      "summary": "A bounded temporal VTK volume.",
      "tags": ["volume", "vtk"],
      "descriptor": {
        "schema_version": "jarvis.dataset-descriptor.v1",
        "dataset_id": "example-volume",
        "kind": "temporal-volume",
        "format": "vti",
        "members": [
          {"index": 0, "location": "/data/example/frame-000.vti", "timestep": 0.0}
        ],
        "arrays": [
          {"name": "density", "association": "point", "components": 1}
        ],
        "bounds": null,
        "fingerprint": {"algorithm": "sha256", "digest": "0e3f72c38f94d2435756f8f2807b154f5cbec5166a1b9071f894277f0ea031dd"},
        "source_artifact": null
      }
    }
  ]
}
```
