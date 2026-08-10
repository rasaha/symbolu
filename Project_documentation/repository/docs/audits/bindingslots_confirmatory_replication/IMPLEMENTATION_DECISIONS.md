# Implementation decisions

Decisions made while executing the confirmatory phase, each chosen to preserve the frozen protocol.

## 1. A+ control arm is included (not a deviation)

The frozen Stage B classifier defines formation, margins, causal-collapse thresholds, and the
quality gate **relative to A+**, and A+ is listed in the frozen `stage_b` matrix arms
(`["A+","B0","SELECTED_CANDIDATE"]`). Running A+ is therefore **required** to apply the merged
classifier unchanged. The task's Section 6 permits an architecture-control arm that was part of the
frozen plan and needs no tuning; A+ qualifies and does not change the primary decision rule.

## 2. Fresh seeds 13–17 via the endorsed deterministic rule

"Next five unused integers after the highest previously-used seed (12)." Two of them (13, 17) appear
in unrelated non-BindingSlots modules as internal RNG; the selection rule is scoped to BindingSlots
**model-training** seeds, for which 13–17 are all unused. Documented fully in `FRESH_SEED_PROOF.md`.

## 3. Harness reuse — no re-implementation

`run_confirmatory.py` calls the frozen `stabilize.run_arm` unchanged; the classifier imports the
frozen `classify_stage_b` per-seed rules. Only orchestration (seed list, provenance enrichment,
manifest) and the confirmatory verdict mapping are new. This guarantees the intervention and the
per-seed thresholds are byte-identical to the merged code.

## 4. torch build differs from the merged run — recorded, not blocking

The merged Stage B run used a different torch build; this environment has torch 2.2.2+cu121 (CPU,
fp32). The frozen protocol pins the optimizer/lr/betas/schedule, **not** the torch build, and the
confirmatory seeds are new — so exact reproduction of seeds 8–12 is neither required nor expected.
The delta is recorded in the manifest/environment fingerprint as a documented factor. It is **not**
treated as `CONFIRMATORY_ENVIRONMENT_MISMATCH` because the environment is fully capable of running
the frozen fp32 CPU code on the frozen seeds; a mismatch verdict is reserved for an environment that
cannot produce a valid comparison at all.

## 5. Compiler metadata

Per the task, any copied documentation referring to the merged compiler distribution uses
**distribution 0.2.0 / product 0.2.0 / workflow_ir.v1 digest semantic identity 0.1.0** — the merged
package state — and never describes the merged distribution as 0.1.0.

## 6. Verdict honesty

If compute prevents completing all 15 runs, the mechanical classifier emits
`CONFIRMATORY_RESOURCE_BLOCKED`. No numeric result is ever fabricated; the scientific verdict is
emitted only from real, completed, committed per-seed data.
