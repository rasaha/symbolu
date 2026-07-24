# Reference EvidenceAssurance Component (Phase 13)

*`evidence_assurance/assurance.py`; evaluated by `eval_assurance.py` → `eval_results/assurance_v1.json`.
Composes the layers — provenance, independence, alignment, counterevidence, freshness, authority —
into ONE of the eleven `EvidenceState` dispositions. It is the component the AssertionGate adapter
(Phase 14) consumes. It sees OBSERVED metadata + layer verdicts only, never TRUE latent state.*

## Disposition precedence

Most safety-critical first; the first matching rule wins.

| # | Condition (observed / layer verdict) | Disposition |
|---|---|---|
| 1 | passage does not support this claim, or wrong jurisdiction | `MISALIGNED` |
| 2 | credible counterevidence found (not false-conflict noise) | `CONFLICTED` |
| 3 | provenance untrusted — fabricated diversity / missing provenance (independence = UNKNOWN) | `INDETERMINATE` |
| 4 | non-authoritative source in a high/critical-risk decision | `AUTHORITY_MISMATCH` |
| 5 | evidence outdated / superseded (old years, or provenance says superseded) | `STALE` |
| 6 | single underlying source (independence = DUPLICATE) | `DEPENDENT` |
| 7 | not duplicate, but effective independent support ≤ 1 | `INSUFFICIENT` |
| 8 | supported, but claim broader than evidence (scope inflation only) | `VERIFIED_WITH_LIMITATIONS` |
| 9 | aligned, independent, authoritative, fresh, uncontradicted | `VERIFIED` |

Two precedence choices carry the study's central design decisions:

- **Staleness owns old publication years (step 5), not misalignment (step 1).** Temporal *misalignment*
  and *staleness* are keyed off the same year signal in this corpus; counting old years at step 1
  would swallow every `STALE` case into `MISALIGNED`. Step 1 therefore excludes the temporal check and
  lets step 5 own it.
- **Single-source ⇒ DEPENDENT (step 6) is the correlated-failure gate.** An aligned-but-wrong claim
  resting on one source lands here exactly like a clean dependent claim — because from observed
  metadata they are identical until counterevidence surfaces the contradiction. `DEPENDENT` is **not**
  delivered as positively supported, so the aligned-but-wrong claim does not escape. This is *why* the
  component reaches zero correlated-failure escape.

## Results (ea_corpus_v1_1, 624 cases)

| Endpoint | Value | |
|---|--:|---|
| **correlated-failure escape** | **0.000** | primary safety — no aligned-but-wrong claim delivered as supported |
| **overall escape** | **0.000** | nothing gold-unsupported delivered as supported |
| **false block** | **0.114** | co-primary — gold-supported cases refused |
| disposition exact accuracy | 0.768 | vs 8-way gold |

Against the Phase-12 baselines: the component matches the safest composites on escape (0.000) while
**cutting false-block from 0.432 to 0.114** — because overstated-but-supported cases now resolve to
`VERIFIED_WITH_LIMITATIONS` (qualified delivery) instead of being refused as misaligned.

### The false-block is noise, not design

All 15 false-blocked cases (5 gold `VERIFIED`, 10 gold `VERIFIED_WITH_LIMITATIONS`) are misrouted to
`MISALIGNED` by the **10% observed alignment-signal noise** the corpus injects to model an imperfect
NLI proxy (`observed_alignment_signal` flips on 1-in-10 cases). 15 / 132 = 0.114 — the false-block
rate is *exactly* this noise floor. No supported case is refused for a structural reason; the residual
is the irreducible cost of a noisy passage signal, and it is what a better NLI proxy (or human
adjudication on flagged cases) would recover — quantified here, not hidden.

### The residual disposition error is the correlated-failure boundary

`REJECT_EVIDENCE_STATE` gold (the correlated-failure / adversarial trap) is labeled
`CONFLICTED` (66, where counterevidence surfaced the contradiction), `MISALIGNED` (25, where the noisy
passage signal flagged it), or `INDETERMINATE` (13, where provenance was untrusted) — **never
`VERIFIED`**. The component cannot always name the failure `REJECT` from observed metadata alone, but
it never delivers it. This is the honest boundary established in Phase 4 and `INDEPENDENCE_MODEL.md`:
correlated failure on a single wrong source is *safely refused* even when it cannot be *precisely
labeled*. Naming it exactly requires either discoverable counterevidence or information
(model/methodological independence) that is not present in evidence metadata.

## What this component is not

It is a **reference rule composition**, not a learned model and not a production integration. It runs
only over the frozen corpus + local fixtures; it makes no provider calls and performs no live
retrieval. Enforcement is off. Its job is to establish whether the layered, provenance-aware
disposition is *achievable and honest* — later phases ablate it (18), stress it under missing metadata
(16), and price it (17).
