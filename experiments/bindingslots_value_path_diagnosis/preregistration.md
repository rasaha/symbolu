# Preregistration — BindingSlots Instrumented Reproduction, Value-Path Isolation, and Gradient-Conflict Diagnosis

**Diagnostic phase only. No fix is implemented. KDA validation remains BLOCKED and
`READY_FOR_KDA_VALIDATION` is never emitted.**

This preregistration, the frozen cohort (`cohort.json`), the reproduction protocol
(`reproduction_protocol.json`), and every decision threshold (`diagnosis_classify.py`
`FROZEN_CONSTANTS`) are fixed **before any newly captured tensor is inspected**.

## 0. Prerequisite (must pass or stop `BINDINGSLOTS_DIAGNOSTIC_PREREQUISITE_FAILED`)

- Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`; persistence merge
  `05dcee8e…` reachable from the current default tip; PR #1340 closed + merged.
- Reconstructed verdict `NO_PERSISTENCE_INTERVENTION_SELECTED` / `KDA_VALIDATION_BLOCKED`.
- Provenance: A+/R0/O1R at `5cc392e1`; H2/O1 at `9380bdb1` (authorized H2 fidelity correction);
  frozen `abc.json` `b31989a3…` unchanged; inherited tests + verifiers pass; tree clean.

## 1. Two independent scientific questions

1. **Value path (Q1):** where does usable needle information disappear when the fixed routing
   diagnostic still prefers the written slot but end-to-end retrieval fails?
2. **Quality (Q2):** which persistence or teacher gradients are responsible for the *separate*
   language-quality regressions?

These are **not assumed to share a cause.**

## 2. Scope restrictions

No new intervention, no coefficient tuning, no architecture change, no extra slots/dimensions, no
Phase / KDA / MLA / quadratic attention / model scaling / new objective / NL-enterprise expansion,
and **no next-phase fix** in this PR.

## 3. Deterministic reproduction (authorized)

No saved weight checkpoints exist, so we perform deterministic **reproduction-for-instrumentation**
by running the **frozen** `persistence_arms.run_arm` unchanged. No training step is added, removed,
or altered. Model snapshots at **600 / 700 / 900 / 1200** are `deepcopy` pure-observers taken at the
committed `record(step)` boundary (they consume no torch RNG, touch no optimizer state). Hooks are
disabled by default; with hooks disabled the execution path reproduces the committed trajectory.

**Gate = EXACT equality** at every checkpoint (needle, correct-slot probability/rank, address
margin, distances, perplexity, ablations, loss log). This is justified because the runs are
deterministic CPU fp32 and the diagnostics never advance the training RNG — proven on control run
**A+ seed 25** (byte-identical) *before* any failure exemplar. No numerical tolerance is fit to
data. A run failing the gate is `INSTRUMENTED_REPRODUCTION_FAILED` and its tensors are not used as
evidence. `threads=4` is preserved (changing it would change fp32 reduction order), so reproduction
is sequential.

## 4. Frozen cohort (see `cohort.json`)

Symmetric **{A+, R0, O1R, H2} × {23, 24, 25}** (12 runs), recovered mechanically from the merged
persistence ledger, covering every required exemplar: H2 s23 (routing-probe/eval-retrieval
dissociation), H2 s24 (weak `CLEAN_STABLE` former), H2 s25 (quality failure), O1R quality-failed
(24, 25) + O1R clean control (23), R0 `CLEAN_STABLE` (24), R0 `FORMED_THEN_COLLAPSED` (23), R0
`QUALITY_FAILED` (25), and same-seed A+ controls (23, 24, 25). No seed is added/replaced on any
diagnostic outcome.

## 5. Architecture binding (see `tensor_manifest.json`)

Read path is `u_read = Σ_j r[j]·slot[j] ; c_mem = W_o(u_read) ; h_post = h_pre + c_mem`. **There is
no learned read or fusion gate** — fusion-gate values / sensitivity / gradients are never reported.
Captured per slot layer: written value `W_wv(norm(x))@fact`, write address, `s*`,
`m_postwrite[s*]`, `m_query[s*]`, read address, `u_read`, `c_mem`, residual `h_pre/h_post`, decoder
state, answer-position logits. The instrumented forward is byte-identical to the frozen forward when
`mode=None` (proven no-op).

## 6. Diagnostics

- **A1 slot-value integrity:** `m_postwrite[s*]` vs `m_query[s*]` — cosine, normalized L2 drift,
  norm ratio, sign-change rate, saturation, later-write count, explicit-overwrite flag.
- **A2 linear decodability (analysis-only):** frozen linear probes predict the needle value from
  `m_postwrite[s*]` and `m_query[s*]`; fixed probe seed `20260804` (disjoint from ledger eval
  seeds), fixed 0.6/0.2/0.2 split, shuffled-label + non-target-slot controls; probe weights never
  written to the model; a stagewise decodability profile across 600/700/900/1200. Probe failure =
  low linear decodability, **not** proof of total information absence.
- **A3 oracle correct-slot address:** on the **actual failed eval examples**, force `r[s*]=1`; keep
  slot values, `W_o`, residual, backbone, decoder. For H2 s23, terminal randomized-address /
  slots-off are **non-informative** (baseline already 0); the oracle bypasses are the evidence.
- **A4a direct query-time read:** `u_read = m_query[s*]`. **A4b restore post-write value:**
  `c_mem = W_o(m_postwrite[s*])`, `h_post = h_pre + c_mem`. No "canonical representation" invented.
- **B2 no-update gradient norms** and **B3 alignment:** LM vs persistence (O1R correct-slot) vs H2
  teacher KL, per parameter group (embeddings, backbone, slot_keys, write/read address projections,
  write-value projection, write gate, `W_o`, slot norm — complete + non-overlapping); zero optimizer
  steps, grads cleared each measurement, snapshot hashes unchanged, zero-gradient-safe cosine.

## 7. Frozen decision constants (`diagnosis_classify.py`)

`DECODABLE_MIN=0.50`, `MATERIAL_DROP=0.20`, `RETRIEVAL_PRESENT_MIN=0.50`, `RETRIEVAL_FAILS_MAX=0.10`,
`RECOVER_MIN=0.50`, `CONFLICT_COS=−0.10`, `CONTROL_GAP=0.15`. Set from the read-path structure and
control runs, **not** from failure exemplars.

### Mechanical value-path rules (per seed, priority order)
- `STORAGE_VALUE_DEGRADED` — post-write decodable, query decodability materially lost, restoring the
  post-write value recovers retrieval.
- `ADDRESS_DISTRIBUTION_FAILED` — query slot still decodable, ordinary retrieval fails, oracle
  one-hot address restores retrieval.
- `READ_AGGREGATION_FAILED` — query slot decodable, oracle address does **not** recover, direct
  query-time read recovers.
- `RESIDUAL_OR_DECODER_UTILIZATION_FAILED` — target-slot info recoverable, oracle memory
  contribution delivered to the residual, retrieval still does not recover.
- `VALUE_PATH_NOT_LOCALIZED` / `NOT_APPLICABLE_RETRIEVAL_PRESENT`.

### Mechanical quality rule
- `QUALITY_GRADIENT_CONFLICT_LOCALIZED` — a quality-failed seed shows materially negative LM-vs-
  (persist|teacher) alignment (`≤ −0.10`) in a shared parameter group, weaker in the clean control
  by `≥ 0.15`; else `QUALITY_INTERFERENCE_NOT_LOCALIZED`.

## 8. Verdict (exactly one) + `KDA_VALIDATION_BLOCKED` always

`BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED` · `…_VALUE_PATH_FAILURE_LOCALIZED` ·
`…_QUALITY_INTERFERENCE_LOCALIZED` · `…_DIAGNOSTIC_RESULTS_INCONCLUSIVE` ·
`…_INSTRUMENTED_REPRODUCTION_FAILED` · `…_DIAGNOSTIC_PROTOCOL_VIOLATED` ·
`…_DIAGNOSTIC_INTEGRITY_FAILED` · `…_DIAGNOSTIC_RESOURCE_BLOCKED`. This phase cannot unblock KDA.

## 9. Stop condition

Reproduction accepted/rejected; A1–A4 complete for accepted runs; B2–B3 complete; per-seed diagnoses
generated mechanically; integrity passes; artifacts committed + hashed; one draft PR open, unmerged.
No fix, no coefficient tuning, no KDA, no subsequent intervention phase.
