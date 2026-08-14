---
name: analyzing-seismic-waveforms
description: Inspects SAC waveform archives and analyses earthquake catalogs, keeping the two apart since one holds ground-motion traces and the other holds event lists. Use when working with SAC files or archives, seismic traces, station data, earthquake catalogs, b-values, or magnitude completeness.
---

# Waveforms and catalogs are different data

Two servers here answer questions about earthquakes, and they take completely
different input. Handing one the other's data fails in confusing ways.

- **`clio-sac`** reads **waveforms** — SAC files or TAR archives of them, holding
  ground motion sampled over time at a station.
- **`clio-seismic`** reads an **earthquake catalog** — a saved list of events with
  locations, times and magnitudes.

A catalog is not derived from waveforms by these tools. If you have waveforms and
the question is about b-values, the catalog is a separate input you do not have
yet.

## Waveforms

**1. Look inside the archive.** `clio-sac:inspect_archive` summarises a SAC file
or TAR archive: member count, a sample of names and sizes, and the inferred
stations. Do this first — an archive can hold hundreds of traces, and station
coverage decides which questions are answerable.

**2. Get the numbers.** `clio-sac:compute_trace_statistics` returns per-trace
amplitude statistics (min, max, mean, std, peak_abs) with header metadata:
`npts`, `delta_s`, `begin_s`, `end_s`.

The header fields matter more than the amplitudes. `delta_s` is the sample
interval — traces with different `delta_s` are not directly comparable, and
comparing peak amplitudes across stations without accounting for instrument
response compares instruments as much as ground motion.

**3. Plot.** `clio-sac:plot_traces` writes a PNG with traces
amplitude-normalised and vertically offset. **Normalised** is the key word: the
figure shows shape and timing, not relative size. Do not read amplitude
comparisons off it — that is what step 2 is for.

## Catalogs

**`clio-seismic:analyze_sequence`** computes the descriptive statistics of a saved
catalog: completeness magnitude (Mc), the Gutenberg-Richter b-value with
uncertainty, and the largest events.

Two things to carry into any interpretation:

- **Mc is a property of the network, not the earth.** Below it, small events were
  not detected — the catalog is incomplete by construction. A b-value fitted
  including events below Mc is biased low, and the drop-off beneath Mc is a
  detection artefact, not physics.
- **The b-value's uncertainty is reported for a reason.** It narrows with event
  count. Comparing two b-values whose intervals overlap is not a difference, and
  a b-value from a short catalog carries an interval wide enough to make most
  comparisons meaningless.

**`clio-seismic:plot_sequence`** renders the three-panel figure: epicenter map
sized by magnitude and coloured by time, the Gutenberg-Richter distribution, and
the sequence over time. Read the map for spatial extent, the distribution for
whether the fit is sound, and the time panel for whether the sequence is a
mainshock-aftershock pattern or a swarm.

## What not to do

- Do not pass waveform files to the catalog tools, or a catalog to the waveform
  tools.
- Do not compare peak amplitudes across stations without accounting for
  instrument response.
- Do not read relative amplitude off `plot_traces` — the traces are normalised.
- Do not compare traces with different `delta_s` without resampling.
- Do not interpret a b-value without Mc and the uncertainty.
- Do not read the roll-off below Mc as a physical result.
