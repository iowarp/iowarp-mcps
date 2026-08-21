# Evals - analyzing-seismic-waveforms

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - waveforms are not a catalog

Setup: A TAR of SAC files. Prompt: "what's the b-value for this sequence?"

Expected:

- The answer states that b-value needs an earthquake catalog, which SAC
  waveforms are not, and that the catalog is a separate input.
- The catalog tools are not called with a waveform path.

## S2 - amplitudes and the normalized plot

Setup: A SAC archive across several stations. Prompt: "which station saw the
strongest shaking?"

Expected:

- `compute_trace_statistics` is used for amplitudes, not `plot_traces`.
- The answer states that `plot_traces` normalizes, so relative amplitude cannot
  be read off the figure.
- Instrument response is raised as a caveat on cross-station comparison.

## S3 - completeness before interpretation

Setup: A catalog. Prompt: "is the b-value unusually low?"

Expected:

- Mc is reported alongside the b-value and its uncertainty.
- The answer states that events below Mc are undetected by construction, so a
  fit including them biases b low.
- A comparison is not declared meaningful when the uncertainty intervals
  overlap.

## Baseline failure modes to watch for (RED)

- Passing waveform files to catalog tools or vice versa.
- Comparing peak amplitudes across stations with no instrument-response caveat.
- Reading relative amplitude off a normalized trace plot.
- Interpreting a b-value with no Mc and no uncertainty.
- Reading the roll-off below Mc as a physical result.
