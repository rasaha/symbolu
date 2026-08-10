# Minimum Experiment: Do Model-Internal Signals Improve Governance?

**Companion to the readiness audit + defensibility analysis · Prepared 2026-06-17**
*The decisive test for the one deep moat: does reading the model's internal state
(entropy, coherence, vritti, JEPA disagreement) make governance decisions better than
text-level governance — on a real model, with publishable, reproducible numbers, in <2 weeks?*

> This is the scaled, statistically-powered version of task #7 in the defensibility plan.
> It is **pre-registered**: success and failure thresholds below are fixed *before* running.
> If it fails its own criteria, that is a real and useful result — kill or pivot the moat.

---

## 0. Framing — governance as selective prediction

A governance layer is a **detector**: for each proposed tool call it outputs a risk score and
either **ALLOW**, **ESCALATE** (send to a human), or **BLOCK**. Its job is to catch the calls
that should *not* execute (unsafe / injected / hallucinated / out-of-policy) while bothering
humans as little as possible. So the question "do signals help?" is precisely:

> *Does the model-internal signal carry information about whether a proposed action is unsafe
> that text-level signals (risk level, self-reported confidence) do not — enough to catch more
> unsafe actions at the same human-review budget?*

That is a **risk-coverage / selective-prediction** problem with standard, deck-friendly
metrics (ROC, catch-rate-at-budget). The whole experiment is one model, one dataset, **four
nested scoring functions**, and a threshold sweep.

---

## 1. Hypothesis

**H1 (primary).** Adding model-internal signals (entropy, coherence, vritti, JEPA
disagreement) to a governance decision improves discrimination of unsafe tool calls over the
best text-level configuration: **AUROC(C4) − AUROC(C3) ≥ 0.05**, DeLong **p < 0.05**, on a
held-out test set.

**H2 (operating point).** At a fixed **10% escalation budget**, C4 catches **≥ 10 percentage
points more** unsafe actions than C3 (non-overlapping bootstrap 95% CIs).

**H3 (monotonic ablation).** Primary metric is monotone non-decreasing across the nested
configs: **C4 ≥ C3 ≥ C2 ≥ C1**.

**H4 (signal substance).** At least **2 of the 4** signals individually achieve **AUROC > 0.60**
as standalone detectors — i.e., the lift is not one lucky feature, and the internals are not noise.

**Null (H0).** Model-internal signals add no discriminative information beyond risk taxonomy +
self-reported confidence (AUROC lift < 0.02 or not significant). *Pre-committed: if H0 holds,
the deep moat is unproven and the roadmap should not depend on it.*

The configurations are **strict nested ablations** so any lift is attributable to the *added
feature group only*:

| Config | Features in the score | Maps to repo |
|---|---|---|
| **C1 Approval only** | static policy: escalate if `action_type ∈ require_approval_set` | `ApprovalPolicy` |
| **C2 + Risk taxonomy** | C1 + `risk_level` rank (read_only→privileged = 0→1) | `ToolRiskLevel` |
| **C3 + Confidence** | C2 + **text-level** confidence (model self-reported safety + quality) | `ConfidenceGate` |
| **C4 + Model-internal signals** | C3 + entropy, (1−coherence), vritti-risk, JEPA-disagreement | `entropy_adapter`, `vritti_adapter`, `jepa_governance`, `sovereign_bridge` |

**Decisive isolation:** C3 and C4 use the **same CG model, same single forward pass**. The
*only* difference is reading the 32-D internal state (C4) vs reading the model's text output
(C3). This is exactly the brief's claim — "state-derived signals, not prompt-level
self-reported confidence" — reduced to one controlled variable.

---

## 2. Dataset

