# Hybrid LLM vNext — Packaging Readiness

**Audit date:** 2026-08-03

## Verdict: `REQUIRES_DECISIVE_EXPERIMENT_FIRST`

An architecture is **selected** (`SELECT_KDA_HYBRID`, fallback GDN, conservative fallback conventional
attention) but the package **may not be created yet**. The default is deliberately **not** "ready."

## Why not ready

The packaging gate requires all of the following; current status:

| # | Gate | Status |
|---|---|---|
| 1 | A non-Phase canonical architecture is selected | ✅ KDA-MLA hybrid selected |
| 2 | Its algorithm and license are verified | ✅ KDA/MLA defined; MIT (Kimi Linear) |
| 3 | An implementation path is defined | ✅ FLA kernels + vLLM/SGLang |
| 4 | True recurrent decoding demonstrated where claimed | ⛔ **not yet** — must be shown on the vNext model (Phase era failed this: full-prefix replay) |
| 5 | No hidden full-prefix replay | ⛔ **must be proven** on the vNext decode path |
| 6 | No linear layer constructs an N×N sequence-score tensor | ⛔ **must be hook-verified** on the vNext implementation |
| 7 | A trained-language-model result exists (for the intended core) | ⛔ **not yet** — external evidence exists, but no Ugence-trained matched result |
| 8 | Matched baselines and causal ablations defined | ✅ Falsification Plan + thresholds pre-registered |
| 9 | Bounded slots, if retained, independently meet their thresholds | ⛔ **not yet** — current slot evidence is fragile single-fact (1/3 seeds) |

Gates 4–7 and 9 are **empirical** and can only be closed by the decisive experiment (H22), which this
audit explicitly does **not** run.

## Evidence gate that must be met before packaging starts

Run the pre-registered matched experiment (Falsification Plan). Packaging may begin **only when**:
1. Arm **C** (KDA + periodic MLA) clears the LM (improvement-or-parity), robust multi-seed retrieval, and
   **binding-beyond-single-fact** gates at matched budget, and beats/holds parity with the conventional
   attention baseline **E**;
2. the vNext decode path is proven **true-recurrent / compressed-KV** with **no full-prefix replay** and
   **no N×N** in linear-only layers (hook-verified);
3. bounded slots, **if** included, independently pass T4–T6 (binding, source, supersession) with causal
   slots-off degradation — otherwise the package ships backbone-only and slots stay an optional extension.

If the experiment fails for all arms, the verdict becomes `NO_CANONICAL_ARCHITECTURE_SELECTED` and
packaging does not begin.

## What is explicitly NOT authorized in this phase

No `packages/models/hybrid-llm/`, no `ugence-hybrid-llm` / `ugence_hybrid_llm`, no source moves, no
compatibility shims, no consumer-import changes, no wheel, no canonical-architecture rename, no investor
brief updated as if the decision were final. **H22 is not implemented.** This audit produces documentation,
machine-readable evidence artifacts, and narrowly-scoped verification scripts only.

## Maturity label

**AUDITED · ARCHITECTURE_SELECTED · EXPERIMENT_REQUIRED.** Not production-ready, not state-of-the-art,
not enterprise-validated — none of those are claimed.
