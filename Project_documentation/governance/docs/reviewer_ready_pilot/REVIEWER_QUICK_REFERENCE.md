# Reviewer Quick Reference (Phase 5)

*One-page cheat sheet. Use with the full `REVIEWER_GUIDE.md`.*

## Levels (low → high)

`E0` no gate · `E1` context · `E2` internal/impl · `E3` independent/measured · `E4` external + review ·
`ER` human review.

## Risk floor

low → **E1** · medium → **E2** · high → **E3** · critical → **E4** · unknown → **ER**. Only raise, never
lower. No high-risk E0.

## Raise to at least…

| If the claim is… | Minimum |
|---|---|
| medical / financial / legal / regulatory | **E4** |
| performance / reliability / current-state / security | **E3** |
| internal policy / code / API | **E2** |
| time-sensitive / current status | **E3** |
| an action proposal | **E3** (E4 if irreversible/high-impact) + needs approval |
| high-impact recommendation | **E4** |

## Authority in one line

Code → current behavior only. Approved policy → yes; draft/expired → no. User → own preference. **Model /
generated text → never evidence for its own factual claim.**

## Evidence → what it can prove

impl/tests → behavior (not production perf) · telemetry → performance/status · external authority →
regulated/high-impact · attribution → that it was *said*, not that it is *true*.

## Traps → force ≥ E3

self-verification · circular corroboration · fixture-as-telemetry · impl-as-operational · stale
authority · attribution-as-truth.

## Choose ER when

risk/authority/type unknown or rules conflict or a trap fires. ER = "a human decides," the safe default.

## Never

lower below the risk floor · accept self-support at E1/E2 · treat "the source said it" as "it is true" ·
assume internal = authoritative.
