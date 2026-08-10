# Atomicity Protocol (Phase 12)

*`claim_integrity/atomicity.py`. Defines when a decomposition is correctly atomic — and commits to the
position that **maximum splitting is not optimal**. Over-splitting and under-splitting are both
failures, measured separately and never netted against each other.*

## Definitions

- **Atomic claim** — one independently evaluable proposition. Evidence can be sought for it without
  dragging in a second, separable assertion.
- **Composite claim** — two or more independently evaluable propositions in one unit (should split).
- **Dependent claim** — a proposition that cannot be evaluated without another (pronoun antecedent,
  multi-hop premise); must be *chained*, not severed.
- **Contextual claim** — a proposition whose meaning depends on a modifier (qualifier, exception,
  attribution); the modifier must ride with it, so it must be *preserved*, not split off.
- **Non-assertive text** — questions, asides, rhetorical framing; must **not** be extracted as a claim.
- **Duplicate claim** — the same proposition stated twice; must be extracted **once**.
- **Implied-but-unstated claim** — a proposition a reader might infer but the text does not assert;
  must **not** be produced (that is an INVENTED_CLAIM).

## The policy: split-vs-preserve is type-dependent

`atomicity.type_expectation(claim_type)` returns one of `atomic | preserve | split | chain |
no_extract` (from the claim taxonomy). A method that splits maximally violates the `preserve` types
(attributed, uncertain, comparative, numerical, temporal, jurisdictional, population-specific,
conditional, exception-bearing, partial-negation, disjunction, citation-dependent, summary,
evidentiary-status, quoted) — 14 of 30 types must be held together. Only `conjunction` splits and
`multi_hop` / `procedural` chain.

`assess(example, produced)` therefore returns both:
- `verdict` — `atomic_ok` / `over_split` / `under_split` against the gold count **and any acceptable
  alternate count** (so a valid finer/coarser decomposition the annotators both accepted is not
  penalized); and
- `preserve_policy_violation` — True if a `preserve`/`no_extract` gold type was split even when the
  count happened to match.

## Measured (metrics.py, over/under reported separately)

| Method | over_split examples | under_split examples |
|---|--:|--:|
| Q_oracle | 0 | 0 |
| B_sentence_split / P_claim_integrity | 0 | 78 |
| A_preserve_whole | 0 | 312 |
| F_openie / O_aggressive_split | 312 | 0 |

The two error directions are genuinely different failures:

- **Over-splitting** (OpenIE, aggressive) detaches modifiers and shatters a single contextual claim —
  it manufactures INVENTED-looking fragments and strips scope. Here it co-occurs with a 0.295 invented-
  claim rate.
- **Under-splitting** (preserve-whole, and the component/sentence-split on the 78 ADVERSARIAL
  conjunctions) merges independent claims — it hides one claim behind another but **drops nothing**, so
  evidence evaluates the merged unit conservatively.

## The stance this protocol takes

Because over-splitting *strips scope and invents fragments* while under-splitting *only merges*, the
protocol treats **under-splitting as the safer error** when the two must be traded — which is exactly
what the reference component does on ADVERSARIAL_SCOPE (it keeps a conjunction whole rather than risk
detaching `unless monitored`). Whether that stance actually reduces *unsafe downstream delivery* — as
opposed to merely reducing text-drift — is not assumed here; it is the H0-9/H0-10 question the
downstream-impact experiment (Phase 18) tests directly. This protocol only fixes the definitions and
the measurement; the safety verdict is earned downstream.
