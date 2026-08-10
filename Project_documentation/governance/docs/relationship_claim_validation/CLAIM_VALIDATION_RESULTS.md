# Claim Validation Results (v0.1)

Primary results for the full system (V4) vs the no-validation baseline (V0). All
figures from the deterministic run (`results/run_v0_1.json`).

> **Scope (binding).** Self-authored synthetic corpus; deterministic (non-LLM)
> judges; no external pipeline. V4's perfect scores are **by construction**. This is
> mechanism validation, **not** evidence of real-world error reduction. Production
> deployment: **NO** (`FINAL_VERDICT.md`).

---

## 1. Primary endpoint — relationship precision

| | V0 (baseline) | V4 (full) |
|---|--:|--:|
| Precision (retained set) | 0.4167 | **1.0000** |
| Recall | 1.0000 | **1.0000** |
| Unsupported relationships removed (tn) | 0 / 28 | **28 / 28** |
| Supported relationships preserved (tp) | 20 / 20 | **20 / 20** |
| False removals (fn) | 0 | **0** |
| False acceptances (fp) | 28 | **0** |
| Status accuracy | 0.2500 | **1.0000** |

## 2. Primary endpoint — paired fixes/breaks (V4 vs V0)

- **Fixes: 28** — every relationship the baseline wrongly retained (8 contradicted,
  8 unsupported, 8 insufficient, 4 unknown) is correctly dropped/flagged.
- **Breaks: 0** — no correctly-supported relationship (12 supported + 8
  partially-supported) was removed.
- **Net: +28**, net-fix-rate **0.5833**, bootstrap 95% CI **[0.4375, 0.7083]**
  (excludes 0).

## 3. Hypotheses

- **H1 (primary):** supported ✓ *on this corpus* — claim validation reduced
  unsupported relationships (fp 28→0) while preserving supported ones (recall 1.0).
- **H0 (null):** rejected *on this corpus* — the effect (net +28, CI excludes 0) is
  not zero.
- **HA (alternative):** consistent — fixes 28, breaks 0.

**These conclusions are corpus-internal and construction-driven.** The judges
implement the grounding logic the gold encodes, so a strong result is expected; the
scientific content is the **ablation decomposition** (§`ABLATION_RESULTS.md`), which
shows each component's distinct, non-redundant contribution — not the headline
perfection.

## 4. Secondary endpoints

| Endpoint | Value |
|---|---|
| False removals (V4) | 0 |
| False acceptances (V4) | 0 |
| Recall (V4) | 1.0 |
| Governance impact | N/A — no governance stage exists in this repo (not modified) |
| Packet impact | N/A — no packet stage exists in this repo (not modified) |
| Runtime determinism | two runs byte-identical |
| Judge adjudications | 4 (the equally-explicit direction conflicts) |
| Evidence completeness | every retained/removed decision carries span or deterministic provenance |

## 5. Governance / packet unchanged

There is no frozen governance or packet implementation in this repository to change.
This experiment adds a stand-alone package and modifies nothing else; the
"governance and packet unchanged" precondition holds **vacuously** and is verified
by `git status` (only the new package + docs are added).
