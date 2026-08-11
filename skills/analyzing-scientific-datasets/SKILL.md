---
name: analyzing-scientific-datasets
description: Inspects a scientific data file, loads the part that matters into a dataframe, computes statistics, and renders a chart. Use when the user asks what is inside an HDF5, Parquet, or ADIOS BP5 file, wants a dataset summarized, correlated, or plotted, or mentions .h5, .hdf5, .parquet, or .bp files.
category: Data Analysis
servers: clio-hdf5, clio-parquet, clio-adios, clio-pandas, clio-plot
tools: clio-hdf5:list_keys, clio-hdf5:get_shape, clio-hdf5:read_partial_dataset, clio-hdf5:export_dataset, clio-parquet:summarize_tool, clio-parquet:read_slice_tool, clio-parquet:aggregate_column_tool, clio-adios:inspect_variables, clio-adios:read_variable_at_step, clio-pandas:load_data, clio-pandas:profile_data, clio-pandas:statistical_summary, clio-pandas:correlation_analysis, clio-plot:plot_timeseries, clio-plot:scatter_plot, clio-plot:histogram_plot, clio-hdf5:read_full_dataset, clio-pandas:profile_csv, clio-pandas:hypothesis_testing
---

# Analyzing a scientific dataset

Scientific files are usually far larger than the question being asked of them.
Inspect the structure first, read only the slice that answers the question, then
analyse and plot. Loading a whole file to compute one mean is the failure this
workflow exists to prevent.

## Workflow

```
- [ ] 1. Identify the format and inspect its structure
- [ ] 2. Read only the slice needed
- [ ] 3. Profile before analysing
- [ ] 4. Compute the specific statistic
- [ ] 5. Plot only if it adds something a number cannot
```

## 1. Inspect structure before reading anything

Pick the server by file extension. Do not read data in this step.

| Extension | Inspect with |
|---|---|
| `.h5`, `.hdf5` | `clio-hdf5:list_keys`, then `clio-hdf5:get_shape` on the interesting dataset |
| `.parquet` | `clio-parquet:summarize_tool` — schema, row count, file size in one call |
| `.bp` | `clio-adios:inspect_variables` — type, shape, and available steps |
| `.csv`, `.xlsx` | `clio-pandas:profile_csv` |

Shape and dtype decide the next step. A dataset of a few thousand rows can be
read whole; anything larger should be sliced.

## 2. Read only what the question needs

- HDF5: `clio-hdf5:read_partial_dataset` with an explicit slice. Reach for
  `clio-hdf5:read_full_dataset` only after `clio-hdf5:get_shape` shows the
  dataset is small.
- Parquet: `clio-parquet:read_slice_tool` with a column projection. If the
  question is a single aggregate, use `clio-parquet:aggregate_column_tool`
  instead and skip loading rows entirely.
- ADIOS: `clio-adios:read_variable_at_step` — BP5 data is per-step, so a step
  is required, not optional.

## 3. Profile before analysing

Call `clio-pandas:profile_data` (or `clio-pandas:load_data` then
`clio-pandas:profile_data`) once. It reports missing values, dtypes and
distributions in a single pass.

Missing values change what the next step means: a correlation over a column that
is 40% null is not the correlation the user asked for. Say so rather than
silently computing it.

## 4. Compute the specific statistic

Choose one, do not run all three:

- `clio-pandas:statistical_summary` — distribution, outliers, per-column
- `clio-pandas:correlation_analysis` — relationships between numeric columns
- `clio-pandas:hypothesis_testing` — when the user asks whether a difference is
  real, not merely how large it is

## 5. Plot only when a chart says more than a number

- Values over time → `clio-plot:plot_timeseries`
- Relationship between two variables → `clio-plot:scatter_plot`
- Distribution shape → `clio-plot:histogram_plot`

`clio-plot` reads CSV and Excel. For HDF5 or BP5 data, write the slice out with
`clio-hdf5:export_dataset` first rather than trying to point the plot server at
a format it cannot open.

## What not to do

- Do not read a whole dataset to compute one aggregate — Parquet and HDF5 both
  answer aggregate questions without materialising rows.
- Do not report a statistic without saying what the profile showed about
  missing data.
- Do not plot a chart the user did not ask for; a single number is often the
  whole answer.
