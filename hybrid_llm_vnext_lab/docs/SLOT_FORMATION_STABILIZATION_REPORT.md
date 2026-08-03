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
B0 (no intervention) reproduced the frozen five-seed S needle@d96 **exactly** on all three
diagnostic seeds — **s3 = 0.000, s6 = 0.075, s7 = 0.042** (targets 0.000 / 0.075 / 0.042). The
environment is faithful (same torch build) and the stabilization runner's no-intervention path is
byte-identical to the frozen harness (checkpoint diagnostics do not perturb training).

### 4.2 Stage A per-arm (development seeds 3, 6, 7)
**Development-set only — not a fresh holdout result.** needle@d96 (A+ frozen: s3=0.017, s6=0.017,
s7=0.000):

| arm | s3 | s6 | s7 | formed | causal | eligible | note |
|---|---|---|---|---|---|---|---|
| B0 (control) | 0.000 | 0.075 | 0.042 | 1/3 | clean | — | reproduces frozen |
| O1 (slot LR 1e-3, warmup 180) | 0.000 | 0.008 | 0.000 | 0/3 | — | ✗ | regressed s6 |
| O2 (slot LR 3e-3, warmup 180) | 0.000 | 0.042 | 0.000 | 0/3 | — | ✗ | regressed s6 |
| K1 (orthogonal init) | 0.125 | 0.017 | 0.017 | 1/3 | clean | ✗ | rescued s3, **broke s6** |
| C1 (curriculum only) | 1.000 | 0.925 | 1.000 | 3/3 | **FAIL** | ✗ | window-pathway confound |
| R1 (alignment only) | 0.008 | 0.558 | 0.225 | 2/3 | clean | ✓ | rescued s7 |
| **CR1 (curriculum + alignment)** | 1.000 | 0.833 | 0.967 | **3/3** | **clean** | **✓** | rescued s3 **and** s7 |

**Family 1 (optimizer): refuted** — both variants regressed the marginal former and rescued no
non-former. **Family 2 (init): no reliability gain** — K1 only *relocated* which seed forms (the
baseline is already orthogonal). **Family 3: the decisive contrast** — C1 (curriculum alone) hits
3/3 on the metric but **fails the causal gate** (slots-off leaves 0.575 on s6, rand-address leaves
0.90/0.33 on s6/s7 → the multi-layer local-window pathway, not slots). Adding the **alignment**
term (CR1) restores clean causal collapse (slots-off ≈ 0 on all three) → the alignment objective
grounds the retrieval *in the slots*.

### 4.3 Candidate selection
Eligible arms: **{R1, CR1}**. The frozen rule ranks by k1 = #seeds formed first: **CR1 (3) > R1 (2)**
→ **CR1 selected**, no tie, no override. (`SELECTED_CANDIDATE.json`, sha256 pinned; committed and
pushed before any fresh training; pre-registration re-verified 26/0.)

### 4.4 Stage B fresh validation (seeds 8–12)
Fresh, uncontaminated seeds. needle@d96:

| seed | A+ | B0 | CR1 | CR1 forms | CR1 causal |
|---|---|---|---|---|---|
| 8 | 0.000 | 0.642 | 0.992 | ✓ | clean |
| 9 | 0.000 | 0.583 | **0.000** | ✗ | — (retention failure) |
| 10 | 0.000 | 0.183 | 0.992 | ✓ | clean |
| 11 | 0.000 | 0.000 | 1.000 | ✓ | clean |
| 12 | 0.000 | 0.033 | 0.967 | ✓ | clean |
| **formed** | 0/5 | **3/5** | **4/5** | | all forming seeds collapse |

CR1 mean(S−A+) = **0.790**, median = **0.992**, wins 4/5; PPL 136.6 ≤ 1.20×144.6; every forming
seed collapses under slots-off **and** randomized-address; d16/d220 gates pass. All Stage B gates
b1–b11 **pass**. CR1 (4/5) **beats B0 (3/5)** — and B0 itself matches the historical ~60% baseline,
confirming the fresh seeds were not anomalously easy for the slot circuit.

**Seed 9 (the one miss)** is a *retention* failure, not a formation failure: CR1 seed 9 reached
needle **1.000 at step 300** (write-read overlap ≈ 1.0), then decayed to 0.000 after the alignment
λ→0 (step 600) and the curriculum handoff to the original distribution (step 700). Seeds 8/10/11
dipped at step 900 but recovered; seed 9 did not. See `SLOT_FORMATION_FAILURE_ANALYSIS.md` and
`routing_diagnostics.json`.

## 5. Classification & readiness
**`PROVISIONALLY_STABILIZED`.** The selected candidate CR1 (curriculum + temporary write-read
alignment) passed **every** pre-registered Stage B gate on fresh seeds 8–12: formation 4/5 (> B0's
3/5), mean/median margin, wins, parameter match, PPL quality, causal collapse on every forming seed,
and distance robustness — with no Phase/KDA/MLA, no N×N, and bounded O(M·D) state.

**Supported mechanism:** the failure is a **weak-early-routing-signal / architectural-bistability**
problem, not an optimizer or symmetry problem. At init the write/read slot addresses are
uncorrelated (overlap ≈ chance) and the routing gradients are ≈ 0; the model learns *what* to write
before *where*. The **write-read alignment** objective supplies the missing early routing gradient
and grounds retrieval in the slots (fixing the window-pathway confound that invalidated
curriculum-alone). Seed 9 shows the residual limit: the scaffold can place the circuit in the
forming basin, but that basin is not always a stable attractor once the scaffold is removed.

**Remaining uncertainty:** (1) 4/5 not 5/5 — one fresh seed formed then unwound; (2) the candidate
was chosen over multiple arms on a development set, so selection bias is possible; (3) needle scores
saturate near 1.0 for forming seeds, so the *margin* size is not the headline — the *reliability
count* and *causal cleanliness* are.

**Exact next gate:** one independent confirmatory five-seed replication of the frozen CR1
configuration, **no further tuning**, before any KDA readiness is reconsidered.

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
