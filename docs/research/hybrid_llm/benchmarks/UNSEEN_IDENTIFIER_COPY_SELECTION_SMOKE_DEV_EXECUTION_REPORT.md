# Unseen-identifier copy/selection — smoke + development execution report

**Scope of this report.** This records the **operator-directed execution of the AUTHORIZED phases only**
(smoke seed 9070; development seeds 9071–9073) of the frozen unseen-identifier copy/selection diagnostic,
under the phase-protocol control model. Reserved **final** seeds 90760–90764 were **never touched**;
`--phase final` was **not** run. No capability/empirical verdict is claimed. The three standing
invariants are preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

**Three dimensions are kept strictly separate (do not conflate):**
1. **Implementation validity** — already established (`PHASE_PROTOCOL_IMPLEMENTATION_CONFIRMED`); re-verified here only via fixture tests.
2. **Successful execution** — the frozen smoke/development runs completed deterministically. ✅
3. **Empirical capability evidence** — **NONE.** Development metrics are `DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE`; the development phase is **shortcut-blocked**; capability verdicts require prohibited final seeds. No capability claim is made or implied.

## Headline frozen verdicts (authorized phases only)
| Phase | Seeds | Frozen verdict (namespace) |
|---|---|---|
| Smoke | 9070 | **`SMOKE_INTEGRITY_PASS`** |
| Development | 9071, 9072, 9073 | **`DEVELOPMENT_SHORTCUT_BLOCKED`** |
| Final | 90760–90764 | **NOT RUN — PROHIBITED** (no capability verdict emitted) |

---

## 0. Authorization precondition (STEP 0) — verified from Git/GitHub

Execution was authorized only because **both** conditions held, verified independently (SHAs not trusted blindly):

- **(a) merged, reviewed smoke/development authorization present on default at HEAD.**
  - Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, tip independently confirmed = `b73a9f1e3cabe5f26bcc9a3a15f20d5519347baa`.
  - Audited implementation head `69f8b492405072d58adaf103094c189bb72938f5` confirmed **ancestor** of default (`git merge-base --is-ancestor` → true).
  - The three docs are present on default: `…_SMOKE_DEV_EXECUTION_AUTHORIZATION.md`, `…_SMOKE_DEV_EXECUTION_PLAN.md`, `…_SMOKE_DEV_EXECUTION_CHECKLIST.md`.
  - Landed via **PR #1378** (`state=closed, merged=true`, merged by `rasaha`; merge commit `b73a9f1e…`; head `a96c99cf…`), superseding the unmerged draft **PR #1373** (`state=open, draft=true, merged=false`) — both verified via the GitHub API.
  - Authorization text scopes to **smoke 9070 + development 9071–9073 ONLY**; **final 90760–90764 PROHIBITED**; `--phase final` **not authorized** (read directly from the merged doc).
- **(b) explicit operator direction** — the execution prompt is that direction.

→ `EXECUTION_NOT_AUTHORIZED` was **not** triggered; execution proceeded for smoke + development only.

---

## 1. Commit + environment

| Item | Value |
|---|---|
| Repo | `rasaha/symbolu` |
| Working branch | `claude/unseen-identifier-protocol-exec-bqrpoj` (from default tip) |
| Commit (HEAD == default tip) | `b73a9f1e3cabe5f26bcc9a3a15f20d5519347baa` |
| Working tree | clean |
| Python | 3.11.15 |
| PyTorch | 2.13.0+cu130 (**CPU execution; `cuda.is_available()=False`**) |
| NumPy | 2.4.6 |
| Platform | `Linux-6.18.5-fc-v18-x86_64-with-glibc2.39`, x86_64, 4 vCPU, 15 GiB RAM |
| Protocol docs used | `…_PROTOCOL_LOCK.md`, `…_PREREGISTRATION.md`, merged `…_SMOKE_DEV_EXECUTION_PLAN.md` / `…_AUTHORIZATION.md` / `…_CHECKLIST.md` |
| Model | `symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM` via `StructuredOutputModel`, reused by import from `experiments/single_hop_typed_vs_prose/` |
| Parameter count | **209,728** (verified == frozen) |
| Recipe source hashes (SHA-256, first 32) | `config.py 324be79d9cefaada9e09ddfae3b325aa` · `tokenizer.py 1849fd1f3d27e5d681d56e19ab099681` · `model.py 39a2a128824137924ef041fb3d1dc251` · `trainer.py ea0af36e4b3843296ee7d46b3f1228a3` — **all match protocol-lock Decision 6** |
| Seed allocation | smoke **9070**; development **9071, 9072, 9073**; fixture (validation only) **993000–993003** |
| Reserved-seed set (untouched) | final **90760, 90761, 90762, 90763, 90764** |
| Install note | `pip install pytest torch numpy` from the **default PyPI** index (CPU wheel); `download.pytorch.org` not used |

