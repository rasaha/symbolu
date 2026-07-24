# Alignment Protocol

*Phase 8. Does the cited passage support the EXACT claim — right population, timeframe, jurisdiction,
and scope? Implemented in `evidence_assurance/alignment.py`. Entailment (a single 3-way label) does
not capture scope/population/temporal/jurisdiction mismatch; this module adds that structure.*

## Checks

| Check | Question | Signal |
|---|---|---|
| passage-supports-claim | is the evaluated passage the one that supports THIS claim? | observed alignment signal (imperfect NLI proxy) |
| scope | is the claim broader than the passage? | scope-inflation flag (claim-vs-evidence scope) |
| population | cohort evidence applied to an individual? | population metadata (conservative default here) |
| temporal | past evidence generalized to present/future? | publication time vs claim timeframe |
| jurisdiction | law/policy from the wrong jurisdiction? | jurisdiction metadata + completeness |

`aligned = passage_ok ∧ scope_ok ∧ temporal_ok ∧ jurisdiction_ok`. Reason codes:
`EA.PASSAGE_MISALIGNED`, `EA.SCOPE_INFLATION`, `EA.TEMPORAL_MISMATCH`, `EA.JURISDICTION_MISMATCH`.

## Compared methods (Phase 8 requirement)

| Method | Catches passage misalignment? | Catches scope/temporal/jurisdiction? |
|---|---|---|
| keyword overlap | no (overlap high even when misaligned) | no |
| semantic similarity | partial | no |
| **entailment** | partial (passage-level) | **no** — a single label, no scope structure |
| structured scope matching | no (passage) | **yes** |
| **combined alignment (this module)** | yes | yes |

## Why alignment is not subsumed by entailment (H0-5)

Entailment answers "does evidence E entail claim C?" as one label. It does **not** distinguish "E
entails a *narrower* claim than C" (scope inflation), "E is about a *different population/timeframe/
jurisdiction*", or "E was evaluated against the *wrong passage*." The AssertionGate robustness study's
"wrong-passage entailment" and "scope inflation" failures are exactly these — an entailment label of
`supports` on the wrong passage/scope. This module adds the structured checks entailment omits.

## Measured

On `ea_corpus_v1`, the combined alignment check flags **100% (104/104)** of MISALIGNED-gold cases as
not-aligned, including scope-inflation (overstated) and temporal cases that a bare entailment label
(`supports`) would pass. The ~10% alignment-signal noise in the corpus models imperfect real NLI;
the structured scope/temporal/jurisdiction checks recover cases the noisy signal alone would miss.
