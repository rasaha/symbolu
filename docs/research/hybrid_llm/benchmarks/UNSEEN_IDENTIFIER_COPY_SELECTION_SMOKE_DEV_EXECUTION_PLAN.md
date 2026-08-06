# Unseen-identifier copy/selection — smoke/development execution plan (docs-only)

**Documentation-only. No execution, generation, training, or seed consumption in this session.**
This plan makes a *future* smoke/development run precise and bounded. It authorizes nothing beyond
the companion `…_SMOKE_DEV_EXECUTION_AUTHORIZATION.md`. Reserved final seeds 90760–90764 remain
forbidden throughout.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Reconciliation note (rebased onto the phase-protocol control model)
This plan was first drafted against an earlier default (`773a7c93…`) that carried a caller-supplied
**cryptographic** authorization layer (signed authorization records/artifacts, `AuthorizationContext`,
`authorize()`, a capability registry / `active_authorization` / mint keys, recognized authorization
states such as `SMOKE_EXECUTION_AUTHORIZED`, and `--authorization-record` / `--authorization-artifact`
CLI inputs). PR #1377 **removed all of that** as disproportionate for an internal research experiment
and replaced it with lightweight **experimental-protocol control**. The plan below has been rebased
onto that current model; no removed crypto machinery is referenced as a control. The frozen scientific
values (run matrix, gates, shortcut-aggregation contract, evidence/fingerprint contract) are unchanged.

**Current control model (the only control that exists on default `6c8fb71…`):**
* every invocation names an explicit **`--phase`** — `fixture` / `smoke` / `development` / `final`;
* the seed must belong to that phase's **exact** role (every cross-role pairing is refused);
* **exactly one** integer `--seed` per invocation (no wildcard / range / comma-list / glob / alias /
  implicit iteration over reserved seeds);
* the **primitive-level fail-closed guard** `require_execution_authorization(seed, phase)` gates the
  three data-generation primitives — a reserved seed is refused unless its exact phase is declared;
* CI and the tests exercise **only** the fixture phase (`993000–993004`).

The real authorization for a reserved run is the **reviewed, independently-audited, merged
authorization plus the operator's explicit phase-named invocation** — there is no crypto gate, secret,
token, or runtime self-verification.

