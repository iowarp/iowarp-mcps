# Evals - choosing-the-right-chart

Baseline scenarios: run each WITHOUT the skill to capture the gap, then WITH it
to confirm the gap closes. Rubric is pass/fail per bullet.

## S1 - chart follows the question

Setup: Prompt: "I want to show how throughput compares across four filesystems."

Expected:

- A bar chart is chosen, not a line, and the reason given is that the x axis is
  categorical.
- The y axis is not truncated.

## S2 - a scale that is honest

Setup: Prompt: "plot runtime against problem size; the sizes span 1e3 to 1e9,
and one measurement is zero."

Expected:

- A log x axis is recommended for the span.
- The zero value is flagged as impossible to show on a log axis rather than
  silently dropped.
- The answer says the caption must state the scale.

## S3 - colour that does not invent features

Setup: Prompt: "which colour map for a continuous temperature field?"

Expected:

- A perceptually uniform map is recommended and rainbow explicitly rejected,
  with the banding artefact named.
- For a difference field, a diverging map centred on zero is recommended.

## Baseline failure modes to watch for (RED)

- Lines drawn across categorical x axes.
- Bar charts with truncated y axes.
- Accepting a default bin count without testing another.
- Log axes applied to data containing zeros with no comment.
- Rainbow colour maps on continuous data.
- Correlation coefficients reported with no significance.

## Trigger record (2026-08-21)

Ran through `evals/trigger_eval.py`, which loads the skill plugins into the
Agent SDK with an empty `setting_sources` and only the Skill tool allowed, so
selection is measured without the operator's own configuration influencing it.

Prompt: "Which chart should I use to compare four filesystems?"

This skill fired, and no sibling fired alongside it. Across the suite: 20 of 20
skills selected correctly on their own prompt, and 3 control prompts outside the
kit fired nothing.

Selection is checked. Whether the skill improves the final answer, versus an
agent working without it, is still not measured.

