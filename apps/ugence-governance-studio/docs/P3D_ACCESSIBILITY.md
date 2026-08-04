# P3D Accessibility

Keyboard navigation across ranking rows and expandable breakdowns; semantic
score-contribution, assignment, permission and fallback tables (scoped headers,
captions); non-color-only selected/not-selected/fallback states (glyph + label);
aria-live replay and what-if status; reset control; reduced-motion honored.
Contrast is measured for the new P3D state pairs (34 total token pairs) by
`npm run verify:contrast`. Ordinary body text is never reclassified as large text
to lower a threshold.
