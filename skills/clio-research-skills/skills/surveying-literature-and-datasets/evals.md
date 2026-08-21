# Evals - surveying-literature-and-datasets

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - the search that matches the question

Setup: Prompt: "find work on speculative decoding for LLM inference."

Expected:

- `search_by_abstract` is used, not `search_arxiv`, and the choice is justified
  as finding papers that DID the thing rather than named it.
- A thin result set triggers a different axis (`find_similar_papers` from the
  closest hit) rather than the same query reworded.

## S2 - a subject code is not guessed

Setup: Prompt: "what's new in distributed computing on arXiv?"

Expected:

- The category code is established rather than invented; an invalid code
  returning nothing is not reported as "no such work exists".

## S3 - from paper to usable data

Setup: Prompt: "find the dataset behind this paper and get it so I can look at
it."

Expected:

- `search_datasets` then `get_dataset_details` before `stage_resource`.
- `stage_resource` is called and `local_path` is what gets handed to any reader.
- A dataset that has only been searched is not treated as readable.

## Baseline failure modes to watch for (RED)

- Defaulting to `search_arxiv` for every question.
- Guessing arXiv subject codes.
- Declaring "no work exists" from a single query.
- Characterising a paper's findings from its title alone.
- Treating a preprint as peer reviewed.
- Attempting to analyse a dataset that was never staged.
