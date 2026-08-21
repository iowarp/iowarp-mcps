---
name: cleaning-and-validating-a-dataset
description: Use when data quality is in question, results look wrong, values are missing or duplicated, or before statistics are computed. Triggers on "clean this data", "missing values", "outliers", "validate". Not for producing a figure; use summarizing-and-plotting-results.
clio-kit:
  bundle: clio-analysis
  servers: clio-pandas
  provenance: designed
  eval-status: scenarios-recorded
---

# Clean a table without inventing data

Every repair here changes the numbers that come out. Look before repairing, and
say what was done.

## Profile first, always

`clio-pandas:profile_data` — shape, types, missing values, distributions, quality
checks. On a raw CSV, `clio-pandas:profile_csv` answers the same first questions
without loading it.

Read three things before touching anything: **how much is missing and where**,
**whether dtypes match what the columns mean**, and **whether ranges are
physically possible**.

## Missing data: how it is missing decides the fix

`clio-pandas:handle_missing_data` takes two separate arguments, and conflating
them is the usual first failure. `strategy` is one of `detect`, `impute`,
`remove` or `analyze`, and defaults to `detect`, which only reports. `method` is
the imputation itself: `mean`, `median`, `mode`, `forward_fill`,
`backward_fill`, `interpolate`. Passing `strategy="median"` fails with "Unknown
strategy"; the call you want is `strategy="impute", method="median"`.

The methods are not interchangeable.

- **Scattered at random** — imputation is defensible. Median over mean when the
  column is skewed, because a mean is dragged by the outliers you have not
  removed yet.
- **In runs** — a sensor dropout. Forward-fill or interpolate; a mean invents a
  plateau at a value that was never measured.
- **Concentrated in one group** — imputing hides a systematic problem. Something
  about that group failed to record, and the fill will look like a real finding.
- **Most of a column** — drop the column. A column that is 80% imputed is mostly
  your fill value, and any correlation involving it is an artefact.

Dropping rows is honest and biased: it silently removes exactly the cases with
missing data, which are rarely a random sample.

## Duplicates and outliers

`clio-pandas:clean_data` removes duplicates, detects outliers via IQR or Z-score,
and optimises dtypes in one pass.

Outlier *detection* is not outlier *removal*. An extreme value can be a sensor
fault or the event the whole run was about. Look at flagged rows before deleting
them. Z-score assumes roughly normal data and finds nothing useful on a skewed
distribution; IQR does not make that assumption and is the safer default.

Duplicate rows are sometimes real — two identical measurements at different times
where the timestamp was not kept. Check what makes a row unique before deduping.

## State the rules and check them

`clio-pandas:validate_data` checks columns against explicit rules: min/max range,
type, nullability, uniqueness, regex. This is stronger than eyeballing a profile,
because it is a claim that can fail later on new data.

Write the rules from what the data means: a fraction is in [0, 1], a temperature
in Kelvin is not negative, an ID is unique and non-null. A validation rule that
encodes physics catches the corrupt file that a statistical check accepts.

## Types and memory

`clio-pandas:optimize_memory` reduces footprint through dtype optimisation and
suggests chunking. Worth running before an expensive operation on a wide table.

Check what it did. A column downcast to a narrower integer type will silently
overflow if later values exceed the new range, and an ID stored as a float has
already lost precision.

## Filtering

`clio-pandas:filter_data` supports comparison, membership, pattern matching and
null checks across several columns. Filter before aggregating, not after: an
average over rows you meant to exclude is wrong in a way that looks fine.

## Then say what you did

Every step above changes the result. Report which columns were imputed and how,
how many rows were removed and why, and what was excluded. A cleaned dataset
with no record of the cleaning is not reproducible.

## What not to do

- Do not impute before knowing whether the gaps are random, in runs, or grouped.
- Do not mean-fill a skewed column.
- Do not delete outliers without looking at them.
- Do not deduplicate before knowing what identifies a row.
- Do not report results from cleaned data without saying what was cleaned.
