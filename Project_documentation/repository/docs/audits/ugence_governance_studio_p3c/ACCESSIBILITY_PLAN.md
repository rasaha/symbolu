# Accessibility Plan (WCAG 2.2 AA target)

- Keyboard navigation across all critical paths; visible focus (`:focus-visible`).
- Skip link to main content; semantic landmarks (`header`, `main`, `nav`, `footer`).
- Graph has a synchronized accessible node/edge list; state is never color-only
  (every status carries a glyph + accessible label).
- Explanation drawer is a `role="dialog"` with `aria-modal`, Escape-to-close,
  focus moved in on open and restored on close.
- Tables use `scope`ed headers and captions; matrix cells carry SR-only condition
  descriptions.
- `aria-live` regions announce loading and selection changes.
- `prefers-reduced-motion` honored globally.
- Automated axe checks (jsdom) on the catalog and eligibility matrix; color-contrast
  validated by the design tokens (axe color-contrast cannot run in jsdom and is
  covered by the token palette + manual review).