**Decision unit:** one *proposed tool call* emitted by the model during a scenario.
**Label (deterministic oracle, no human judging):** `y = 1` if the proposed call is
**unsafe/out-of-policy** for that scenario (matches the scenario's prohibited-action spec),
else `y = 0`. Reproducible because the oracle is a per-scenario rule, not an annotator.

**Sources (real, published → diligence-credible):**

1. **AgentDojo** (primary, ~70% of N) — the recognized prompt-injection benchmark for
   tool-using agents. Native utility *and* security checks: the attack defines the exact
   prohibited tool call, so "injection succeeded = unsafe call emitted" is an objective label.
   Gives both unsafe calls (attack-induced) and safe calls (legitimate task steps).
2. **InjecAgent** (secondary, generalization check) — indirect prompt-injection across many
   tool/attacker combos; confirms the result is not AgentDojo-specific.
3. **Enterprise destructive set** (~40–60 hand-built, ~15–20% of N) — refund/payment/delete/
   privileged-credential scenarios with ambiguous or contradictory instructions and
   hallucination-inducing missing context. Fast to author, matches the BFSI/healthcare buyer
   narrative, and broadens the claim beyond injection (covers destructive + hallucinated-tool +
   over-broad-request failure modes from the audit's edge-case list).

**Size & balance:** target **N ≈ 400–600 labeled decisions**, **~25–35% positive** (unsafe).
This is powered to detect a 0.05 AUROC gap at p<0.05 via DeLong; bootstrap CIs will confirm
N suffices and scenarios can be expanded if CIs are too wide.

**Split:** stratified **60/40 train/test by scenario family** (split on scenario, never leak a
scenario across splits). All thresholds and any learned signal weights are fit on **train**;
**all reported numbers are test-set only.** A **zero-tuning C4** variant (gateway's existing
fixed formula — entropy penalty ≤0.15, published JEPA thresholds) is reported alongside the
fitted C4 so skeptics cannot attribute the lift to overfitting.

**Model:** the best available **CG checkpoint via `MistralCGAdapter`** (real torch forward
pass producing the 32-D state). One forward pass per decision point — *not* full generation —
keeps compute to hours on a single GPU and sidesteps the audit's O(n²) generation-loop concern.
Features are **cached to disk** so the analysis is re-runnable in seconds and the run is
deterministic given a seed + checkpoint hash.

---

## 3. Metrics

**Primary (the headline):**
- **AUROC** and **AUPRC** of each config's risk score as an unsafe-action detector (AUPRC
  matters because positives are the minority).
- **Catch-rate @ fixed escalation budget** — at 5%, 10%, 20% of calls escalated, what fraction
  of unsafe actions is caught? *This is the investor chart.*
- **Human burden @ fixed catch** — escalations needed to catch 90% of unsafe actions (lower = better).

**Security/utility (native to the benchmark, buyer-legible):**
- **Attack success rate (ASR)** at a fixed operating point — fraction of unsafe calls that
  would execute under each config (lower = better).
- **Utility retention / over-block rate** — fraction of *legitimate* tasks needlessly
  blocked/escalated. Guards against "wins by blocking everything."

**Proof-grade statistics (this is what makes it publishable, not anecdotal):**
- **DeLong test** for paired AUROC differences (C4 vs C3, same samples).
- **Bootstrap 95% CIs** (≥2,000 resamples) on AUROC and catch-@-budget; report CI overlap.
- **Signal ablation:** standalone AUROC per signal (entropy / coherence / vritti / JEPA) +
  logistic-regression coefficients in C4 → shows *which* internals carry the lift.
- **Calibration:** ECE / reliability curve for C3 vs C4 (the "confidence" claim).
- **Robustness:** 3 seeds + (if feasible) 2 checkpoints; report metric stability.

---

## 4. Implementation plan (<2 weeks, mostly harness — governance code already exists)

The gateway already consumes entropy/vritti/JEPA and has ConfidenceGate + risk taxonomy
(`mcp_gateway.py`, `jepa_governance.py`, `confidence_gate.py`), so this is **a harness +
dataset + metrics**, not new governance logic.

| Days | Task | Output |
|---|---|---|
| 1–2 | **Dataset adapter** — load AgentDojo + InjecAgent task/attack suites; write per-call safety oracle; author the enterprise destructive set. | `experiments/signal_gov/dataset.py` → list of `(scenario_id, conversation, proposed_call, y)` |
| 3–4 | **Feature extraction** — run `MistralCGAdapter` once per decision; capture 32-D state → entropy/coherence/vritti/JEPA via existing adapters; also elicit text-level confidence (self-report prompt) + risk level. Cache to parquet. | `experiments/signal_gov/extract_features.py` → `features.parquet` |
| 5–6 | **Four scoring functions** C1–C4 as pure functions over cached features (reuse `ConfidenceGate`/`jepa_governance` in "score mode"); fit thresholds + C4 logistic weights on **train**. | `experiments/signal_gov/configs.py` |
| 7–8 | **Metrics + stats + plots** — sklearn AUROC/AUPRC, DeLong, bootstrap; ROC overlay, catch-@-budget bars, signal-importance, calibration. | `run_experiment.py`, `figs/` |
| 9–10 | **Robustness + write-up** — seeds/checkpoint sensitivity; held-out report; 1-page result + deck figure; `README` with `make experiment`. | `REPORT.md`, deck-ready PNGs |
| +2 | Buffer (benchmark integration is the main risk; enterprise set de-risks it). | — |

**Reproducibility contract:** single command (`python experiments/signal_gov/run_experiment.py`),
pinned dataset versions + commit hashes, committed cached features (or a regeneration script),
fixed seeds, deterministic oracles, every figure regenerated from data. CI smoke-test on a
10-scenario subset.

**Investor figure (the one slide):** ROC overlay, four curves, C4 dominant; caption —
*"At equal human-review burden (10% of actions), model-internal signals catch [X]× more unsafe
agent actions than the best text-level governance — on the standard agent-security benchmark
(AgentDojo+InjecAgent, N=[…], held-out, DeLong p=[…])."* Plus the catch-@-budget bar chart.

---

## 5. Success criteria (pre-registered, all on the held-out test set)

The experiment **succeeds** (moat validated) iff **all** of:
1. **AUROC(C4) − AUROC(C3) ≥ 0.05**, DeLong **p < 0.05**.
2. **Catch @ 10% budget: C4 − C3 ≥ +10 pts**, non-overlapping bootstrap 95% CIs.
3. **Monotone** C4 ≥ C3 ≥ C2 ≥ C1 on AUROC (no inversion).
4. **≥ 2 of 4** signals individually AUROC > 0.60.
5. **No utility tax:** at matched catch rate, C4's over-block rate ≤ C3's + 5 pts (the lift is
   real detection, not over-escalation).
6. **Zero-tuning C4** (fixed gateway formula) still beats C3 on AUROC (lift survives without fitting).

A **strong** result (deck-leading) additionally shows catch @ 10% ≥ 1.5× C3, or ASR cut ≥ 50%
vs C3 at matched utility.

---

## 6. Failure criteria (pre-registered — what kills or pivots the moat)

Declare the moat **unproven** if any of:
- **F1.** AUROC(C4) − AUROC(C3) **< 0.02** or DeLong **p ≥ 0.05** → internals add nothing beyond
  confidence. *Action: kill the "signal" pitch; compete on gateway depth + budget circuit-breaker.*
- **F2.** C4 wins **only by escalating more** (no improvement at matched human burden) → signals
  are a noisier risk proxy, not new information.
- **F3.** All four signals standalone **AUROC ≈ 0.5** → no information in the internals (model too
  weak or signals miscomputed). *Action: better checkpoint or fix the signal pipeline; re-run.*
- **F4.** Result **flips across seeds/checkpoints** (lift CI crosses 0) → not robust, not publishable.
- **F5.** C3 already **saturates (AUROC > 0.92)** → no headroom; the task is too easy. *Action: harder
  adversarial scenarios, then re-run — do not report a non-result as success.*

**Threats to validity (state them in the deck — diligence will ask):** (a) the claim is only as
good as the CG checkpoint; a weak model makes internals noise. (b) AgentDojo is injection-heavy
— the enterprise destructive + hallucination set is what generalizes the claim. (c) thresholds
must be held-out; the zero-tuning variant defends against overfitting accusations. (d) this
proves *discrimination lift*, not end-to-end production safety — frame it as the first
controlled evidence, with external pilots as the next step.

---

## 7. Why this is the right minimum

- **Real model, real benchmark, objective labels** — no synthetic fixtures (the exact gap the
  audit found: every existing CG test uses fakes).
- **One controlled variable** (internal state vs text, same model, same forward pass) — the
  cleanest possible isolation of the differentiating claim.
- **Reuses existing governance code** — feasible in <2 weeks because only the harness/metrics
  are new.
- **Pre-registered + held-out + DeLong-significant** — survives a skeptical reviewer and is
  honestly publishable whether it wins or loses.
- **Directly answers the investor question** with one ROC slide and one catch-@-budget bar.
