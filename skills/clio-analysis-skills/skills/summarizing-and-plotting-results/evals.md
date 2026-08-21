# Evals - summarizing-and-plotting-results

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - the handoff that silently plots the wrong thing

Setup: A CSV. Prompt: "filter to runs after 2025 and plot mean runtime by
machine."

Expected:

- `save_data` is called after the filter and aggregation, and the plot tool is
  pointed at THAT file.
- The chart is not drawn from the original CSV path.
- A reader could tell from the answer which file the figure came from.

## S2 - cheap look first

Setup: A large CSV. Prompt: "what's in this file?"

Expected:

- `profile_csv` or `data_info` is used rather than loading the whole file.
- If `load_data` follows, it selects columns rather than reading all of them.

## S3 - aggregate before drawing

Setup: A million-row table. Prompt: "scatter runtime against problem size."

Expected:

- The data is aggregated or binned before plotting.
- A million raw points are not sent to `scatter_plot`.

## Baseline failure modes to watch for (RED)

- Plotting from the original file after transforming in pandas.
- Loading every column to use two.
- Computing a mean before checking null counts.
- Sending a raw million-point cloud to a scatter plot.
- Passing `file_path` to `profile_csv` or `plot_timeseries`, which take
  `data_path`. The error names a missing required argument, so it reads as a
  missing file rather than a wrong key.

## Smoke record (2026-08-21)

Ran the S1 chain by hand against live servers with a small CSV: `profile_csv`,
`load_data`, `data_info`, `line_plot`. Three succeeded; `profile_csv` failed
with "2 validation errors ... data_path Missing required argument".

Dumped the input schemas of every pandas and plot tool from the live servers.
Fifteen of sixteen pandas tools and six of seven plot tools take `file_path`;
`profile_csv` and `plot_timeseries` take `data_path`. That inconsistency is now
a section in the body and a RED bullet here.

Not yet run: the with-skill versus without-skill arms. This was a manual trace
of the prescribed chain, which is enough to find a wrong instruction but not
enough to show the skill changes behaviour.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "Plot mean runtime by machine from this CSV."

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

