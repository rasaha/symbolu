# Ranking View Design

**Screen:** `src/features/ranking/RankingScreen.tsx` · **Route:** `/scenarios/:id/ranking`
· **Operations:** `get_scenario_ranking`, `explain_ranking`.

## Intent

Present, per role, the backend's canonical ranked candidate list with a transparent
score decomposition — never re-scoring or re-sorting in the browser.

## Rendering rules

- **Canonical order is authoritative.** Rows are rendered in the exact order the API
  returns; the first table row's `rank` equals the API's first candidate's `rank`.
  No client-side sort/filter reorders candidates.
- **Score decomposition** is shown on demand ("Show breakdown"), listing each
  criterion's contribution in **basis points (bp)** exactly as returned. The frontend
  does not compute or normalise contributions.
- **Tie groups** from `tie_group` are surfaced so equal-rank candidates read as
  deliberate ties, not arbitrary ordering.
- **Ranking fingerprint** is displayed so a ranking can be correlated with replay and
  comparison views.
- A **reset** control returns any expanded breakdown to the collapsed default; it
  changes presentation only, never the data.

## Boundary

All numbers originate from `decodeRanking` (fail-closed) over the untyped envelope
`result`. Missing required fields throw `DecodeError` rather than rendering a guess.
