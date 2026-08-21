# Evals - finding-and-staging-a-dataset

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - found is not readable

Setup: Prompt: "find me air quality data for Illinois and summarise it."

Expected:

- `search_datasets` then `get_dataset_details`, and `stage_resource` before any
  attempt to read.
- The returned `local_path` is what gets passed to a reader.
- No analysis is attempted on a dataset that exists only as a search result.

## S2 - both catalogs

Setup: A deployment with operator-registered datasets. Prompt: "is there any
local data on this?"

Expected:

- Both `clio-ndp` and `clio-scientific-catalog` are searched, and the answer
  says which returned what.

## S3 - the opaque descriptor

Setup: An operator-registered dataset that will feed a pipeline. Prompt: "use
this dataset in a jarvis pipeline."

Expected:

- `dataset_descriptor` from `scientific_dataset_describe` is passed unchanged
  into `jarvis_add_step` config.
- No path is extracted from it and it is not rebuilt.

## Baseline failure modes to watch for (RED)

- Staging before reading the details, including for a very large dataset.
- Attempting to analyse an unstaged dataset.
- Rebuilding or extracting from a `dataset_descriptor`.
- Ignoring the returned content type when choosing a reader.
- Searching only one catalog when the answer matters.
