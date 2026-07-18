# C×R×S Phase 4D — Guna/Vritti-Controlled Residual Bhava — RESULT

> **Verdict: `PHASE4D_LEAKAGE_SUSPECTED` (all targets). The Guna/Vritti/Bhava decomposition cannot be
> cleanly applied to these audit labels, and the residual carries no incremental signal regardless.**
> Per the locked kill criterion (`CSR_MATCH_FILTER_PHASE4D_RESIDUAL_BHAVA.md §9`), this track STOPS.
> No Bhava wiring; no model/weight/logit/hidden-state change; no Phase 1–3 change. C×R×S remains the
> product.

Run: `runs/csr_phase4_v3` (n=1032), framed arm, rich PCA-256, seeds 0–2 × hidden_dim {32,64},
group-by-term CV, within-arm.

## Leakage gate (run first) — fired on every target
| target | Guna→target | **Vritti→target** | Guna+Vritti→target | gate |
|---|---|---|---|---|
| frame_violation | 0.53 (clean) | **0.94** | 0.68 | LEAKAGE (>0.70) |
| rejected_domain_leak | 0.64 (clean) | **0.89** | 0.69 | LEAKAGE |
| audit_fail | 0.52 (clean) | **0.95** | 0.77 | LEAKAGE |
| secondary_promoted | 0.59 (clean) | **0.84** | 0.67 | LEAKAGE |

**Why (structural, pre-registered caveat):** the targets are audit ORs of the very drift finding-types
the Vritti proxy is built from (`frame_violation` ⊇ `rejected_domain_promoted` and
`secondary_promoted_to_primary`; `audit_fail` ⊇ the frame findings). So "Vritti" is **definitionally
nested** in the targets — controlling for it partly controls for the target. Guna (quality:
`answer_too_generic OR factuality_suspected`) is clean (≤0.64), but Vritti cannot be cleanly separated.

## Even ignoring leakage — residual adds nothing
| target | hidden_only | residual_only | hidden+residual | Δ vs hidden | Δ vs noise | Δ vs n-gram | eff. rank |
|---|---|---|---|---|---|---|---|
| frame_violation | 0.76–0.80 | 0.52–0.54 | 0.75–0.80 | −0.019…+0.004 | −0.013…+0.010 | +0.09…+0.15 | 11.9 |
| rejected_domain_leak | 0.78–0.83 | 0.64–0.65 | 0.77–0.82 | −0.028…+0.003 | −0.019…+0.008 | +0.05…+0.11 | 11.9 |
| audit_fail | 0.74–0.80 | 0.51–0.53 | 0.74–0.80 | ≈0 | ≈0 | +0.11…+0.16 | 11.9 |
| secondary_promoted | 0.80–0.88 | 0.45–0.56 | 0.78–0.86 | −0.022…0.0 | ≈0/neg | +0.12…+0.23 | 11.9 |

`hidden+residual ≈ hidden_only` (d_h ≈ 0/neg across all 24 configs); `residual_only` is at/near chance;
no collapse (eff. rank 11.9); `Guna+Vritti` (0.60–0.72) is below `hidden_only`. The strict gate fails
on every config (`gate_pass_frac = 0`).

## Decision (per kill criterion §9)
**`PHASE4D_LEAKAGE_SUSPECTED` → STOP.** No post-hoc search for a different residualization or label
set; any future attempt is a new pre-registration. No Phase 5. The honest statement:
*the Guna/Vritti decomposition is not separable from the audit targets on this taxonomy, and a residual
Bhava read adds no signal beyond hidden-only.*

## What this adds to the record
- Reinforces the closed-Stage-B2 conclusion from a different angle: **hidden-only is sufficient**; no
  Bhava-structured read (supervised object-mode in B2, or Guna/Vritti-residual here) adds value.
- Surfaces a genuine conceptual finding: the Guna/Vritti/Bhava categories **do not map onto the
  available audit labels without circularity** — the audit's failure taxonomy already *is* the "Vritti"
  layer, so there is no clean residual to attribute to "Bhava."
- Side-finding (again): the hidden-only failure signal beats a surface n-gram baseline → it is more
  than lexical.

## Interpretation boundaries (unchanged)
No claim of consciousness, proof, generation-activity, runtime wiring, causal control, or cross-model
generalization. C×R×S Phase 1–3 is the product; Bhava stays out of runtime.
