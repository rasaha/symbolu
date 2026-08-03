# Accessibility

Targets WCAG 2.2 AA. Keyboard navigation on all critical paths; visible focus;
skip link; landmarks; semantic tables with scoped headers; graph accessible-list
alternative; dialog focus trap + restoration; aria-live loading/selection
announcements; reduced-motion support; state never conveyed by color alone (glyph
+ label). Automated axe checks run on the catalog and eligibility matrix.

## Measured contrast (evidence-based)

Contrast is programmatically **measured**, not assumed. `scripts/verify-contrast.mjs`
loads the canonical Tailwind tokens, composites the app's `/10` tinted surfaces,
computes WCAG 2.2 relative-luminance contrast ratios for 21 critical pairs (body,
secondary and muted text; links; focus indicator; buttons normal + disabled; table
text/headers; drawer/dialog; all eight status states; error and success surfaces)
and fails below threshold (normal 4.5:1, large 3:1, non-text 3:1). The machine-
readable evidence is `artifacts/contrast-report.json`.

- Token-level contrast verification: **measured** (lowest passing ratio 4.09:1).
- Rendered-browser visual review: supplemental; the four scenario E2E flows render
  every screen in a real browser, full manual visual audit remains a follow-up.
