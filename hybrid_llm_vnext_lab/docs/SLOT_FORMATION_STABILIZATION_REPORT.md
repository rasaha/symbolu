# Slot Formation Stabilization — Report

**Status:** EXPERIMENTAL · NOT_AN_INSTALLABLE_PACKAGE · NOT_A_PRODUCTION_MODEL
**Phase:** Phase-free slot-formation stabilization (three intervention families, tested independently).
**Immutable starting point (not reclassified):** PR #1300 five-seed holdout `PARTIALLY_STABLE` (3/5) →
`NOT_READY_FOR_KDA_VALIDATION`.

> This document separates, explicitly and throughout: **development diagnostic seeds** (3, 6, 7)
> from **fresh validation seeds** (8–12); **historical baseline evidence** (PR #1300) from **new
> intervention evidence**; **primary gates** from **secondary diagnostics**; and **inference** from
> **unproven hypotheses**. Diagnostic-seed rescue is **never** described as generalization.

## 1. Question
Can one of three training interventions increase **reliable formation** of the existing bounded-slot
**S** circuit without changing its architecture, degrading language quality, or weakening causal
slot dependence? The suspected failure is an optimization/initialization sensitivity in the
write→address→read routing loop.

## 2. What is held frozen
The S architecture (d=128, 4 heads, 4 layers, window 64, 32 slots, key dim 64, seq 160, batch 16,
1200 steps, AdamW, base LR 2e-3, wd 0.01, warmup 60, clip 1.0, dropout 0, fp32, ~2.0M params),
its read/write equations, the tokenizer, corpus, task definitions, parameter count, output head, and
inference path are **unchanged** and hash-pinned (`FROZEN_BASELINE_MANIFEST.json`). Only the
pre-registered surfaces differ per arm: optimizer parameter groups + warmup, initial slot-key
values, curriculum, a temporary label-free alignment loss, and diagnostic instrumentation.

## 3. Design (pre-registered before training)
- **Stage A (development):** seeds 3, 6, 7 (historical non-former / marginal-former / non-former).
  Arms **B0, O1, O2, K1, C1, R1, CR1**. A+ reused from the frozen five-seed artifacts.
- **Stage B (fresh validation):** seeds 8, 9, 10, 11, 12 (verified uncontaminated). Arms **A+, B0,
  selected candidate**. 1200 steps, no tuning.
- Interventions tested **independently**; no cross-family combination this round (CR1 combines only
  the two Family-3 scaffolds).
- Formation rule (inherited, unchanged): `S_d96 ≥ 0.075` AND `S − A+ ≥ 0.050` AND `S ≥ 0.07`.
- Selection is mechanical (`SELECTION_RULE.json`); Stage B requires **≥ 4/5** formation (a higher
  mean with < 4/5 does **not** pass).

Environment: Python 3.11.15, torch 2.13.0+cu130, CPU, threads=4, fp32 — the **same torch build**
that produced the frozen five-seed result. Per S-seed ≈ 1057 s (matches the frozen run).

## 4. Results

### 4.1 B0 reproduction (development seeds) — is the environment faithful?
_Populated from `artifacts/slot_formation_stabilization/diagnostic_results.json`._
Target (frozen five-seed S on 3/6/7): **s3 = 0.000, s6 = 0.075, s7 = 0.042**.

<!-- RESULTS:B0 -->

### 4.2 Stage A per-arm (development seeds 3, 6, 7)
_Per-seed needle@d16/d96/d220, PPL@256, causal ablations, formation, rescue, eligibility from
`diagnostic_classification.json`. **Development-set only — not a fresh holdout result.**_

<!-- RESULTS:STAGE_A -->

### 4.3 Candidate selection
_Mechanical selection trace from `selected_candidate.json`._

<!-- RESULTS:SELECTION -->

### 4.4 Stage B fresh validation (seeds 8–12)
_A+, B0, candidate; formation count, mean/median margin, causal, PPL, distance from
`fresh_holdout_classification.json`._

<!-- RESULTS:STAGE_B -->

## 5. Classification & readiness
<!-- RESULTS:VERDICT -->

Regardless of Stage B outcome, readiness remains **NOT_READY_FOR_KDA_VALIDATION** — even under
`PROVISIONALLY_STABILIZED` (an intervention was selected over multiple candidates). The next gate is
**one independent confirmatory five-seed replication of the frozen winning intervention, with no
further tuning**. KDA readiness may only be reconsidered by that later confirmatory phase.

## 6. Safeguards (confirmed)
No global N×N; bounded streaming state O(M·D); training scan O(N·M·D); no quadratic event softmax;
no Phase/KDA/MLA in the graph; parameter count matched; alignment loss adds no inference-time
parameter or operation and is zero after step 600 and during all evaluation; evaluation runs without
curriculum or auxiliary loss; the frozen `abc.json` is byte-unchanged. Details in
`complexity_report.json` and `SLOT_FORMATION_FAILURE_ANALYSIS.md`.

## 7. Scope discipline
Not KDA, MLA, Phase, quadratic event attention, global softmax, streaming-slot architecture, slot
count/dim, depth/width, window, parameter budget, production inference, packaging, Agent Runtime, AI
Hiring, Procurement, TAP, ActionGate, Cloud Scaling Controller, or H22. The slot system is **not**
promoted to a packaged module.
