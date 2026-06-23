# RESULTS — Kosha K2: frame-only (W) vs frame+Kosha (W+K) generation quality

> **Decision: `CG_KOSHA_K2_DEGRADES_FRAME`.** Enabling the Kosha depth layer on top of the validated C×R×S
> wrapper **regresses C×R×S frame correctness, rejected-domain avoidance, factuality, and recall.** Per the
> pre-registered guardrail-first gate (`docs/KOSHA_K2_QUALITY_EVAL_PREREG.md` §9/§13), Kosha is **NOT safe
> to enable as-is** → it **stays disabled by default**; the depth modifier needs redesign under a new
> pre-registration. No post-hoc tuning.

## 1. Run
- **Data:** `kosha_k2_queries.json` (105 depth-varied queries, all 5 levels + mixed + negative-control).
- **Arms:** W = base Mistral + C×R×S wrapper (`kosha=None`); W+K = same + Kosha depth modifier. Same model,
  same frame; the **only** difference is the inserted depth block → delta attributable to Kosha.
- **Scoring:** validated `rubric_v2` (guardrails) + deterministic `depth_conformance`. Real Mistral
  (bf16), greedy. No model-as-judge.

## 2. Result (n = 105)
| metric | W | W+K | Δ |
|---|---|---|---|
| **primary_frame_correct** | **0.819** | **0.781** | **−0.038** ❌ |
| **rejected_domain_avoidance** | **1.000** | **0.971** | **−0.029** ❌ |
| **factuality_preserved** | **1.000** | **0.962** | **−0.038** ❌ |
| **must_include_recall** | **0.705** | **0.657** | **−0.048** ❌ |
| depth_conformance | 0.619 | 0.705 | +0.086 (CI [−0.01, 0.18], **incl. 0**) |
| clarity_usefulness | 0.876 | 0.857 | −0.019 (CI incl. 0) |
| answer_length (words) | 118.3 | 107.8 | −10.5 (shorter) |
| over_framing_rate | 0.010 | 0.019 | +0.010 |
| slices_improved (depth) | — | — | 2 |

## 3. Verdict vs the §9 gate (guardrail-first)
Guardrails dominate any upside. The candidate fails **all four**:
- `primary_frame_correct` 0.781 < 0.799 (W−0.02) → **`DEGRADES_FRAME`** (the returned label).
- `rejected_domain_avoidance` 0.971 < 0.98 (W−0.02) → also frame degrade.
- `factuality_preserved` 0.962 < 0.98 (W−0.02) → would be `DEGRADES_FACTUALITY`.
- `must_include_recall` 0.657 < 0.675 (W−0.03) → would be `DEGRADES_RECALL`.
Even the quality side does **not** qualify: depth_conformance Δ CI includes 0; clarity slightly negative.

## 4. Honest reading
- **Kosha's depth steering partly "works"** — depth_conformance rose 0.619→0.705 (answers took more of the
  intended shape). But it is **not significant** (CI through 0) and is **irrelevant** under the gate,
  because…
- **…the depth instruction degrades the C×R×S frame.** Adding "answer at depth X" alongside the frame
  instruction pulled the model off primary-frame adherence (0.819→0.781), let a little rejected-domain
  leakage in (1.00→0.971), and made answers shorter (118→108 words) — dropping factuality-proxy and
  must-include recall. The depth modifier **competes with** the frame instruction.
- This is the exact failure the guardrail-first gate exists to catch. It is an **important negative**, not
  a tuning problem.

## 5. Close-out (pre-reg §13)
- **Kosha stays OFF by default** (it already is; `build_framed_prompt(kosha=None)` is byte-for-byte the
  validated prompt). Do **not** enable it on top of the wrapper.
- **Do NOT proceed to K3** (human-preference eval) — K3 was gated on K2 being guardrail-safe + adding
  quality; it is neither.
- **No post-hoc tuning** of the modifier to rescue this run. Redesigning the depth modifier so it does not
  compete with the frame (e.g. depth as a *post-frame* light touch, or only on non-frame-critical queries)
  is a **new hypothesis → new pre-registration**.
- C×R×S wrapper unchanged; runtime unchanged; selector (K1.1) unaffected (it remains a correct depth
  *selector*; the problem is the generation-time *modifier* interfering with the frame).

## 6. Standing claim (updated)
*Kosha is implemented as an optional, deterministic inference-time depth/readiness layer (selector at
K1.1), disabled by default. On the K2 generation eval it **degraded C×R×S frame correctness,
rejected-domain avoidance, factuality, and recall** when enabled, so it remains **off-by-default and is not
a validated quality layer**. The validated product is unchanged: C×R×S wrapper + framed generation +
Phase 3 audit.*
