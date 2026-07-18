# Kosha Control-Plane Readiness/Entropy Gate — PRE-REGISTRATION + CPU Simulation (doc-only)

## 1. Title
Kosha readiness/entropy as a **control-plane gate** (emit / defer / hedge / depth-cap) over existing
traces — pre-registration and CPU-safe simulation harness.

## 2. Status
**DESIGN + CPU SIMULATION ONLY.** No runtime wiring, no prompt-construction change, no model generation,
no Quad/Phase/recursion behavior. Deterministic query-derived `p_k` only. Hidden-state `p_k` is BLOCKED
until real Kosha labels pass the surface-baseline gate. Parameters are frozen here, before any outcome is
seen. No validation claim; no consciousness/readiness-detection claim.

## 3. Prior result — K2 prompt-modifier failure
The Kosha **prompt-modifier** generation eval (`docs/KOSHA_K2_QUALITY_EVAL_PREREG.md`,
`docs/RESULTS_KOSHA_K2.md`) returned **`CG_KOSHA_K2_DEGRADES_FRAME`**: inserting a Kosha depth block into the
prompt regressed C×R×S frame correctness / rejected-domain avoidance. The Kosha prompt modifier is therefore
**disabled** and is **not** part of the validated product.

## 4. New hypothesis
> *Can Kosha readiness/entropy be used as a **control-plane gate** for emit/defer/hedge/depth-cap decisions
> **without touching prompt text** and **without degrading** the validated C×R×S wrapper?*

This is a **new hypothesis**, not a K2 continuation and not a K2 rescue.

## 5. Intervention-surface distinction
| | K2 (rejected) | This proposal |
|---|---|---|
| Surface | **prompt text** (depth block injected) | **control plane** (decision to emit/defer/hedge/cap depth) |
| Touches the LLM input? | yes | **no** |
| What K2 measured | generation quality / frame correctness under a modified prompt | n/a — this never changes the prompt |
| Tested by K2? | yes → degrades frame | **no** — untested surface |
K2 killing the prompt modifier says nothing about a gate that never edits the prompt. Hence a fresh test.

## 6. Non-goals (hard boundaries)
1. No runtime wiring of the gate. 2. No prompt-construction change. 3. No model generation path.
4. No Quad/Phase/recursion runtime behavior. 5. No hidden-state `p_k` unless real labels pass the
surface-baseline gate. 6. No post-hoc parameter tuning. 7. No "Kosha is validated" claim. 8. No
consciousness / readiness-detection claim. 9. No reopening of the K2 prompt-modifier rescue.

## 7. Source of `p_k`
**First simulation uses a DETERMINISTIC query-derived `p_k`** from the existing Kosha selector/scoring
layer (`select_kosha_depth`, `kosha.py`): the selector's additive per-level cue scores are mapped to a
5-state distribution by a frozen-temperature softmax (`selector_to_pk`).
- This is a **deterministic heuristic `p_k`.**
- It is **not** hidden-state `p_k`.
- It is **not** a trained Kosha estimator.
- It **cannot** support a learned-state claim.

**Hidden-state `p_k` is BLOCKED** until **all** of: (a) real Kosha labels exist; (b) human or otherwise
non-circular labels pass the usability gate; (c) a hidden-state probe **beats the surface-feature
baseline** (`surface_baseline.py`). Requesting `--pk-source hidden` returns
`KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED` and does nothing else (§18).

## 8. Formulas
5-state Kosha distribution (order: annamaya, pranamaya, manomaya, vijnanamaya, anandamaya):
```
p_k = [p_annamaya, p_pranamaya, p_manomaya, p_vijnanamaya, p_anandamaya]
Σ p_k = 1 ,  p_k ≥ 0
```
Kosha entropy and its normalization:
```
H_K       = -Σ_k p_k log(p_k)
H_K_norm  =  H_K / log(5)            # ∈ [0,1]; 0 for one-hot, 1 for uniform
```
Readiness:
```
R_K = p_target · (1 - H_K_norm)
```
Soft recursion-modulation gate (reported, NOT wired to runtime):
```
w_K = α_K · sigmoid(κ · (τ_K - H_K_norm))
```
Final emit score:
```
E_emit = R_res · sigmoid( a·(τ_D - H_D) + b·(τ_G - H_G) + c·(τ_K - H_K_norm) + d·R_K )
```
`H_D`, `H_G`, `R_res` are **not present** in current traces. With the frozen defaults `a = b = 0` the
`H_D`/`H_G` terms drop out exactly; `R_res` falls back to its declared default and the simulation **labels
this clearly** (`used_defaults` per row). No tuned values are invented after seeing outcomes.

## 9. Fixed parameters (FROZEN — declared before simulation)
```
τ_K = 0.55      κ = 8.0        α_K = 1.0
a = 0.0         b = 0.0        c = 1.0        d = 1.0
τ_emit = 0.55   τ_hedge = 0.45 τ_defer = 0.35
max_depth_default = 1
softmax_temp = 0.5            # selector-score -> p_k temperature
H_D_default = 0.5  H_G_default = 0.5  τ_D = 0.55  τ_G = 0.55  R_res_default = 1.0
# pre-registered verdict thresholds:
min_separation = 0.15   max_withhold_good = 0.20   min_beat_random = 0.10   degrade_separation = -0.10
```
Simple fixed values, not optimized. **If any value is changed, the reason is documented here BEFORE
re-running**, and the run is flagged `KOSHA_CONTROL_SIM_PARAMETER_TUNING_RISK` (§15, §17).

## 10. Gate decisions
Each example yields an **emit decision** and a **depth decision** (simulation only; never affects runtime):
```
if   E_emit >= τ_emit:  EMIT
elif E_emit >= τ_hedge: HEDGE
else:                   DEFER

if R_K >= 0.65 and H_K_norm <= 0.45:  DEPTH_CAP_HIGH
else:                                 DEPTH_CAP_LOW
```