Environment note: pytorch/pytest/numpy were not preinstalled; installed from default PyPI. No GPU; run on CPU. Model is tiny; the frozen 2000-update matrix runs ~33–37 s per run on CPU.

---

## 2. Frozen research question (unchanged; not answered here)

> Can the exact frozen small-model recipe **copy and select previously unseen identifiers** from a
> bounded context when representation comparison, enterprise semantics, memory, evidence semantics,
> and multi-hop reasoning are removed?

The **authorized phases cannot answer this** — smoke and development are integrity/feasibility phases
and may not contribute to a scientific gate or capability verdict (protocol-lock Decision 10; plan
Decisions 5–6, 11). Answering it requires a separately-authorized **final** execution, which is
prohibited here.

## 3. Conditions + controls

- **One** frozen model recipe · **one** representation (protocol-lock Decision 2 — *no* prose-vs-JSON / typed-vs-prose arm by design) · one tokenizer · one optimizer · splits **C1–C8** · **no intervention arm**.
- **Cohorts:** `seen` (train-pool identifiers) and `unseen` (fully-disjoint final-pool identifiers). Training is on the **seen** cohort; evaluation on **both** cohorts (the seen-vs-unseen generalization axis, protocol-lock Decision 1 Axis B).
- **Controls (STEP 4):**
  - *known vs unseen identifiers* — seen vs unseen cohort (reported §5–6).
  - *no-binding / no-match* — split **C8** missing-key → abstention.
  - *positional shortcut baselines* — `first_target` / `middle_target` / `last_target`.
  - *lexical shortcut baselines* — `lexical_similarity` / `prefix_match` / `character_overlap`; split **C5** adds 1–2-char lexical decoys.
  - *frequency/memorization baselines* — `most_frequent_target` / `source_target_cooccurrence` / `seen_id_frequency`.
  - *leakage baselines* — `output_template_leakage` / `task_label_leakage`.
  - *chance / majority baseline* — chance computed mechanically = **1/3 = 0.3333** (3 candidates); `constant_abstention` is the C8 majority-class baseline.
  - *shuffled/broken bindings, typed-vs-prose, temporal-transfer, frozen ablations* — **N/A by frozen design** (single representation, no ablation arm, no temporal arm). No post-hoc controls were added.

## 4. Seed allocation (as consumed)

| Role | Seed(s) | Consumed? | Purpose |
|---|---|---|---|
| smoke | 9070 | yes — 1 official run + 1 no-write deterministic replay | integrity/feasibility only |
| development | 9071, 9072, 9073 | yes — 1 official run each (+1 no-write replay of 9071) | implementation validation, determinism, shortcut precheck, gate mechanics |
| fixture (validation) | 993000–993003 | yes — harness validation only (always-permitted namespace) | pre-flight; never scientific evidence |
| reserved final | 90760–90764 | **NO — never opened, generated, inspected, or consumed** | prohibited |

Run matrix executed = **4 training runs** (1 smoke + 3 development) × **2000 updates** = **8000 aggregate optimizer updates** — exactly the frozen matrix (plan Decision 2). No seed omitted; no failed run discarded.

## 5. Per-seed result table (DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE — descriptive, non-final)

Exact-sequence accuracy per split; per-seed then mean. **Seen** cohort = train-pool IDs; **unseen** = disjoint final-pool IDs.

