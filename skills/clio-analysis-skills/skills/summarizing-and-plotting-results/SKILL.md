---
name: summarizing-and-plotting-results
description: Use when a table would be summarised or plotted by reading it into context and eyeballing it, which misstates aggregates and silently drops rows on larger files. Covers CSV and Excel statistics and figures. Triggers on "plot this", "summarize the data", "make a chart". Not for mesh or volume data; use visualizing-3d-simulation-output. Not for choosing a chart type; use choosing-the-right-chart.
clio-kit:
  bundle: clio-analysis
  servers: clio-pandas, clio-plot
  provenance: designed
  eval-status: eval-run
---

# From a table to numbers and a figure

Two servers, and the handoff between them is where this goes wrong.

## The plotting tools read files, not dataframes

Every `clio-plot` tool takes a **path to a CSV or Excel file**. There is no way to
hand it the result of a pandas operation in memory.

So the chain is:

```
load_data → transform → save_data (CSV) → plot tool (reads that CSV)
```

Skipping `clio-pandas:save_data` means the plot is drawn from the original file,
silently ignoring every filter and aggregation applied. The chart renders. It is
just answering a different question.

## Two tools spell the file argument differently

Almost every tool on both servers takes `file_path`. Two do not, and they are
the two you reach for early:

| Tool | Argument |
|---|---|
| `clio-pandas:profile_csv` | `data_path` |
| `clio-plot:plot_timeseries` | `data_path` |

Fifteen pandas tools and six plot tools use `file_path`, so the pattern learned
from the rest is wrong for exactly these. Passing `file_path` to either returns
a validation error naming a missing required argument, which reads like the file
is missing rather than the key being wrong.

## Steps

**1. Look before loading.**

`clio-pandas:profile_csv` gives row and column counts, per-column dtype, null
counts and numeric ranges **without loading the file**. On a large CSV this is
the difference between a cheap look and an expensive one.

`clio-plot:data_info` answers a similar question and is the cheaper choice when
plotting is all that is wanted.

**2. Load only what you need.**

`clio-pandas:load_data` takes column selection and a row limit. Use both. Reading
40 columns to plot 2 is the same waste as reading a whole array for one number.

**3. Profile properly.**

`clio-pandas:profile_data` — shape, types, missing values, distributions, quality
checks. This is where you find out the column is 30% null before the mean is
computed from it. If it needs fixing, see `cleaning-and-validating-a-dataset`.

**4. Aggregate before plotting.**

`clio-pandas:groupby_operations` for grouped aggregates,
`clio-pandas:statistical_summary` for descriptives,
`clio-pandas:correlation_analysis` for relationships between columns,
`clio-pandas:pivot_table` to reshape into the layout the chart wants.

A million-point scatter is unreadable and slow. Aggregate to the resolution the
figure can actually show.

**5. Write the intermediate file.**

`clio-pandas:save_data` takes **`data` and `file_path`**, not a source file. The
server is stateless per call: every tool reads the file, computes, and returns a
result, and nothing carries a dataframe between calls. So the transform's
returned payload is what you pass forward as `data`.

This is the step that is easy to forget and that makes everything after it
wrong: skip it and the plot is drawn from the original file.

**6. Plot from that file.**

| Question | Tool |
|---|---|
| How does y change with x | `clio-plot:line_plot` |
| Several series over time | `clio-plot:plot_timeseries` |
| Compare across categories | `clio-plot:bar_plot` |
| Are these two related | `clio-plot:scatter_plot` |
| How is one variable distributed | `clio-plot:histogram_plot` |
| Which of many columns move together | `clio-plot:heatmap_plot` |

Match the chart to the question, not to preference — see
`choosing-the-right-chart`.

## When the data is not a table

Mesh and volume data does not belong here. `clio-plot` reads CSV and Excel; a
simulation field goes to ParaView instead — see
`visualizing-3d-simulation-output`.

## What not to do

- Do not plot before saving the transformed data; the plot reads the file.
- Do not load every column to use two.
- Do not compute a mean before checking the null count.
- Do not plot a million raw points instead of an aggregate.
- Do not reach for a chart type before deciding what the figure has to show.
- Do not assume `file_path` on `profile_csv` or `plot_timeseries`; both take
  `data_path`.
