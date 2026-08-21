# Evals - cleaning-and-validating-a-dataset

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - the fix depends on the pattern

Setup: A table where nulls occur in contiguous runs (a sensor dropout). Prompt:
"clean up the missing values."

Expected:

- `profile_data` is run before any imputation.
- The run structure is recognised and interpolation or forward-fill is chosen
  over a mean fill.
- The answer says a mean fill would invent a plateau that was never measured.

## S2 - outliers are looked at, not deleted

Setup: A skewed column with extreme values. Prompt: "remove the outliers."

Expected:

- IQR is preferred over Z-score for the skewed distribution, with a reason.
- Flagged rows are inspected before removal, and the answer raises that an
  extreme value may be the event of interest.

## S3 - rules that encode meaning

Setup: A table with a fraction column and an ID column. Prompt: "validate this
data."

Expected:

- `validate_data` rules are stated from meaning: fraction in [0, 1], ID unique
  and non-null.
- The answer distinguishes this from a purely statistical check.

## S4 - reporting the cleaning

Setup: Any of the above, then: "so what's the average?"

Expected:

- The answer reports which columns were imputed and how, and how many rows were
  dropped, alongside the number.

## Baseline failure modes to watch for (RED)

- Imputing before knowing whether gaps are random, in runs, or grouped.
- Mean-filling a skewed column.
- Deleting flagged outliers unexamined.
- Deduplicating before establishing what identifies a row.
- Reporting results from cleaned data with no record of the cleaning.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "There are missing values and duplicates in this table."

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

