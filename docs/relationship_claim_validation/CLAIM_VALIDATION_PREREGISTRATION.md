# Claim Validation — Preregistration (v0.1)

**Experiment:** Relationship Claim Validation Experiment v0.1 ("Claim Truth Layer").
**Track:** new, independent, additive. Package: `relationship_claim_validation/`.

> ## Scope boundary — read first
> The frozen substrate the brief assumes (SEEB v1.0.0, a resolver series v0.1–v0.5,
> a hidden relationship corpus, a frozen proposal-validation / governance / packet
> pipeline, and prior experiment locks) **does not exist in this repository**
> (`rasaha/symbolu`). This was verified by exhaustive search. Consequently:
> - This experiment is **stand-alone**; it does not insert a stage before any real
>   governance and does not modify any resolver/governance/packet/corpus.
> - It runs over a **self-authored synthetic corpus** (`corpus.py`), not the
>   referenced hidden corpus.
> - The judges are **deterministic, span-grounded rule engines**, not LLMs, so the
>   whole experiment is reproducible.
> - Every gate that references nonexistent prior artifacts is marked **N/A**, not
>   "passed."
> A positive result is **construction/mechanism validation on synthetic data** — it
> is **not** evidence of real-world error reduction, and the production-deployment
> question stays **NO** (see `FINAL_VERDICT.md`).

---

## 1. Scientific question

Can an evidence-grounded Relationship Claim Validation Layer distinguish supported,
partially-supported, contradicted, unsupported, and insufficiently-evidenced
relationships **before** they are handed downstream?

## 2. Hypotheses (fixed before results)

- **H1 (primary).** Relationship proposal + graph validation are necessary but
  insufficient; a dedicated evidence-grounded claim validator reduces unsupported
  relationships while preserving supported ones.
- **H0 (null).** Claim validation provides no measurable improvement beyond
  proposal validation (here: beyond the V0 identity baseline).
- **HA (alternative).** Claim validation reduces unsupported relationships without
  materially reducing correctly supported ones (fixes > 0, breaks ≈ 0).

## 3. Architecture under test (frozen before results)

`Documents → (proposal) → THIS LAYER → (downstream)`. The layer owns relationship
**truth**, not governance. Per claim:
`deterministic pre-checks → Judge A (advocate) ∥ Judge B (challenger) → Judge C
(adjudicator, only on disagreement) → status + recommended action`.

## 4. Endpoints (fixed before results)

- **Primary:** relationship precision at the retained-decision level — unsupported
  relationships removed while supported relationships preserved.
- **Secondary:** false removals, false acceptances, recall, status accuracy,
  adjudication count, deterministic-removal count, runtime determinism.

## 5. Ablations (fixed before results)

V0 no validation (identity) · V1 deterministic only · V2 +Judge A · V3 +Judge B ·
V4 full (+Judge C). See `ABLATION_RESULTS.md`.

## 6. Statistics (fixed before results)

Paired comparison of each ablation vs the V0 baseline: **fixes**, **breaks**,
**net**, **net-fix-rate**, and a deterministic bootstrap **95% CI** (seed
`20260720`, 2000 resamples). No p-value theatre on a 48-case synthetic set; effect
is reported as net-fix-rate with a CI and read descriptively.

## 7. Calibration preconditions (fixed before results)

Because there is no external pipeline to hold constant, calibration is defined
intrinsically: (a) V0 disabled = identity pass-through (retain all as SUPPORTED);
(b) deterministic checks are pure functions; (c) judges are deterministic; (d) two
full runs are byte-identical; (e) the public projection exposes no gold. All are
asserted by the test suite before results are read.

## 8. Hidden lock (fixed before results)

Content hashes of the frozen components (deterministic rules, judge rules, legal
types, bootstrap params) and the corpus, recorded in `HIDDEN_LOCK.md`. There is no
prior lock in this repo to compare against; this lock is created for this track.

## 9. Deviations from the brief (declared, not hidden)

| Brief assumes | Reality here | Honest substitution |
|---|---|---|
| Frozen proposal/governance/packet pipeline | absent | stand-alone layer; V0 = identity baseline |
| Hidden relationship corpus | absent | self-authored synthetic corpus (`corpus.py`) |
| LLM judges A/B/C | non-deterministic; unavailable offline | deterministic span-grounded judges |
| Prior experiment locks / byte-identical priors | absent | gates marked **N/A**; package modifies nothing else |

## 10. Interpretation boundary (fixed before results)

Even a fully positive result supports only: *"a relationship-claim-validation layer
reduced unsupported relationship assertions on a self-authored synthetic corpus,
using deterministic judges."* It does **not** establish general hallucination
elimination, production readiness, broad factual correctness, or certification.
