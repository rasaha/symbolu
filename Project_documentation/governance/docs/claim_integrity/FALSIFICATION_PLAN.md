# Falsification Plan (Phase 5)

*Preregistered before any outcome-bearing evaluation. The core hypothesis is stated with explicit
rejection conditions; the eighteen nulls below are the tests. Negative and null results are the
expected default and will be reported plainly. Frozen before Phase 26; the evaluation protocol
(Phase 25) may only narrow, never widen, these.*

## Core hypothesis (H1)

> A meaningful fraction of downstream governance failures originate **before** evidence evaluation,
> because claim decomposition silently changes the semantic content of the original output. A reliable
> claim-integrity stage must therefore preserve assertion content, polarity, quantifier scope,
> uncertainty, attribution, conditions, exceptions, temporal limits, causal direction, numerical
> bounds, and domain qualifiers.

**H1 is rejected if** sentence splitting performs as well as richer decomposition; decomposition errors
rarely affect downstream decisions; EvidenceAssurance/AssertionGate stay robust despite decomposition
noise; semantic preservation is achievable by trivial rules; a distinct component adds no value beyond
existing parsing; or the component creates more ambiguity/fragmentation than it resolves.

## Preregistered thresholds (frozen)

- **Material semantic-drift rate** — fraction of extracted claims whose meaning differs materially from
  the source span (per the five preservation properties, Phase 2).
- **Unsafe downstream delivery** — the primary safety endpoint: a decomposition that causes the thin
  AssertionGate to deliver-as-supported a claim that gold would withhold (Phase 18).
- "Materially lower" = a method's endpoint is lower than the comparator's by a margin that holds under
  the paired test (Phase 26), not a single-point difference.

## Null hypotheses

| H0 | Null claim | Experiment | Primary endpoint | Reject H0 if | Kill ClaimIntegrity if | Consequence |
|---|---|---|---|---|---|---|
| 1 | sentence splitting ≈ semantic decomposition | A/B vs P on all partitions | semantic-drift + unsafe delivery | P materially lower on both | they tie | decomposition not load-bearing |
| 2 | dependency parsing ≈ dedicated component | D vs P | drift | P materially lower | tie | parser suffices |
| 3 | OpenIE / SRL sufficient | E/F vs P | drift + completeness | P preserves dimensions OpenIE structurally drops | tie | triple extraction suffices |
| 4 | LLM extraction alone sufficient | I/J vs P | drift + unsafe delivery | P matches/beats at lower variance | LLM dominates | use the LLM, drop the component |
| 5 | qualifier preservation immaterial downstream | qualifier-drop perturbation (Phase 19) | unsafe delivery Δ | dropping qualifiers changes delivery materially | no downstream change | drop qualifier handling |
| 6 | negation/modality errors too rare to matter | frequency × severity on corpus | unsafe delivery from 3/7/35 | they occur AND flip delivery | negligible | fold into a cheap check |
| 7 | decomposition errors don't change EvidenceAssurance | perturbation → EA adapter | EA evidence-state Δ | material EA change | none | EA is robust to upstream drift |
| 8 | decomposition errors don't change AssertionGate | perturbation → gate adapter | delivery Δ | material delivery change | none | gate is robust to upstream drift |
| 9 | over-splitting safer than under-splitting | O vs N downstream | unsafe delivery + false reject | asymmetry demonstrated | symmetric | informs split policy |
| 10 | under-splitting safer than over-splitting | N vs O downstream | unsafe delivery + false reject | asymmetry demonstrated | symmetric | informs split policy |
| 11 | simple semantic-equivalence checks sufficient | M vs P equivalence | drift-detection F1 | P catches drift M misses (esp. type 50 vs inversions) | tie | ship the simple check |
| 12 | uncertainty propagation adds no value | with/without ambiguity state | unsafe delivery on ambiguous | propagation cuts unsafe delivery | none | drop uncertainty propagation |
| 13 | learned extraction ≫ deterministic | R vs P | drift + unsafe delivery | R materially better | R wins big | prefer the learned system |
| 14 | distinct component unnecessary | P vs best baseline overall | safety frontier | P on the frontier, no baseline dominates | a baseline dominates | reject the component |
| 15 | human disagreement makes gold too unstable | two-annotator agreement (Phase 7) | agreement / unresolved rate | agreement high enough on material dimensions | agreement collapses | ground truth unusable |
| 16 | decomposition not a major downstream-failure contributor | attributable-failure share (Phase 18/19) | share of unsafe deliveries traceable to decomposition | share is material | negligible | not a governance function |
| 17 | "preserve original sentence" trivially safer & equally useful | A vs P downstream | unsafe delivery + evaluability | P beats "preserve whole" on evaluability without raising unsafe delivery | preserve-whole ties | avoid decomposition entirely |
| 18 | cost of reliable decomposition outweighs safety value | Phase 21 cost vs Phase 18 benefit | cost per unsafe-delivery avoided | benefit justifies cost at high risk | cost dominates everywhere | high-risk-only or reject |

## Anti-circularity & honesty commitments

- **Ground truth (Phase 7) is not generated from the ClaimIntegrity implementation.** Two independent
  annotation procedures + adjudication; alternate valid decompositions are recorded, not coerced to one
  gold sequence; irreducible ambiguity is kept as ambiguity.
- **ADVERSARIAL_SCOPE (Phase 6) exists to make the component lose** — cases engineered to induce drift.
  Cases where "preserve whole sentence" is genuinely safest are included.
- **Baselines are dev-tuned; the reference component is not tuned on the eval split.**
- **The decisive realism test is H0-16 (downstream attributable share) crossed with H0-1 (sentence
  splitting).** If sentence splitting causes no more unsafe delivery than the full component, the
  component is not justified regardless of its intrinsic drift numbers.
- **A structural-honesty note:** the reference component and the perturbations are deterministic
  fixtures. The *rates* will not transfer to live text; the *ordering and mechanism* claims (which
  dimensions are fragile, whether downstream layers absorb drift) are what the study puts weight on.
  This limit is stated now, not discovered later.

## What a clean win vs a clean null looks like

- **Win:** P has materially lower semantic drift AND lower unsafe downstream delivery than sentence/
  clause splitting; a material share of unsafe deliveries is attributable to decomposition; qualifier/
  negation/scope preservation each change downstream outcomes; no unsafe high-risk subgroup; no
  invented claims; simple comparators do not match it on the safety endpoint.
- **Null (equally publishable):** sentence splitting ties on unsafe delivery; downstream layers absorb
  the drift; the attributable share is negligible; a simple comparator matches P. The architectural
  decision (Phase 28) would then be REDUCE, MERGE, PRESERVE-WHOLE, or REJECT — reported without spin.
