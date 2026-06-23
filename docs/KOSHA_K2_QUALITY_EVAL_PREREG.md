# Kosha K2 — Generation Quality Evaluation — PRE-REGISTRATION

> **Status: DESIGN ONLY, doc-only, locked before any run.** Tests whether the K1.1 Kosha depth layer, on
> top of the validated C×R×S wrapper, **improves answer quality without regressing C×R×S frame correctness,
> rejected-domain avoidance, or factuality.** Kosha stays **disabled by default**; C×R×S is **unchanged**;
> no training; no Guna/Vritti/Bhava; no runtime wiring; no consciousness claim; **no model-as-judge**; no
> post-hoc tuning.

## 1. Prior results being followed up
- **K1 / K1.1:** Kosha implemented as an optional deterministic depth/readiness prompt layer; selector is at
  K1.1 (additive scoring + secondary level). **Selector accuracy is a sanity check, NOT validation.**
  (`docs/KOSHA_INFERENCE_LAYER.md`, `docs/KOSHA_SELECTOR_K1_1_PREREG.md`.)
- **Open question (this doc):** does *enabling* Kosha actually produce better answers — or at least change
  depth as intended — **without harming** the validated C×R×S behavior?

## 2. Motivation
K1.1 proves Kosha *picks* a depth level sensibly. It says nothing about generation. K2 is the first test
that touches answer text: it measures (a) that Kosha does **no harm** to the validated frame/factuality
metrics, and (b) whether it **changes answer depth as intended** and improves clarity/usefulness. "No harm"
is the gating requirement; "improves quality" is the upside.

## 3. Hypotheses
- **H1 (primary, guardrail):** frame+Kosha does **not** regress `primary_frame_correct`,
  `rejected_domain_avoidance`, or `factuality_preserved` vs frame-only (within tolerance).
- **H2 (benefit):** frame+Kosha **increases depth-conformance** (answers structurally match the selected
  Kosha level) and/or `clarity_usefulness`, vs frame-only, **without** reducing `must_include_recall`.
- **H0 (null):** Kosha changes nothing measurable, or it harms a guardrail metric.

## 4. Non-goals
No training; no DPO; no Guna/Vritti/Bhava; no 32-D head; no runtime wiring; no C×R×S change; no
model-as-judge (the LLM under test is not its own grader); no human-preference claim (that is a future K3);
no post-hoc threshold/weight tuning of Kosha or the rubric. Beating frame-only is **not** required for a
"safe" verdict — frame-only may remain best and Kosha may still be a no-harm optional layer.

## 5. Evaluation arms
Kosha layers on the validated wrapper, so the core comparison is two arms (plus base for context):
| arm | model | prompt |
|---|---|---|
| **(ctx) A** | base Mistral | plain (context only; not the comparison) |
| **W** | base Mistral + C×R×S wrapper | framed (`kosha=None`) — the validated baseline |
| **W+K** | base Mistral + C×R×S wrapper + **Kosha** | framed + depth modifier (`enable_kosha=True`) |
**Primary comparison: W+K vs W.** (Stacking onto a fine-tuned LoRA is explicitly out of scope — T1 showed
LoRA+wrapper interference; K2 tests Kosha on the *base* wrapper only.)

