# Contrast Verification (C4)

Token-level contrast is **measured**, not asserted. `npm run verify:contrast`
(`scripts/verify-contrast.mjs`) loads the canonical Tailwind tokens, composites the
app's `/10` tinted surfaces, computes WCAG 2.2 relative-luminance contrast ratios,
compares each pair to its threshold, prints a table, writes
`artifacts/contrast-report.json`, and fails on any violation or missing required
pair.

- Pairs measured: **21** (body / secondary / muted text; link+focus indicator;
  buttons normal + disabled; table body + header; drawer/dialog; all eight status
  states — eligible/ineligible/indeterminate/invalid/authority/review/governance/
  deterministic; error text + title; success/readiness).
- Thresholds: normal 4.5:1, large 3:1, non-text/focus 3:1.
- Failures: **0**. Lowest passing ratio: **4.09:1** (disabled button, large).

Several original state tokens failed measurement and were brightened to pass (and
the workflow-graph hex map was synced). Token-level contrast verification is
**measured**; full rendered-browser visual review remains supplemental (the four
scenario E2E flows render every screen in a real browser). axe alone does not
verify CSS color contrast and cannot in jsdom.
