# Accessibility Plan (P3D)

P3D inherits the P3C accessibility baseline and extends it to the seven new screens.

## Automated

- **axe** (`vitest-axe`) runs against each new screen's rendered output in the
  component suite; violations fail the `accessibility-suite` CI job.
- **Measured contrast** (`scripts/verify-contrast.mjs`) now evaluates **34 pairs**,
  including 13 P3D semantic pairs (selected primary/fallback, eligible-not-selected,
  permission proposed/excluded, fallback available/none, replay match/mismatch, plan
  added/removed/changed, what-if active). Every pair meets its WCAG 2.2 threshold;
  the lowest passing ratio is **4.09:1** (normal-text threshold 4.5 is met by all
  normal-text pairs; 4.09 is a non-text/large pair above its 3.0 threshold). The
  report is committed at `artifacts/contrast-report.json` and re-verified in CI
  (`contrast-verification`).

## Structural

- Each screen has a single `<h1>`/heading landmark and the shared scenario `<nav>`
  labelled "Scenario sections".
- Data tables (ranking, comparison) use real `<table>`/`<th>` semantics with row and
  column headers.
- Expand/collapse controls (score breakdown) are real `<button>`s with accessible
  names ("Show breakdown").
- The what-if perturbation control is a labelled `<select>` ("Perturbation
  (bounded)"), keyboard-operable, with no free-form text trap.
- State is conveyed by text/token pairs, not colour alone; semantic tokens carry an
  accessible text label in every state chip.

## Not colour-only

Every domain state (plan state, selection state, fallback state, diff category,
replay match) is rendered as an explicit text label alongside its colour token, so
the information survives greyscale and colour-blind viewing.