**Seen cohort (train-pool identifiers):**
| Split | 9071 | 9072 | 9073 | mean | token-acc mean |
|---|---|---|---|---|---|
| C1 direct-copy | 0.933 | 0.783 | 0.667 | **0.794** | 0.906 |
| C2 relation-lookup | 0.517 | 0.433 | 0.450 | 0.467 | 0.706 |
| C3 evidence-lookup | 0.583 | 0.583 | 0.483 | 0.550 | 0.725 |
| C4 position-robust | 0.483 | 0.417 | 0.350 | 0.417 | 0.681 |
| C5 lexical-decoy | 0.633 | 0.550 | 0.317 | 0.500 | 0.761 |
| C6 seen-ID control | 0.450 | 0.450 | 0.300 | 0.400 | 0.694 |
| C7 (unseen-split, seen pool) | 0.483 | 0.533 | 0.350 | 0.456 | 0.707 |
| C8 abstention (exact) | 0.000 | 0.000 | 0.000 | 0.000 | — |

**Unseen cohort (disjoint final-pool identifiers):**
| Split | 9071 | 9072 | 9073 | mean | token-acc mean |
|---|---|---|---|---|---|
| C1 direct-copy | 0.000 | 0.017 | 0.000 | **0.006** | 0.381 |
| C2 relation-lookup | 0.000 | 0.000 | 0.000 | 0.000 | 0.125 |
| C3 evidence-lookup | 0.267 | 0.100 | 0.117 | 0.161 | 0.371 |
| C4 position-robust | 0.000 | 0.000 | 0.000 | 0.000 | 0.131 |
| C5 lexical-decoy | 0.000 | 0.000 | 0.000 | 0.000 | 0.324 |
| C6 seen-ID control | 0.000 | 0.000 | 0.000 | 0.000 | 0.126 |
| C7 unseen-ID cohort | 0.000 | 0.000 | 0.000 | 0.000 | 0.139 |
| C8 abstention (exact) | 0.000 | 0.000 | 0.000 | 0.000 | — |

**Abstention (C8):** correct-abstention rate = **1.000** (both cohorts, all seeds); false-answer rate = **0.000**; fabricated-ID rate = 0.000. (C8 exact-match is 0 by construction — the exact-match column excludes abstention-expected items; the abstention metric is the relevant one and it is perfect.)

**Smoke (9070), for integrity context only (NON-FINAL):** C1 seen 0.600 / unseen 0.000; C6 seen 0.300 / unseen 0.000; C7 seen 0.217 / unseen 0.000; first_loss 5.300 → final_loss 0.611.

## 6. Aggregate metrics with uncertainty (development, non-final)

Cohort-level seen−unseen exact-match gap (mean over 9071–9073):

| Split | seen mean | unseen mean | gap |
|---|---|---|---|
| C1 | 0.794 | 0.006 | 0.788 |
| C2 | 0.467 | 0.000 | 0.467 |
| C3 | 0.550 | 0.161 | 0.389 |
| C6 | 0.400 | 0.000 | 0.400 |
| C7 | 0.456 | 0.000 | 0.456 |

Per-seed spread is modest (e.g. C1-seen SD ≈ 0.109; C5-seen SD ≈ 0.130). These figures are **descriptive development evidence, explicitly non-final** and inadmissible as capability evidence; they are reported for gate-mechanics and feasibility only.

## 7. Primary-gate reconstruction (mechanical, from raw results)

**Important:** for the **authorized phases there is no primary *capability* gate to apply** — the
protocol-lock Decision 7 numeric gates and Decision 8 verdict engine are **final-phase** constructs
(they require "≥4/5 final seeds"). Smoke/development gates are integrity/feasibility gates
(plan Decisions 5–6). Reconstructed mechanically:

**Smoke gates (plan Decision 5 — integrity/feasibility; positive accuracy NOT required):**
| Gate | Result |
|---|---|
| command completed, no infrastructure failure | ✅ |
| all C1–C8 cohorts generated (both cohorts) | ✅ |
| checkpoint written + readable | ✅ |
| parser categories operational | ✅ (7-category classifier populated across 8 splits) |
| manifest complete with **actual** digests | ✅ (`build_run_manifest` enforces all 13 digest fields) |
| deterministic replay exact (scientific digests) | ✅ (§10) |
| no reserved-final artifact | ✅ |
| wall-clock ≤ frozen 24 h ceiling | ✅ (37.45 s) |
| shortcut machinery produces valid baselines + chance | ✅ (12 baselines/split; chance=0.3333) |
→ **`SMOKE_INTEGRITY_PASS`.**

