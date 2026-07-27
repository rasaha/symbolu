# Phase as an Auxiliary Information-Health Sensor

**Decisive question:** does frozen Phase state add *causal, generalizable* information about
long-range evidence health **after** exact joins and bounded quadratic evidence reasoning are
already handled correctly?

Phase is tested **only** as an auxiliary long-stream temporal/contextual sensor — never as an
evidence router, factual authority, join engine, or decision-maker.

## Responsibility boundary (structurally enforced)

| concern | handled by | never by |
|---|---|---|
| entity equality, joins, timestamps, versions, provenance, authority | deterministic schema/index (`dataset.py`) | Phase |
| comparing candidate records, contradictions, local evidence, selected evidence IDs | bounded quadratic attention over a **bounded packet** (`quality_heads.QuadraticBranch`) | Phase |
| long-stream temporal/contextual quality signals | **frozen** Phase recurrence, O(N) scan (`quality_heads.PhaseBranch`) | — |

Fusion is **late** — only inside the information-health head:
`health_input = concat(deterministic_features, quadratic_features, phase_auxiliary_features)`.
Phase never feeds deterministic joins, evidence admission, or the quadratic keys, and
`supporting_evidence_ids` come **only** from the deterministic/quadratic packet.

## Targets (Phase-plausible only)

`persistence`, `unresolved_recurrence`, `context_shift`, `sequence_anomaly`. Already-deterministic
dimensions (provenance presence, source authority, timestamp validity, schema completeness, access)
are **not** Phase targets — they enter as deterministic features.

## Designed information asymmetry

The causal evidence for the long-range targets is placed at controlled (often large) distances from
the query. The bounded deterministic packet is **local**, so it structurally cannot see most distant
evidence (verified: 76% at N=256, 89% at N=1024 of relevant positions lie outside the packet). Only
an O(N) full-stream scanner (Phase, or a matched temporal baseline) can integrate it. This is what
makes the A3-vs-A1 and A3-vs-baseline comparisons meaningful.

## Arms

`A0` deterministic only · `A1` +bounded quadratic · `A2` +Phase · `A3` +quadratic+Phase ·
`A4/A5/A6` +quadratic+{mean pool / EMA / small GRU} (matched temporal-state dim, approx params).
Decisive comparisons: **A3 vs A1** and **A3 vs best(A4,A5,A6)**.

## Compute boundary

Phase scan O(N) (chunked recurrence, no N×N); deterministic index = bounded lookup; quadratic
attention over ≤ `packet_K` candidates only. Phase state bytes are constant in N (`state_bytes`).
`tests/test_quality.py` asserts the packet bound and the frozen Phase core.

## Files

`dataset.py` · `quality_heads.py` · `baselines.py` · `train.py` · `evaluate.py` ·
`causal_controls.py` · `run_pilot.py` (§17 validity pilot) · `run_full.py` (full matrix, gated) ·
`tests/` · `results/` · `PHASE_QUALITY_AUXILIARY_REPORT.md` · `PHASE_QUALITY_AUXILIARY_RESULTS.json`.

## Sequencing

Pilot first (A0/A1/A3/A5 @ N=256,1024, one seed). The full matrix (all arms, N=4096, 3 seeds,
held-out generalization, full causal controls) runs **only** if the pilot is valid: labels
balanced, A1 above chance, Phase causal controls functioning, no leakage, ≥1 Phase target showing
preliminary gain. Acceptance thresholds (§14) are fixed in advance and never lowered after seeing
results.
