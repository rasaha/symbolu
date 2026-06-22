# RESULTS — P-B: does CSR_policy beat the Phase 3 `needs_rewrite` gate?

> **Decision: `PB_POLICY_NO_INCREMENTAL_VALUE`. Kill criterion fires → policy track stopped, P-C NOT
> built.** The pre-registered question (`docs/CSR_GUNA_VRITTI_POLICY_PB_PREREG.md`) is answered: a
> deterministic `CSR_policy` built from existing diagnostics does **not** beat the existing Phase 3 audit
> `needs_rewrite` gate. It is significantly **worse**. No post-hoc re-tuning (per §8 of the pre-reg).

## 1. Run (reproducible)
- **Input:** `robustness_eval_v2.json` — the validated Phase 2B-v2 real-Mistral traces
  (`production_valid=True`, 110 examples × 2 arms = **220 rows**), persisted on the RunPod
  `/workspace` network volume.
- **Command:**
  ```bash
  python scripts/cg_wrapper_ablation/csr_match_filter/csr_policy_eval.py \
    --traces robustness_eval_v2.json --out csr_policy_eval.json
  ```
- **Outputs:** `csr_policy_eval.json` + `csr_policy_eval.md` (on the pod volume).
- **Code/tests:** `scripts/cg_wrapper_ablation/csr_match_filter/csr_policy_eval.py` (commit `21dcbe0`);
  `tests/test_csr_policy_eval.py` (9 synthetic-row tests, all decision labels exercised, CPU-only).

## 2. Result (verbatim)
```
P-B — CSR_policy vs Phase 3 needs_rewrite
  n=220 pos=78  baseline F1=0.526  policy F1=0.341  ΔF1=-0.185 [CI>0]
  false_rewrite base=0.162 policy=0.204  agreement=0.855
  term_contribution_f1={'inv_match': 0.152, 'traj': 0.357, 'guna': 0.0, 'sev': 0.012}
  DECISION: PB_POLICY_NO_INCREMENTAL_VALUE
```

| metric | baseline (`needs_rewrite`) | CSR_policy | verdict |
|---|---|---|---|
| F1 (primary) | **0.526** | 0.341 | policy worse by **ΔF1 = −0.185**, bootstrap CI excludes 0 (i.e. significantly negative) |
| false-rewrite rate | **0.162** | 0.204 | policy **higher** (worse), exceeds the +0.02 tolerance |
| decision agreement | — | 0.855 | not repackaging (< 0.97) — policy makes *different*, *worse* calls |
| positives (rubric residuals) | 78 / 220 | — | enough label power to decide (not `INSUFFICIENT`) |

**Term contribution (marginal F1, single-term policy):** `traj = 0.357`, `inv_match = 0.152`,
`sev = 0.012`, `guna = 0.0`. The trajectory term carries essentially all of the (still sub-baseline)
signal; `(1−MATCH_primary)` adds a little; `guna_quality` and `audit_severity` add ~nothing. Even the
best single term (traj, 0.357) is **below** the baseline gate (0.526).

## 3. Verdict against the pre-registered success gate (§7)
`PB_POLICY_BEATS_AUDIT_GATE` requires **all** of §7. The result fails at the first clause:
1. **Beat baseline on the primary metric with CI excluding 0** — ❌ ΔF1 = −0.185, CI excludes 0 in the
   **wrong** direction (significantly worse).
2. Not worsen missed-critical rate — n/a (gate already failed at 1).
3. Not increase false-rewrite beyond +0.02 — ❌ 0.204 vs 0.162 (≈ +0.042).
4. Improve ≥1 meaningful failure class — ❌ no class recovered net-positive (policy F1 strictly lower).
5. Non-overlap partition holds — ✅ (no `PB_TERM_OVERLAP_INVALID`; the disjoint partition was emitted).
6. Enough labelled positives — ✅ (78 positives; not `PB_INSUFFICIENT_LABEL_POWER`).

→ **`PB_POLICY_NO_INCREMENTAL_VALUE`.**

## 4. Why (honest reading)
This is the pre-registered honest prior (§10), and the mechanism is clear:
- The Phase 3 `needs_rewrite` gate is **narrow and precise** — it fires only on *critical*
  `rejected_domain_promoted` / `phoneme_overreach_claim`. On these traces that narrowness gives it a
  high-precision F1 (0.526).
- The candidate's only genuinely new degrees of freedom were `(1−MATCH_primary)` and the freedom to flag
  *non-critical* residuals. In practice flagging the broader trajectory-drift / generic residuals
  **trades precision for recall badly**: it raises the false-rewrite rate (0.162 → 0.204) without a
  compensating recall gain, so pooled F1 drops.
- `guna_quality` contributed **0.0** — `answer_too_generic` does not predict the rubric residuals at all
  on this set. `audit_severity` contributed **0.012** — almost nothing once the critical findings are
  already captured by the narrow gate.
- Decision agreement 0.855 rules out `PB_AUDIT_REPACKAGING_ONLY`: the policy is not the audit output
  renamed — it is a *different, worse* decision boundary.

## 5. Close-out (kill criterion — `docs/...PB_PREREG.md` §8)
- **Policy track stopped. P-C is NOT built.** "Anything other than `PB_POLICY_BEATS_AUDIT_GATE` → do not
  build P-C; record the label and stop. No post-hoc re-tuning; a new attempt is a new pre-registration."
- **The product stays exactly as validated:** C×R×S MATCH-filter + the Phase 3 audit `needs_rewrite`
  gate. No runtime change, no threshold change, no audit-logic change resulted from P-B (as pinned).
- **P-A stays diagnostic-only.** `DerivedVrittiTrajectory` / `GunaQualityDiagnostic`
  (`trajectory.py`, `guna.py`) remain observational labels in the audit trace; they are **not** wired
  into any rewrite/escalation decision. The trajectory term *does* carry the most standalone signal
  (0.357), which is consistent with keeping it as a diagnostic, but it does not justify replacing or
  augmenting the gate.
- **Future tracks remain off** unless independently re-pre-registered: canonical five-state `p_v`,
  canonical softmax-3D `p_g`, hidden-risk, and any new Guna-detector weight stayed weight-0 here and are
  untouched.

## 6. What would (and would not) reopen this
- A **new pre-registration** with a *different* ground truth (human-labelled rewrite necessity, not
  rubric_v2 which shares detectors with the audit) could legitimately re-ask the question — the §5 caveat
  (partially-correlated proxy) means this negative is against a proxy, not against human judgement.
- Re-running the **same** comparison with hand-loosened weights/thresholds to chase a positive would
  violate the kill criterion and is explicitly **not** allowed.
