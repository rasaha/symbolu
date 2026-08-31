# Final Contrast Classification (C3)

The previous report's lowest pair was **4.09:1**, classified as *large* text — an
unjustified use of the 3:1 threshold for what is really small muted/disabled text.
This is resolved by **raising the token**, not by reclassifying.

## The former 4.09 pair

| Field | Before | After |
|-------|--------|-------|
| Pair | button text (disabled) on surface-2 | same |
| Foreground token | `ink-3` `#727d90` | `ink-3` `#828da0` (brightened) |
| Background | `surface-2` `#161c2a` | `surface-2` `#161c2a` |
| Computed ratio | 4.09:1 | **5.08:1** |
| Content classification | `large` (3.0) — unjustified | `normal_text` (4.5) |
| Rendered typography | 14px / 600 | 14px / 600 |
| Pass rationale | relied on large-text exception | meets normal-text 4.5 outright; **no exception relied upon** |

`ink-3` is the muted/tertiary/disabled text token. Brightening `#727d90 → #828da0`
lifts **every** pair that uses it — including the second-lowest pair, *muted text on
card* (was 4.35 *large* → now ~5.06 *normal_text*) — above the 4.5 normal-text
threshold. No pair in the set now uses a `large_text` or
`inactive_component_exception` classification.

## Result

- Total pairs: **34** · failures: **0** · classification errors: **0**
- Lowest passing ratio: **4.69:1** (deterministic-service state pill, `normal_text`)
- Lowest **normal-text** ratio: **4.69:1** (≥ 4.5 ✓)
- Non-text pairs (accent/link, focus indicator) are `non_text_ui` / `focus_indicator`
  at 3.0, and even so measure **8.03:1** — they clear normal-text 4.5 too.

## Report schema (v2) and enforcement

Every pair now carries `foreground`, `background`, `content_type`, `font_size_px`,
`font_weight`, `ratio`, `required_ratio`, `pass`, `rationale`. Content types:
`normal_text` (4.5), `large_text` (3.0, requires ≥24px or ≥18.66px bold),
`non_text_ui` (3.0), `focus_indicator` (3.0), `inactive_component_exception`
(no minimum, rationale required).

`npm run verify:contrast` FAILS on: missing/unknown content type; ratio below the
declared threshold; normal text using a 3:1 threshold; large-text classification
without qualifying size/weight; inactive exception without a rationale; missing
foreground/background; or a **stale** committed report (drift from freshly computed;
regenerate with `-- --write`). Enforced by `tests/contrast.test.ts` (18 tests) and
the CI `contrast-classification` gate.