**Development gates (plan Decision 6):**
| Gate | Result |
|---|---|
| all three seeds completed | ✅ |
| deterministic replay exact (scientific) | ✅ (§10) |
| manifest completeness | ✅ |
| **no shortcut baseline above frozen bound (pooled across 9071–9073)** | ❌ **FAIL** (see §9) |
| no seed collision | ✅ |
| resource within budget | ✅ (≈33 s/run) |
→ first failing frozen gate is the **shortcut precheck** → **`DEVELOPMENT_SHORTCUT_BLOCKED`.**

Per plan Decision 6, a shortcut anomaly **blocks further execution**, must be **diagnosed from
development evidence only**, and any corrective change **invalidates affected development evidence and
requires a corrective PR + fresh development authorization**. No such change was made here.

## 8. Diagnostics (Axis A / Axis B — descriptive, non-final; NOT a verdict)

Reported only to characterise the run; **no** capability verdict is emitted (final seeds prohibited; development is shortcut-blocked):
- **Axis A (copy vs selection):** on the seen cohort, C1 direct-copy (0.79) > C2 relation-lookup (0.47); on the unseen cohort C1 ≈ 0.006. Under the frozen **copy-masks-selection** rule, a below-gate C1 forbids reading C2 as a selection result — so **no selection diagnosis is admissible**, which is consistent with declining to emit any selection verdict.
- **Axis B (seen vs unseen):** large seen→unseen drop across every positive split (e.g. C1 0.79→0.006; C6 0.40→0.00; C7 0.46→0.00). Descriptively consistent with the preregistration's *floor-limited* hypothesis, **but** this is development (non-final) evidence and the phase is shortcut-blocked, so **it establishes nothing about capability** and must not be read as `GENERALIZATION_FAILED` or `COPY_CAPABILITY_NOT_FOUND` (those are final-phase verdicts).

## 9. Shortcut / leakage checks (the blocking gate)

Twelve structure-blind baselines, scored per split per seed, **pooled across development seeds
9071–9073** (frozen aggregation contract, plan Decision 7), threshold = **chance + 0.05 = 0.3833**.

| Cohort | pooled `all_pass` | max pooled baseline | over-bound (split · baseline · pooled score) |
|---|---|---|---|
| seen | **False** | 0.4056 | C2·lexical_similarity 0.3833; C2·character_overlap 0.3833; C5·first_target 0.3833; C5·output_template_leakage 0.3833; C5·task_label_leakage 0.3833; C6·source_target_cooccurrence 0.4056; C6·seen_id_frequency 0.4056; C7·last_target 0.4056 |
| unseen | **False** | 0.4056 | C7·last_target 0.4056 |

**Mechanical outcome:** the frozen gate (`aggregate_shortcuts`, `score <= chance+0.05`) returns
`all_pass=False` → **shortcut precheck FAILED** → `DEVELOPMENT_SHORTCUT_BLOCKED`. This is reported as
a failed gate; it is **not** relabeled as a pass.

**Diagnosis (development evidence only; no protocol change made).** The identifiers are provably
opaque and uniformly random (character-visible, collision-free, disjoint pools — all fixture-verified),
so every structure-blind baseline is at chance (1/3) in expectation. The exceedances are **marginal**:
the maximum pooled score is 0.4056 = 73/180 ≈ **+2.06 σ** above chance (pooled SD ≈ 0.035); several
"exceedances" are exact boundary ties at 0.3833 that fail only through floating-point representation.
Across **84 baseline×split comparisons per cohort**, ≈1.9 exceedances beyond 2 σ are **expected under
the null**. In other words, the block is driven by the fixed chance+0.05 margin being **tighter than
the pooled sampling error under multiple comparisons**, not by demonstrated lawful leakage — a
**gate-mechanics finding**, which is precisely what the development phase exists to surface
(plan Decision 6). Remediation (e.g. a sampling-aware margin, larger applicable-n, or multiple-comparison
control) is a **later, separately-authorized corrective PR** and is deliberately **not** performed here.

## 10. Determinism evidence

No-write re-runs compared against the official runs' digests:
- **Smoke 9070 replay:** byte-identical on **all** scientific digests — `dataset_seen`, `dataset_unseen`, `identifier_pool`, `initialization`, `batch_order`, **`checkpoint_parameter`**, `prediction_seen`, `prediction_unseen`; identical `first_loss`/`final_loss`. The only differing digest is the run manifest, which folds in the run-specific `wall_clock_s`/environment resource fields (not scientific content).
- **Development 9071 replay:** byte-identical on all eight scientific digests + losses.

