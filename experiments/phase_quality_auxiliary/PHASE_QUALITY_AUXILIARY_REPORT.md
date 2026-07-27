# Phase as an Auxiliary Information-Health Sensor — Report

**Decisive question:** does frozen Phase state add *causal, generalizable* information about
long-range evidence health **after** exact joins and bounded quadratic evidence reasoning are
already handled correctly?

**Answer: No — unsupported.** Frozen Phase adds no measurable information-health signal on top of
deterministic joins + bounded quadratic reasoning, and the one long-range condition that *is*
learnable is captured by a **trained GRU baseline**, not by Phase.

## Setup validity (pilot, §17 — PASSED)

- **No leakage:** deterministic-metadata-only `A0` is at chance on every target (macro 0.481).
- **Quadratic works:** `A1` solves both local targets (context_shift, sequence_anomaly = 1.00).
- **Designed asymmetry:** 100% of long-range (persistence/recurrence) evidence is placed strictly
  outside the bounded packet; local (context_shift/anomaly) evidence is inside it (verified).
- **Causal controls functioning; ≥1 Phase target preliminary gain** → `PILOT_VALID`.

## Full matrix — N=1024, 3 seeds (decisive)

| arm | context_shift | seq_anomaly | persistence | unresolved_recurrence | **macro AUROC** | params | Phase bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0 deterministic only | 0.48 | 0.50 | 0.44 | 0.51 | 0.481 | 7.6k | 0 |
| A2 det + Phase | 0.49 | 0.46 | 0.54 | 0.52 | 0.504 | 19.2k | 576 |
| A1 det + quadratic | 1.00 | 1.00 | 0.52 | 0.49 | 0.752 | 34.7k | 0 |
| **A3 det + quadratic + Phase** | 1.00 | 1.00 | 0.51 | 0.50 | **0.751** | 46.3k | 576 |
| A4 det + quad + mean | 1.00 | 1.00 | 0.48 | 0.50 | 0.746 | 42.5k | 0 |
| A5 det + quad + EMA | 1.00 | 1.00 | 0.51 | 0.49 | 0.749 | 42.5k | 0 |
| **A6 det + quad + GRU** | 1.00 | 1.00 | 0.50 | **0.84** | **0.834** | 48.8k | 0 |

Three facts, stable across 3 seeds:

1. **A3 ≡ A1** (macro 0.751 vs 0.752): Phase adds *nothing* on top of the bounded quadratic.
2. **A2 ≈ chance** (0.504): Phase *alone* (no quadratic) adds nothing — it neither compares local
   evidence nor extracts long-range health.
3. **A6 (GRU) uniquely learns `unresolved_recurrence` (0.84)** — the ordered open→resolve→reopen
   pattern — while Phase, EMA, and mean pooling all sit at chance (0.49–0.50). The one learnable
   long-range condition is captured by a **trained** temporal recurrence, and frozen Phase is
   **dominated** by it (A6 0.834 ≫ A3 0.751).

`persistence` (focus has distant active records) is not learned by *any* arm — it requires
focus-conditioned retrieval over the full stream that no bounded temporal state (Phase, GRU, or
EMA) provides here. The local targets are fully handled by the bounded quadratic.

## §14 acceptance (thresholds fixed in advance, never lowered)

| criterion | required | actual | pass |
|---|---|---:|---|
| A3 macro-AUROC gain over A1 | ≥ 0.05 | **−0.001** | ❌ |
| A3 macro-AUPRC gain over A1 | ≥ 0.05 | ≈ −0.001 | ❌ |
| A3 Brier relative improvement | ≥ 10% | ≈ 0% | ❌ |
| gain collapses under Phase corruption | yes | no gain to collapse | ❌ |
| A3 beats best temporal baseline (A6) by ≥0.03 | yes | **−0.083 (worse)** | ❌ |

**PASS: NO.** Every Phase-value criterion fails; Phase is not merely unhelpful but *worse* than the
best matched temporal baseline.

## Phase causal controls (A3)

Macro AUROC is **exactly 0.757 under every intervention** — normal, Phase-zeroed,
Phase-shuffled-across-examples, Phase-shuffled-across-time, Phase-reversed, distant-relevant-segment
removed, and irrelevant-segment removed. Corrupting or deleting the Phase signal changes *nothing*:
there is no Phase-dependent signal to collapse (`causal_dependence_verified = False`). The model's
accuracy comes entirely from the deterministic + quadratic branches.

## Compute boundary (§16, verified)

- Phase scan **O(N)** (chunked recurrence, no N×N); Phase state **576 bytes**, constant in N.
- Deterministic index: bounded lookup; bounded packet ≤ K=16 records.
- Quadratic attention: over the query + packet only (≤17 tokens); never the N-stream, never N×N
  (`tests/test_quality.py`). Events processed by Phase = N; by each quadratic block ≤ 17.

The N=4096 stage was **stopped early**: with A3−A1 ≈ 0 and Phase dominated by the trained GRU across
3 seeds, the §14 "preserves the gain at N=4096" criterion has *no gain to preserve* and cannot
change the verdict — a compute-disciplined stop consistent with the gated methodology.

## §18 Required verdict

- **Deterministic evidence joins:** verified.
- **Bounded quadratic evidence comparison:** verified (solves both local targets to AUROC 1.00;
  bounded ≤17-token attention, no N×N).
- **Phase used only as auxiliary:** verified (late fusion only; Phase never touches joins, evidence
  admission, quadratic keys, or `supporting_evidence_ids`; frozen core, FREEZE OK, 98/98).
- **Persistence prediction gain:** ≈ −0.01 (none; unlearnable by all arms).
- **Unresolved-recurrence gain:** ≈ +0.01 for Phase (none); the trained GRU gets +0.35 — Phase does not.
- **Context-shift gain:** 0.00 (already 1.00 from the quadratic).
- **Sequence-anomaly gain:** 0.00 (already 1.00 from the quadratic).
- **Phase causal dependence:** failed (no Phase-dependent signal to collapse).
- **Held-out generalization:** not decisive — with no in-distribution Phase gain there is nothing to
  generalize (local targets generalize via the quadratic; Phase contributes nothing to carry over).
- **Phase versus best temporal baseline:** **worse** (A3 0.751 vs GRU 0.834).
- **Phase information-health value:** **unsupported.**
- **Authorized production role:** **none.** Keep exact joins deterministic and local evidence
  comparison in the bounded quadratic; a small trained recurrence (GRU) — not frozen Phase — is what
  captures the one learnable long-range pattern.

**Decisive answer:** frozen Phase state does **not** add causal, generalizable information about
long-range evidence health once exact joins and bounded quadratic reasoning are handled correctly.
Where a long-range signal is learnable at all, a trained temporal baseline captures it and frozen
Phase does not.
