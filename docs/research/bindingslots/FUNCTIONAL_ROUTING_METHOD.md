# Functional routing & retention — method

Follow-up to the confirmatory failure (PR #1324). A focused **Stage-1 screen** testing whether an
**address-specific functional objective** and/or a **gradual scaffold withdrawal** yield **causally
clean, retained** slot routing on five fresh seeds (18–22), under the frozen synthetic protocol with
no inference-architecture change.

## Motivation (reproduced, `validate_known_signatures.py` 5/0)

Aggregate write-read overlap dissociates from causally-address-dependent retrieval:
- **Purity:** seed 16 retrieves at 1.0 with correct-slot prob 0.21, rank 14, margin 0.9, and survives
  address randomization (0.45).
- **Retention:** seeds 13/14 retrieve at 0.0 while their *addressing* metrics at step 1200 are clean
  (prob 0.82–0.88, margin 6.7–9.9) — collapse is downstream of addressing (value/decoding).

See `docs/audits/bindingslots_functional_routing_development/PROXY_DISSOCIATION_ANALYSIS.md`.

## Arms (training-only; frozen loop, one in-memory function swap)

| arm | objective / change | swap |
|---|---|---|
| A+ | window-only control | none |
| R0 | frozen CR1 (comparator) | none |
| O1 | `L = −log(r[q, s*] + 1e-6)` | `alignment_loss` |
| O2 | `L = max(0, 3.0 − (z[q, s*] − max_{j≠s*} z[q, j]))` | `alignment_loss` |
| H3 | original-distribution mixture 0→1 across steps 600–900 | `curriculum_batch` |

`s* = argmax_j stop_gradient(w[f,j])` (lowest index on ties). O1/O2 keep R0's λ schedule (0.10→0 by
step 600) and use only captured slot-address vectors — no answer label, evaluator outcome, or frozen
randomized-address signal (verified). `interventions.py`/`stabilize.py` disk hashes are preserved.

## Metrics & classifier

New per-checkpoint routing metrics (already computed by the frozen diagnostics at d96):
correct-slot probability (≥ 0.50), written-slot rank (≤ 5), address-logit margin (≥ 3.0), plus
value-recovery and entropies; aggregate overlap kept as a diagnostic only. The classifier reuses the
frozen formation + causal rules and adds the retention checkpoints (600/900/1200) and routing
thresholds. `FORMED_FUNCTIONALLY_CLEAN_AND_RETAINED` requires endpoint retrieval at 600/900/1200 **and**
routing-clean at 1200 **and** slots-off + randomized-address collapse **and** quality + distance.

## Gate & selection

Stage-1 full single gate: clean-stable ≥ 4/5, wins vs R0 ≥ 4/5, every final former causally clean,
collapse ≤ 1/5, routing-unclean = 0, quality + distance pass. Winner by clean-stable count → wins →
fewer collapses → tie-break O1, O2, H3, R0. On selection, readiness is
`KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION` (Stage-2 + confirmation deferred);
`READY_FOR_KDA_VALIDATION` is never emitted.

## Environment

Python 3.11.15, torch 2.2.2+cu121, CPU, fp32, threads=4. ~1000 s per R0/O1/O2/H3 seed; A+ ~230 s.
Resumable/idempotent; frozen `abc.json` recorded before/after.