## 11. Simulation dataset
Run over **existing trusted, CPU-only traces.** Primary (default) input:
`scripts/cg_wrapper_ablation/csr_match_filter/eval_data/answer_audit_eval.jsonl` — **72** Phase-3 audit
examples with `query`, `csr_trace_fixture` domains, and **outcome labels**
(`expected_passed`, `expected_needs_rewrite`, `expected_findings`). Outcome mapping:
- `good_answer` ← `expected_passed`;  `audit_failure` ← `expected_needs_rewrite`;
- `frame_failure` ← findings ∈ {`primary_frame_missing`, `secondary_promoted_to_primary`};
- `rejected_domain_leak` ← findings ∈ {`rejected_domain_promoted`, `rejected_domain_mentioned_as_refutation`}.

Also accepted (no outcome labels → `OUTCOMES_UNAVAILABLE`): `kosha_k2_queries.json` (queries), any
`{queries|per_example|rows}` JSON or JSON list. If only a subset exists locally, use it and report counts.
**No GPU is required.**

## 12. Baselines
- **NO_GATE** — always EMIT (separation ≡ 0).
- **RANDOM_GATE** — the gate's own decisions, **permuted with a fixed seed** → identical marginal
  distribution, link to outcomes broken (expected separation ≈ 0).
- **QUERY_LENGTH** — length heuristic (≥8 words EMIT, ≥4 HEDGE, else DEFER).
At minimum NO_GATE and RANDOM_GATE are implemented; QUERY_LENGTH is included.

## 13. Metrics
total examples; decision distribution; emit/hedge/defer rates; depth_cap_high_rate; decision_by_slice (when
slice labels exist); guardrail violation rate (= withhold_good_rate); would_defer_good_answer_rate;
would_emit_bad_answer_rate; would_hedge_bad_answer_rate; correlation (φ) of *withhold* with audit_failure,
frame_failure, rejected_domain_leak; and the **separation** = P(withhold|audit_fail) − P(withhold|good),
compared against every baseline. If outcome labels are unavailable, report
`KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE` and claim nothing.

## 14. Guardrails
The gate is **promising only if all** hold:
1. It does **not** preferentially defer/hedge good C×R×S-valid answers (low `withhold_good_rate`).
2. It **does** preferentially hedge/defer audit-failing / frame-failing answers (positive separation).
3. It **beats** NO_GATE and RANDOM_GATE on separation.
4. It does **not** rely on post-hoc parameter tuning.

## 15. Decision labels (pre-registered)
```
KOSHA_CONTROL_SIM_READY                 # harness wired, ready to run
KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE  # no trusted outcome labels in the trace set
KOSHA_CONTROL_SIM_NO_SIGNAL             # outcomes present, gate does not beat baselines
KOSHA_CONTROL_SIM_BEATS_BASELINES       # gate beats NO_GATE & RANDOM_GATE on separation (guardrails pass)
KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS   # gate withholds good answers / negative separation
KOSHA_CONTROL_SIM_PARAMETER_TUNING_RISK # non-default params used (flag appended)
KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED     # hidden-state p_k requested before the surface gate is passed
```

## 16. Pass/fail criteria
With outcomes present and **default** params:
- **BEATS_BASELINES** iff `separation ≥ min_separation` **and** `withhold_good_rate ≤ max_withhold_good`
  **and** `(separation − random_separation) ≥ min_beat_random`.
- **DEGRADES_GUARDRAILS** iff `separation ≤ degrade_separation` **or** `withhold_good_rate > 0.5`.
- Otherwise **NO_SIGNAL**.
A `BEATS_BASELINES` result here is **necessary but not sufficient** for any product decision (it is a
deterministic query-derived simulation, not a learned-state validation).

## 17. Parameter-freezing rule
All parameters in §9 are frozen prior to running. They are **not** adjusted after seeing any metric. Any
change is (a) justified in this document first, (b) flagged `KOSHA_CONTROL_SIM_PARAMETER_TUNING_RISK`, and
(c) treated as a new pre-registration, not a continuation.

## 18. Hidden-state `p_k` blocker
Hidden-state `p_k = softmax(W_K·h + b_K)` is **forbidden** until real Kosha labels exist, pass a
non-circular usability gate, and a hidden-state probe **beats the surface-feature baseline** — the same
anti-circularity wall as Guna/Vritti. Until then `--pk-source hidden` returns
`KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED` and performs no simulation.

## 19. Interpretation rules
- A deterministic query-derived `p_k` measures only **query ambiguity**, while audit outcomes depend on the
  **answer**; low or zero separation is the expected, honest baseline result and must be reported as such.
- Positive separation under default params is **suggestive only** — it would justify a hidden-state probe
  attempt (still behind §18), never a validation/consciousness claim.
- Negative separation (gate withholds good answers) is a **real negative** and is recorded as
  `KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS`.

## 20. Future work (each gated, step by step)
1. Collect real (human / non-circular) Kosha labels; run them through the surface-baseline gate.
2. Only if they pass: train a hidden-state Kosha probe; re-run this simulation with `--pk-source hidden`.
3. Only if the gate then beats baselines without tuning: design a **shadow-mode** runtime evaluation that
   logs gate decisions **without acting on them** — still no prompt change, still guardrail-first.

---
*Status wording:* **Kosha control-plane readiness/entropy gating is pre-registered and simulated CPU-side
only. It is distinct from the failed K2 prompt modifier, does not touch runtime or prompts, and remains
unvalidated until it beats baselines on trusted outcome-labelled traces without post-hoc parameter tuning.**