## 6. Dataset plan
The current C×R×S eval set is depth-uniform (word-sense framing questions), so it does **not** exercise
Kosha. K2 needs a **depth-varied** query set:
- For each of several in-registry topics/terms, author query variants targeting each intended depth
  (surface / practical / context / reasoning / synthesis), each carrying a **C×R×S-computable frame**
  (term + domains in the engine's 23-domain registry) and, where applicable, `must_include` constraints.
- **Targets:** ≥ **100** test queries (prefer 150–200), spanning all five Kosha levels + mixed-cue cases +
  high-stakes cautious cases + negative controls (queries with no depth cue → default).
- Each query carries an **intended depth label** (for depth-conformance scoring) authored **independently**
  of the Kosha selector output (label = human intent, not the selector's prediction).

## 7. Metrics
**Guardrail (must NOT regress — same validated `rubric_v2` + Phase 3 audit, no new judge):**
`primary_frame_correct · rejected_domain_avoidance · factuality_preserved · must_include_recall`.

**Quality / benefit (deterministic; no model-as-judge):**
- `depth_conformance` — does the answer's structure match the selected Kosha level, by deterministic checks:
  e.g. ANNAMAYA → short/concise (word-count band); PRANAMAYA → contains step/imperative markers;
  MANOMAYA → acknowledges concern/uncertainty; VIJNANAMAYA → contains comparison/tradeoff language;
  ANANDAMAYA → contains synthesis/principle language. (A transparent, rule-based conformance scorer,
  pre-registered, NOT an LLM judge.)
- `clarity_usefulness` (rubric clarity proxy) · `answer_length` / `terse_rate` / `over_framing_rate`.

**Per-slice** (all metrics): each Kosha level · mixed-cue · high-stakes · negative-control. Bootstrap CIs on
all primary deltas (W+K − W).

> **Honest measurement caveat (stated up front):** `depth_conformance` measures whether Kosha *changed depth
> as intended*, NOT whether the answer is *better for the user*. True quality/preference is a **future K3**
> (human or independent-judge eval). K2's positive claim is bounded to "changes depth as intended +
> preserves frame/factuality/recall + does not reduce clarity."

## 8. Decision labels (use exactly these)
`CG_KOSHA_K2_ADDS_QUALITY · CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN · CG_KOSHA_K2_FRAME_ONLY_BEST ·
CG_KOSHA_K2_DEGRADES_FRAME · CG_KOSHA_K2_DEGRADES_FACTUALITY · CG_KOSHA_K2_DEGRADES_RECALL ·
CG_KOSHA_K2_INSUFFICIENT_POWER · CG_KOSHA_K2_ENV_UNAVAILABLE`

## 9. Pass/fail gates
**Guardrail first (any failure → the corresponding DEGRADES label, regardless of upside):**
- `primary_frame_correct(W+K) ≥ W − 0.02` and `rejected_domain_avoidance(W+K) ≥ W − 0.02` else
  `CG_KOSHA_K2_DEGRADES_FRAME`;
- `factuality_preserved(W+K) ≥ W − 0.02` else `CG_KOSHA_K2_DEGRADES_FACTUALITY`;
- `must_include_recall(W+K) ≥ W − 0.03` else `CG_KOSHA_K2_DEGRADES_RECALL`.

**Then quality:** `CG_KOSHA_K2_ADDS_QUALITY` requires ALL:
1. guardrails all pass;
2. W+K beats W on `depth_conformance` **or** `clarity_usefulness` with **bootstrap CI lower bound > 0**;
3. improvement holds on **≥ 2 Kosha-level slices** (not one level only);
4. `terse_rate` / `over_framing_rate` not increased beyond pre-set tolerance (+0.05).

**Otherwise:**
- guardrails pass but no significant quality gain → `CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN` (Kosha is a safe,
  optional layer that didn't measurably help — keep off-by-default, no harm).
- frame-only clearly best on the quality metric too → `CG_KOSHA_K2_FRAME_ONLY_BEST`.
- CIs too wide / n below plan → `CG_KOSHA_K2_INSUFFICIENT_POWER`. No GPU → `CG_KOSHA_K2_ENV_UNAVAILABLE`.

## 10. Power
T1 showed `n_test=20` was too small. K2 targets **n_test ≥ 100 (prefer 150–200)**, bootstrap CIs on all
W+K−W deltas. Generation is greedy/deterministic (no seed variance), so power comes from **test size +
depth-slice coverage** (≥ ~8 per Kosha level). Below plan → `INSUFFICIENT_POWER`, not a forced verdict.

## 11. Leakage / fairness controls
- W and W+K use the **same** model, decoding, and C×R×S frame; the **only** difference is the inserted
  Kosha depth block — so any delta is attributable to Kosha.
- Same `rubric_v2` + Phase 3 audit scores both arms identically; **no LLM judge**.
- `depth_conformance` is scored against the **intended** depth label (authored independently of the
  selector), not the selector's own prediction (no circularity).
- No target/reference answers in prompts; high-stakes queries keep the cautious modifier.

## 12. Risks
- **Depth-conformance ≠ quality** — the central caveat; K2 cannot claim "better answers," only "intended
  depth change + no harm." Over-reading it is the main risk.
- **Kosha could harm frame adherence** (the depth modifier competes with the frame instruction) — exactly
  what the guardrail gate is for; a `DEGRADES_FRAME` outcome is acceptable and informative.
- **Dataset authoring bias** — depth labels are author intuition; report inter-label ambiguity and keep the
  conformance checks simple/transparent.
- **Small n** → `INSUFFICIENT_POWER`.

## 13. Interpretation rules
- A **guardrail regression** means Kosha is **not** safe to enable as-is → keep off, redesign modifier
  (new pre-reg). This is the most important outcome to catch.
- `SAFE_NO_QUALITY_GAIN` is a legitimate, common result: Kosha is harmless but unproven-useful → stays
  off-by-default, optional.
- `ADDS_QUALITY` (bounded to depth-conformance/clarity) would justify a **K3 human/independent-judge
  preference eval** before any default-on or runtime claim — **not** auto-enabling.

## 14. Future work (only after K2)
- K2 guardrail-safe **and** ADDS_QUALITY → **K3**: human/independent-judge preference eval (real quality).
- K2 SAFE_NO_QUALITY_GAIN → keep Kosha optional; revisit modifier design only if motivated.
- K2 DEGRADES_* → redesign the Kosha modifier under a new pre-reg; do not enable.
- Guna/Vritti/Kosha *training* heads remain separate future tracks; Bhava remains interpretive, not a
  training target.

## 15. Current valid claim
*Kosha is implemented as an optional inference-time depth/readiness prompt-control layer (selector at K1.1),
disabled by default and separate from C×R×S. It is not yet validated as a quality-improving signal; K2 is
pre-registered to test whether enabling it changes answer depth as intended without regressing C×R×S frame
correctness, rejected-domain avoidance, or factuality — before any human-preference (K3) or runtime claim.*