## Decision 1 — Frozen execution commands (future; fail-closed; unexecuted here)
The merged package already exposes a real, phase-scoped executable interface (verified present and
importable, **not run**):
`python -m experiments.unseen_identifier_copy_selection <subcommand> --phase <phase> --seed <one int>
--cohort <seen|unseen> --output-dir <dir>` over the building blocks `runner.build_cohort(seed, cohort,
phase)`, `runner.serialize_cohort(...)`, `shortcuts.shortcut_precheck(...)`, `manifest.*` digest
utilities, `training.train_cohort(...)` (reusing the frozen `train_in_memory` recipe), and
`runner.enter_final_phase(...)` (final phase — **not used** for smoke/dev). Every subcommand requires
an explicit `--phase`, exactly one integer `--seed` belonging to that phase's role, an explicit
`--cohort`, and an explicit `--output-dir`; `--help` imports no model, generates no data, and writes
nothing. Every command is fail-closed: a reserved seed raises `ExecutionNotAuthorized` at the
data-generation primitive **and** at the CLI/runner unless its exact phase is explicitly declared (the
declared phase is threaded as the primitive guard's `phase` argument; the guard covering the three
primitives was consolidated in PR #1372). **No command names a final seed or `--phase final`.**

| Future command (illustrative) | Building block | Guard |
|---|---|---|
| smoke identifier pools / dataset | `build_cohort(9070, cohort, "smoke")` | fail-closed unless `--phase smoke` is declared |
| smoke shortcut baselines | `shortcut_precheck(<smoke cohort>)` | fixture-safe; no reserved final |
| smoke training | `train_cohort(model, encoded, seed=9070, phase="smoke")` (frozen `train_in_memory`, `seed=sub_seed(9070,'batch')`) | requires `--phase smoke` |
| smoke evaluation / replay | greedy decode + `parse` + `metrics` | deterministic |
| smoke manifest | `manifest.*` actual digests | required-value fingerprints |
| development pools/dataset/precheck/train/eval/replay | same with seeds 9071–9073 | requires `--phase development` |

The plan verifies the commands are **syntactically supported by the merged package** (the functions
and the CLI subcommands exist and import cleanly); it does **not** run them.

## Decision 2 — Frozen run matrix
- **smoke:** seed **9070**; **development:** seeds **9071, 9072, 9073**; **final:** none.
- one model recipe · one representation · one tokenizer · one optimizer · one task configuration ·
  splits **C1–C8** · **no intervention arm**.
- Derived (fixed here, from the frozen recipe and split counts):
  - training runs = **1 (smoke) + 3 (development) = 4**;
  - updates per run = **2000** (frozen);
  - aggregate optimizer updates = **4 × 2000 = 8000**;
  - expected checkpoints = **4** (one final checkpoint per run);
  - expected manifests = **4** (one per run) + 1 environment manifest per phase;
  - expected prediction-trace sets = **4** (per-example, all splits/cohorts per run);
  - maximum wall-clock = **24 h** (frozen ceiling; realistic projection ≪ that — the frozen
    recipe trains ~1–2 min/run on CPU);
  - storage budget = small (few MB of JSON traces/manifests per run; no large checkpoints beyond
    the 209,728-parameter model state).
- No value is inferred during a future run; all are fixed here.

## Decision 3 — Frozen scientific-cohort generation order (future)
Permitted order (each step gated; development requires a recorded smoke-integrity pass):
1. environment manifest → 2. source/config/tokenizer hash verification → 3. phase/seed-role
verification → 4. smoke identifier pools → 5. smoke dataset → 6. smoke shortcut baselines →
7. smoke training → 8. smoke evaluation → 9. smoke deterministic replay → 10. smoke integrity report
→ 11. smoke audit → **12. only if smoke passes:** development identifier pools → 13. development
datasets → 14. development shortcut precheck → 15. development training → 16. development evaluation
→ 17. development replay → 18. development evidence report → 19. independent development-evidence
audit. **Development must not begin automatically because smoke code exits 0** — it requires an
explicit recorded `SMOKE_INTEGRITY_PASS` and a separate operator `--phase development` invocation
(there is no automatic smoke→development transition).

## Decision 4 — Frozen pre-execution checks (all required before smoke)
Authoritative default clean · correct merge ancestry · protocol-lock digest matches ·
implementation-authorization digest matches · **implementation audit verdict = confirmed** · model
source hashes match · **parameter count = 209,728** · scientific seeds still unused · fixture outputs
removed or isolated · environment recorded · disk/memory budget sufficient · no training process
running · no stale checkpoint · no stale run directory · **this merged smoke/development authorization
is in place and the operator explicitly declares `--phase smoke`** (the merged authorization + the
explicit phase-named invocation is the control; there is no token or record to check). **Any failure
blocks smoke.**

## Decision 5 — Frozen smoke gates (integrity/feasibility, NOT scientific)
Smoke requires: command completes without infrastructure failure · all C1–C8 cohorts generated ·
no pool collisions · no train/dev/final contamination · serializer byte stability · manifest
complete · all required digests present · parser categories operational · checkpoint readable ·
deterministic replay exact · no reserved-final artifact · no protocol deviation · wall-clock
projection ≤ frozen budget · shortcut machinery produces valid baselines and chance values.
**Smoke does NOT require positive model accuracy.**

Smoke outcomes (exactly one): `SMOKE_INTEGRITY_PASS` · `SMOKE_IMPLEMENTATION_DEFECT` ·
`SMOKE_PROTOCOL_DEVIATION` · `SMOKE_RESOURCE_BLOCKED` · `SMOKE_NONDETERMINISTIC` ·
`SMOKE_AUTHORIZATION_VIOLATION`. **Only `SMOKE_INTEGRITY_PASS`** may permit a later
development-execution continuation, per the frozen lifecycle.

## Decision 6 — Frozen development gates
Development must verify: all three seeds complete · deterministic replay · manifest completeness ·
**no shortcut baseline above its frozen bound** · no task-construction imbalance · no identifier
leakage · no position leakage · no output-template leakage · no seed collision · no protocol
deviation · resource use within budget. Development results are labeled
**`DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE`**; **no final capability verdict may be emitted.**

If a shortcut anomaly occurs: block further execution · do **not** inspect final seeds · diagnose
using development evidence only · any protocol/implementation change invalidates affected
development evidence and requires a corrective PR + fresh development authorization.

## Decision 7 — Frozen shortcut precheck (aggregation contract explicit)
Future shortcut artifacts: per-task chance · per-split heuristic score · per-seed heuristic score ·
aggregate heuristic score · threshold (**chance + 0.05**) · competence-floor comparison · blocking
status. **Aggregation contract (explicit, so execution code never infers it):**
- chance is computed **mechanically per split** (1 / candidate-count for selection splits);
- each heuristic is scored **per split, per seed**;
- the gate is evaluated on the **per-split score pooled across the development seeds** (9071–9073)
  to reduce single-cohort sampling noise, and additionally reported per seed;
- a split fails if its pooled score exceeds chance + 0.05 **or** falls at/above the learned
  competence floor.
This matches the merged implementation (`shortcuts.shortcut_scores` computes per-split baselines).
A shortcut precheck must occur **before** development results can be accepted and **before** any
future final authorization can be drafted.

## Decision 8 — Frozen evidence artifacts (actual digest values, not booleans)
Every future smoke/development run must produce: source digest · config digest · tokenizer digest ·
identifier-pool digest · dataset digest · serializer digest · initialization digest · batch-order
digest · checkpoint/parameter digest · prediction digest · evaluator digest · environment digest ·
**per-example traces** · per-task metrics · per-seed metrics · parser-category counts · shortcut
results · resource measurements · protocol-compliance report. **No aggregate-only result package**
(this closes the typed-vs-prose aggregate-only gap). Every artifact must identify: **seed · cohort ·
source commit · authorization commit · protocol-lock commit · implementation commit · environment.**
The merged `manifest` module already emits actual digest values; the run must record them (not a
`determinism_ok: true` boolean).

## Decision 9 — Frozen failure handling
**No selective restart.** Rerun is allowed **only** for documented infrastructure failure (host
termination · disk failure · scheduler interruption · unrecoverable dependency outage). **Model
underperformance is not infrastructure failure.** Implementation defects require: stop · corrective
PR · independent audit · invalidation of affected evidence · fresh execution authorization. No
failed seed may be silently replaced. **No budget extension after observing results.**

## Decision 10 — Frozen stopping rules
Stop immediately if: any reserved final seed is touched · source hash differs · parameter count
differs · protocol digest differs · a shortcut anomaly exceeds its bound · identifier pools overlap ·
the serializer changes · deterministic replay fails · a manifest is incomplete · an artifact path is
contaminated · an unauthorized process starts · the wall-clock budget cannot be met · implementation
code changes during execution. **Do not proceed from smoke to development without
`SMOKE_INTEGRITY_PASS`. Do not proceed from development to final authorization within this session.**

## Decision 11 — Frozen development-report vocabulary
Allowed development-status outputs: `DEVELOPMENT_INTEGRITY_PASS` · `DEVELOPMENT_SHORTCUT_BLOCKED` ·
`DEVELOPMENT_IMPLEMENTATION_DEFECT` · `DEVELOPMENT_PROTOCOL_DEVIATION` ·
`DEVELOPMENT_RESOURCE_BLOCKED` · `DEVELOPMENT_NONDETERMINISTIC` ·
`DEVELOPMENT_AUTHORIZATION_VIOLATION`. **Do not emit** `UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED`,
`UNSEEN_IDENTIFIER_SELECTION_FAILED`, `UNSEEN_IDENTIFIER_GENERALIZATION_FAILED`,
`UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND`, or any final scientific verdict. Development metrics
may be reported descriptively but remain **non-final**.

## Decision 12 — Frozen next lifecycle (this session authorizes none of it)
After a future smoke/development run: 1. stop all compute → 2. commit raw evidence and manifests →
3. open a development-evidence PR → 4. independently reconstruct every result → 5. audit shortcuts
and determinism → 6. merge only if evidence is complete → 7. separately draft reserved-final
execution authorization → 8. independently audit that authorization → 9. **only then** permit final
seeds 90760–90764. **This session performs and authorizes none of steps 1–9.**

## Claim boundary
No smoke/development outcome supports typed structure over prose · enterprise reasoning · tenant
competence · evidence grounding generally · multi-hop · temporal · BindingSlots · KDA · production
readiness. Development metrics are non-final. Preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Status
This package's authorization readiness marker remains **`SMOKE_DEV_EXECUTION_AUTHORIZATION_DRAFT_READY`**
— the smoke/development scope and controls are fully specified for independent review. Under the
phase-protocol model there is **no** runtime "execution-authorized" state or capability verdict to
emit: the removed recognized states (`SMOKE_EXECUTION_AUTHORIZED`, `DEVELOPMENT_EXECUTION_AUTHORIZED`,
`FINAL_EXECUTION_AUTHORIZED`, `EXECUTION_AUTHORIZED`) no longer exist. Authorization is effected by
merging this reviewed, independently-audited authorization plus the operator's explicit `--phase`
invocation. Merged with operator authorization, this package makes **smoke (seed 9070) and development
(seeds 9071–9073) execution AUTHORIZED** under the frozen implementation; **final seeds 90760–90764
and `--phase final` remain PROHIBITED**, and no capability or empirical-result claim is made here.
