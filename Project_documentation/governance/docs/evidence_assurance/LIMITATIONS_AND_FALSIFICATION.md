# Limitations & Falsification Outcomes (Phase 23)

*Every preregistered null hypothesis (`FALSIFICATION_PLAN.md`, H0-1…15) reported against the frozen
results — rejected, not rejected, or not decisively testable on this corpus. Negative and null results
are reported plainly; they were the expected default.*

## H0 outcomes

| H0 | Null claim | Outcome | Evidence |
|---|---|---|---|
| 1 | source count ≈ independence analysis | **Rejected** | count/`B` escapes 1.000 of trap; independence 0.000 |
| 2 | domain diversity ≈ provenance diversity | **Rejected** | `C_diversity` 1.000; provenance/independence 0.000 |
| 3 | grounding+entailment+freshness sufficient | **Rejected** | signal-only baselines 0.667–1.000 vs component 0.000 |
| 4 | counterevidence adds no value | **Rejected (bounded)** | it cuts escape under fabrication (0.250 vs 0.500) and surfaces 66 CONFLICTED; on benign data its marginal escape-reduction is 0 (redundant tell) |
| 5 | alignment ⊆ entailment | **Rejected** | alignment flags 104/104 MISALIGNED; a single entailment label cannot express scope/temporal/jurisdiction |
| 6 | provenance graphs too incomplete to use | **Rejected** | escape stays 0.000 through 70% missingness; degrades to abstention, not escape |
| 7 | independence over-blocks | **Rejected** | component false-block 0.114 ≤ 0.25 threshold, and it is entirely NLI noise |
| 8 | simple abstention ≈ EA | **Rejected** | `H_always_block` reaches 0 escape only at false-block 1.000; component 0.114 |
| 9 | thin AssertionGate captures it all | **Rejected** | end-to-end delivery-level escape 0 requires the EA disposition; the gate has no evidence logic |
| 10 | dedicated EA layer unnecessary | **Rejected (qualified)** | component is on the safety frontier (0.000 / 0.114); no baseline dominates it on both endpoints — but `K_independence` matches it on *this* benign corpus (see below) |
| 11 | more retrieval paths = cost only | **Rejected** | path fabrication is a load-bearing attack vector; path-collapse detection catches trap cases missing other tells |
| 12 | multiple models = false diversity, undetectable | **Not rejected (honest limit)** | model/methodological independence is NOT in evidence metadata; types 23/30 reported UNKNOWN/INDETERMINATE, and the no-tell case (S23) escapes 1.000 |
| 13 | freshness+authority+count rule suffices | **Rejected** | `S_learned_comparator` (a fixed-weight rule over those signals) escapes 1.000 |
| 14 | counterevidence contradiction-noise > safety | **Rejected** | false-conflict noise never causes an escape; it costs abstention, not safety |
| 15 | EA needs oracle provenance (not deployable) | **Rejected — the decisive test** | on realistic noisy metadata the component reaches 0.000 escape; it does NOT require oracle provenance |

**Score:** 13 of 15 nulls rejected; H0-4 rejected only in the bounded/adversarial sense; **H0-12 not
rejected** and stands as the study's fundamental limit.

## The two limits the study does not overcome

1. **No-tell correlated failure (H0-12).** When a correlated failure leaves no observable trace — model
   consensus on a shared false premise, training-data contamination, a perfectly-fabricated provenance
   record with an aligned passage and no counterevidence — the component escapes 100% (S23). This is
   not a tuning gap; it is a property of *any* metadata-based method. The dependence and the error live
   outside the evidence record. Only independent human or external verification addresses it.

2. **Benign-corpus redundancy (qualifies H0-10).** Because every trap case in `ea_corpus_v1_1` carries
   multiple tells, the primary endpoint is reachable on benign data by independence-checking alone
   (2 probes of 18). We do not hide this. The full stack earns its cost under **adversarial metadata
   fabrication** (independence-alone escapes 0.500 there; full stack 0.000) and by covering the
   **non-correlated** failure states (stale, conflicted, misaligned, authority) that independence alone
   misses (overall escape 0.366 → 0.000). A study on a corpus where trap cases carried a *single* tell
   would show independence-alone failing — that corpus is the natural next step (below).

## Other limitations (scope honesty)

- **Deterministic fixtures, not live data.** No provider calls, no live retrieval; observed signals are
  modeled (10% NLI noise, ~92% counterevidence recall, keyed false-conflict). Real NLI/retrieval error
  is not identical to the injected model. The *shape* of the findings should transfer; the exact rates
  will not.
- **Single corpus, constructed by us.** Gold is two-annotator with shared hard precedence; the soft
  tail (STALE×DEPENDENT) carries 8.3% disagreement. External corpora with independent annotation are
  needed to confirm the disposition accuracy (0.768) is not corpus-specific.
- **Population/methodological checks are conservative placeholders.** `population_ok` defaults true;
  methodological independence is unobservable. These are declared, not solved.
- **No enforcement, no production integration.** By design (the track's constraints). Adoption would
  require a shadow-mode rollout with the missing-metadata abstention rate wired to a data-quality alarm.
- **The v1_1 gold fix was ours to make.** The corpus is not externally validated; the AUTHORITY_MISMATCH
  gate bug (CORPUS_CHANGELOG.md) shows the annotator logic needed correction — a reminder that the gold
  is engineered, not observed.

## What a follow-up should test

- A **single-tell** trap corpus, to force each layer to be individually load-bearing and re-run the
  minimal-subset analysis (expected: independence-alone fails, unlike here).
- **Real NLI + retrieval** back-ends replacing the noise model, to measure true false-block and
  counterevidence recall.
- **Human verification on the no-tell residual**, to quantify how much of the S23 ceiling external
  checking actually recovers.
