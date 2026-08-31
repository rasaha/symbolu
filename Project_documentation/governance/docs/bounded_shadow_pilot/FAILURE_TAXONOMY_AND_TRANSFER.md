# Natural Failure Taxonomy & Transfer Analysis (Phases 13–14)

## Failure taxonomy (`failure_taxonomy.py` → `eval_results/failure_taxonomy.json`)

How the full governed stack behaves on all 857 natural artifacts, by exhaustive, mutually-exclusive
category (config `FULL_STACK_HIGH_RISK`):

| Category | Count | Rate |
|---|---|---|
| CLEAN_TRANSFER (GT ALLOW → WOULD_ALLOW) | 0 | 0.0% |
| **OVER_QUALIFICATION** (GT ALLOW → WOULD_QUALIFY) | **733** | **85.5%** |
| FALSE_WITHHOLD (GT ALLOW → withheld) | 118 | 13.8% |
| CORRECT_REVIEW (GT REVIEW → withheld/escalated) | 4 | 0.5% |
| RESIDUAL_UNSAFE_QUALIFY (GT REVIEW → WOULD_QUALIFY) | 2 | 0.2% |
| UNSAFE_PERMIT (GT REVIEW → WOULD_ALLOW) | 0 | 0.0% |

Natural-language cause tags (multi-label): `NO_EXTERNAL_EVIDENCE` 763 · `STRONG_CLAIM_UNBACKED` 94 ·
`HEDGED_UNCERTAIN` 18 · `SECURITY_SENSITIVE` 14.

**Dominant failure = OVER_QUALIFICATION, driven by `NO_EXTERNAL_EVIDENCE`.** Natural documentation has no
verifiable evidence bundle, so the honest derived evidence base (`VERIFIED_WITH_LIMITATIONS`) makes the
evidence-grounded runtime qualify almost everything. The taxonomy exhaustively partitions the corpus
(counts sum to n).

## Transfer analysis (`transfer_analysis.py` → `eval_results/transfer_analysis.json`)

Compares against the **frozen** structured evaluation
(`governed_inference_pilot/eval_results/evaluation.json`), read-only — never recomputed or modified.

| Structured reference (CLEAN_LOW_RISK) | Value |
|---|---|
| false_block_rate | 0.0 |
| unnecessary_qualification | 0.0 |
| unsafe_action_escape | 0.0 |
| audit_completeness / replay_determinism | 1.0 / 1.0 |

| Natural full-stack | Value |
|---|---|
| clean_allow_rate | 0.0% |
| over_qualification_rate | 85.5% |
| false_withhold_rate | 13.8% |
| unsafe_permit | 0 |
| residual_unsafe_qualify | 2 |

### Dimension-by-dimension verdict

| Dimension | Verdict | Basis |
|---|---|---|
| **Safety** | **TRANSFERS** | 0 fully-supported unsafe permits on natural artifacts, as on structured cases |
| **Utility** | **DOES NOT TRANSFER** | structured clean cases qualified 0% / blocked 0%; natural benign artifacts over-qualify 85.5% and withhold 13.8% |
| **Auditability** | **TRANSFERS** | frozen audit completeness 1.0; full-stack determinism holds on natural inputs |
| **ActionGate native semantics** | **PRESERVED** | Phase 5: native contract loss 0%, no safety-relevant outcome collapsed |

### Headline

> The **safety** property transfers and **native ActionGate semantics are preserved with zero loss**,
> but **utility does not transfer**: on evidence-free natural text the evidence-grounded runtime emits
> **0% clean allow**, over-qualifying 85.5% and withholding 13.8% of benign documentation, with a small
> residual of **2** review-worthy artifacts delivered as `WOULD_QUALIFY`.

### Primary cause (honest, conditioned)

Natural artifacts carry no verifiable evidence bundles; the honest `VERIFIED_WITH_LIMITATIONS`
derivation drives systematic qualification. This is a property of applying an **evidence-grounded**
runtime to **evidence-free** natural text, conditioned on `natural_derivation_v1`. It is not a safety
regression — it is a utility/calibration finding that directly shapes the architectural decision
(Phase 21): the runtime is safe on natural artifacts but, as configured, not yet *useful* on them
without an evidence-acquisition step or a natural-text calibration of the evidence stage.
