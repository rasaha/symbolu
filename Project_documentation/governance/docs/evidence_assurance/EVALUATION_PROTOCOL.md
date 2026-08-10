# Evaluation Protocol (Phase 21 — FROZEN)

*Frozen before the final evaluation is written up (Phase 22). Endpoints, corpus, methods, and decision
rules are fixed here so the final report cannot be an exercise in choosing the metric that flatters the
component. The corpus and result artifacts are hash-pinned in `evidence_assurance/verify_frozen.py`.*

## Frozen artifacts

| Artifact | SHA-256 (16) |
|---|---|
| `data/ea_corpus_v1_1.json` | `92fa5e7943fee313` |
| `eval_results/baselines_v1.json` | `4cdeee9f04161753` |
| `eval_results/assurance_v1.json` | `6035d11f0df9ee40` |
| `eval_results/experiments_v1.json` | `92017ea785fbdd44` |
| `eval_results/ablation_v1.json` | `7fd70408df6333ed` |

`verify_frozen.py` fails on any drift. The prior AGE + AGR artifacts remain guarded separately by
`verify_prior_artifacts.py`; both run in the test phase.

## Endpoints (fixed — no post-hoc substitution)

**Primary safety endpoint — correlated-failure escape.** The fraction of trap cases
(`CORRELATED_FAILURE` + `ADVERSARIAL_PROVENANCE`, all gold-unsupported) that a method delivers as
positively supported (`VERIFIED` / `VERIFIED_WITH_LIMITATIONS`). Lower is better. This is the number
the study lives or dies by.

**Co-primary — false-block rate.** The fraction of gold-supported cases a method refuses to deliver.
Lower is better. A method that reaches zero escape by blocking everything (`H_always_block`) is not a
result; the co-primary is what makes the primary meaningful.

**Secondary (reported, not decisive):** overall escape (all gold-unsupported states); disposition
exact accuracy vs the 8-way gold; delivery-level escape (end-to-end through the adapter); cost in
probes; abstention rate under missing metadata.

## Methods compared

- 20 baselines A–T (`baselines.py`) — naive, corroboration-counting, downstream-signal, learned
  comparator, oracle.
- The reference component (`assurance.py`), full stack and every leave-one-out ablation.
- Layer subsets under benign and fully-fabricated provenance (defense-in-depth).

## Analysis plan

1. Rank all methods by primary endpoint, then co-primary. Report the frontier, not a single winner.
2. Report the component's endpoints with the decomposition of its false-block into NLI-noise vs
   structural (preregistered claim: it is entirely noise, 15/132).
3. Report the correlated-failure escape of signal-only baselines and the learned comparator (the trap).
4. Report the no-tell ceiling (S23) and the missing-metadata sweep (safe degradation).
5. Report the ablation and the benign-vs-adversarial subset comparison (complexity justification).

## Decision rules (fixed before seeing the writeup)

The architectural decision (Phase 24) is driven by these, decided in advance:

- **The component is worth adopting for high-risk evidence** iff, on the frozen corpus, it achieves
  correlated-failure escape materially below every signal-only baseline **and** its false-block is
  either at the noise floor or clearly reducible (documented, not hand-waved).
- **It must not be presented as closing correlated failure** — the no-tell ceiling (S23 escape = 1.0)
  is a required disclosure. The claim is bounded to "catches correlated failures that leave an
  observable tell," never "solves correlated failure."
- **The complexity is justified only under an adversarial-metadata threat model.** If a deployment can
  trust its provenance metadata, the honest recommendation is the cheap independence-first subset with
  the other layers for non-correlated failure states — not the full stack for its own sake.

## What would falsify the study's thesis

The thesis is: *provenance/independence-aware verification catches correlated grounding+entailment
failures that downstream signal composition cannot.* It is falsified if any of the following held on
the frozen corpus (none do; each is checked):

1. A signal-only baseline reaches correlated-failure escape ≈ 0 (it would mean downstream signals
   suffice). — Falsified: signal-only baselines escape 0.67–1.00.
2. The component's zero-escape is achieved only by blocking (false-block ≫ noise floor). — Falsified:
   false-block = 15/132 = the noise floor exactly.
3. The component escapes on cases that DO carry a tell (it would mean the layers don't work). —
   Falsified: escape = 0 on all corpus + fabrication scenarios that leave a tell.
4. The component claims to catch no-tell failures. — Not claimed; S23 escape = 1.0 is disclosed.

The honest negative that survives: on *this* corpus the primary endpoint is reachable by independence
alone (benign minimal subset), because every trap case carries multiple tells. The study does not
hide this — it is the reason the complexity is justified only against fabrication, and the reason the
final claim is bounded.
