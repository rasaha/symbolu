# Hybrid LLM VC Brief — Changelog v2.0 → v3.0

**This is a reframe, not an additive revision.** v2.0 made `HybridPhaseTransformer` / Protected Phase
the central product and TAP a complementary layer above it. v3.0 makes **Hybrid LLM — the governed
hybrid-intelligence and evidence-reasoning layer — the product**, and demotes Phase to a separate,
currently-unsupported research track. Every number now traces to a committed result artifact
(source-of-truth commit `ae59749`, `FREEZE OK`, 98 frozen-phase + 30 experiment tests).

## Structural changes

1. **Product repositioned.** Center is no longer an attention architecture. Hybrid LLM is defined as
   the layer that decides what is computed exactly, what needs a model, which model, what evidence may
   enter the ledger, and what the AI may claim. The production thesis **no longer depends on Phase**.
2. **Phase separated and demoted.** Pillar-1 "long-context reasoning substrate as primary product" is
   removed. Phase is now an appendix research track with an explicit **UNSUPPORTED (enterprise) /
   RETIRED (product-superiority)** status.
3. **Four-page structure rewritten around the governed pipeline** (problem → architecture → tested
   evidence → commercial/roadmap), replacing the attention-family problem/architecture/landscape pages.
4. **Claim-status taxonomy introduced** (`VALIDATED` / `CONTROLLED-EVIDENCE` / `IMPLEMENTED` /
   `ROADMAP` / `UNSUPPORTED` / `RETIRED`), shown inline in the Page-3 table and in a new machine-readable
   `HYBRID_LLM_VC_CLAIM_LEDGER.json` (18 claims).
5. **Competitive comparison replaced.** Attention-family superiority table removed; replaced with an
   architectural comparison to conventional agentic stacks (proposal-vs-result, TAP-vs-prompting,
   persistent-vs-query-time, deterministic-vs-end-to-end, ActionGate-vs-tool-permission).
6. **New evidence added** from four committed enterprise studies (slots+quadratic, output mapping, field
   prediction, semantic normalization + TAP) plus the Phase auxiliary result.

## Claims removed or materially weakened

- **RETIRED:** "Phase removes the long-context decay tax"; "Phase is a validated global-retrieval
  substrate"; "serial Protected Phase is better than other hybrid architectures"; "quadratic is
  conditionally invoked only where Phase confidence is low, as a product advantage"; "Phase retrieval
  superiority is ready for commercialization."
- **UNSUPPORTED (now stated):** Phase adds causal long-range value in enterprise late fusion (it did
  not; a trained GRU beat it, A3 0.751 ≈ A1 0.752, GRU 0.834; causal dependence failed); serial-fusion
  "gradient competition" advantage (no committed ablation).
- **Weakened from "primary product" to "research appendix":** the entire `HybridPhaseTransformer`
  architecture, 7B recipe, and LRA/needle roadmap — retained only as separated research, with the
  240K-param needle result relabeled *historical mechanism-level evidence*, not product validation.
- **Removed framing:** AGI/"limits any solution to intelligence will navigate" language; "better
  because" superiority claims without matched benchmarks; consciousness-adjacent component naming as
  capability.
- **Corrected attribution:** version accuracy is credited to the **deterministic policy, not
  Quadratic** (active+stale co-survival was only 0.11); the constrained mapper's value is **0.00
  mapping error**, not an end-to-end accuracy lift (field prediction was upstream).
- **Capacity claim corrected:** "K=4 optimal" → "smallest sufficient capacity is contract-dependent"
  (K=4 role task, K=8 outcome contract; K=32 underperforms).

## Claims added or strengthened (with committed evidence)

- Deterministic field computation → **1.00 held-out outcome** (vs 0.64 learned) — CONTROLLED-EVIDENCE.
- Deterministic mapper → **0.00 mapping error**, oracle **1.00** — VALIDATED (given correct fields).
- Normalization safety → **0.00 unsupported-fact admission** at all simulated interpreter qualities;
  ungoverned baseline **17.7%** — CONTROLLED-EVIDENCE.
- TAP → **100%** unsupported/authority-exceedance recall vs **0%** for prompt-only — CONTROLLED-EVIDENCE.
- ID preservation **1.00**, unauthorized inclusion **0.00** — VALIDATED.

## Scope discipline enforced throughout

- Distinguishes **synthetic / controlled / simulated** evidence from **live-model** evidence; the
  semantic interpreter is stated as a **controllable simulator** and live-model validation is ROADMAP.
- Distinguishes **outcome accuracy** from **intermediate field accuracy** (0.955 field macro with 1.00
  outcomes).
- Never uses "validated" for implementation-only or simulator-only results.
- States Phase is **not** in the authorized production path.

## Files

- `HYBRID_LLM_VC_BRIEF_v3.md` (this revision) — v2 left intact at `HYBRID_LLM_VC_BRIEF_v2.md`.
- `HYBRID_LLM_VC_BRIEF_v3_CHANGELOG.md` (this file).
- `HYBRID_LLM_VC_CLAIM_LEDGER.json` (18 material claims with status, artifact, allowed/forbidden wording).