→ Determinism is **exact** on all scientific content for both a smoke and a development seed. (Selected smoke digests: `checkpoint_parameter ab553248db3eca7c…`, `prediction_seen 2a917e983533f99a…`, `batch_order 7233785eb2328247…`.)

## 11. Final protocol verdict (authorized phases only)

- **Smoke (9070): `SMOKE_INTEGRITY_PASS`** — every frozen smoke integrity/feasibility gate passed; the machinery, determinism, checkpointing, parsing, manifesting, and shortcut computation all operate correctly. (Smoke does not require positive accuracy or a shortcut pass.)
- **Development (9071–9073): `DEVELOPMENT_SHORTCUT_BLOCKED`** — all runs completed deterministically, but the frozen pooled shortcut precheck did not clear `chance+0.05`; per Decisions 6/7/11 this blocks the development phase. Development metrics remain `DEVELOPMENT_ONLY_NOT_FINAL_EVIDENCE`.
- **No capability verdict** from the `UNSEEN_IDENTIFIER_*` namespace is emitted (final seeds prohibited; development shortcut-blocked). `SMOKE_INTEGRITY_PASS` did **not** clear development to proceed to final (it did not, and could not, per the frozen lifecycle).

## 12. Strictly bounded interpretation

This report supports **only**: *the frozen implementation runs the authorized smoke and development
phases to completion, deterministically, at 209,728 parameters on CPU, and the frozen pooled shortcut
gate blocked the development phase on marginal, noise-level baseline exceedances.* It does **not**
support — and explicitly does not claim — any of: base copy/selection capability, seen→unseen
generalization (or its failure) as a *verdict*, typed-structure superiority, enterprise/tenant
reasoning, evidence grounding, multi-hop, temporal reasoning, BindingSlots repair, KDA eligibility,
real-model transfer, capacity-scaling justification, production readiness, or any AGI / general-reasoning
/ broad-compositionality claim. The suggestive seen→unseen drop is **development-only, non-final, and
inside a shortcut-blocked phase** — it authorizes nothing.

## 13. Artifact / result-file paths

```
results/unseen_identifier_copy_selection/
  gate_reconstruction.json                      # mechanical smoke + development gate reconstruction
  run/summary_seed{9070,9071,9072,9073}.json    # per-run summary (digests, shortcut, per-split metrics)
  run/{9070,9071,9072,9073}/{seen,unseen}/
      manifest.json                             # canonical run manifest — actual digest values (13 fields)
      traces.json                               # per-example prediction traces (480 examples/cohort)
```
Raw checkpoints (`run/seed*_ckpt/checkpoint.pt`, 209,728-param state) are **deterministically
reproducible** from seed + the frozen recipe (verified §10) and their `checkpoint_parameter` digests
are recorded in each manifest; they are excluded from version control as reproducible binaries.
Driver + analysis scripts: `results/unseen_identifier_copy_selection/driver.py` and `analyze.py`
(orchestrate the frozen building blocks only — no protocol/implementation code was modified). Run from
the repo root with `PYTHONPATH=. python3 results/unseen_identifier_copy_selection/driver.py <phase> <seed> <out-dir>`.

## 14. Effect on standing invariants

**Unchanged and preserved** — this execution touched none of them:
- `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` — unaffected (no BindingSlots work performed).
- `E1_TEMPORAL_TRANSFER_PARTIAL` — unaffected (no temporal arm; N/A by frozen design).
- `KDA_VALIDATION_BLOCKED` — unaffected (no KDA work; explicitly out of scope).

The prior implementation verdict `PHASE_PROTOCOL_IMPLEMENTATION_CONFIRMED` for head `69f8b492…` stands;
this report adds **execution** evidence for the authorized phases, not implementation or capability
re-analysis.

---

### Separation of claims (restated)
- **Implementation validity:** confirmed previously; re-verified here only by fixture tests (136 passed) and static guards. Not re-audited.
- **Successful execution:** yes — smoke + development ran deterministically to completion within budget.
- **Empirical capability evidence:** **none.** No capability verdict; development is shortcut-blocked and non-final; final seeds remain prohibited. Implementation completion and successful execution are **not** empirical capability confirmation.
