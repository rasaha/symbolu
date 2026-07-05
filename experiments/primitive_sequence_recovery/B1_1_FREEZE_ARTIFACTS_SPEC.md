# B1.1 Freeze-Artifacts — SPECIFICATION (spec only, do not implement)

## 1. Scope and non-claims

**Spec only.** Defines the complete B1.1 freeze-artifact set required **before** any generation run.
**No freeze performed · no model / generation / scoring / judging.** Does **not** modify B1, change the
verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology validation, Sanskrit
privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Why this freeze spec exists

- The prereg (`9d474f2`) is **complete as a draft** but does **not yet bind run-time configuration**.
- B1.1 must **not** repeat the B1 **freeze-coverage gap**, where configs / seeds / judges / scorer settings
  (and the lexicon JSONs) sat **outside** the frozen artifact set.
- Freeze must **bind every artifact needed to reproduce generation, judging, and scoring** — so the run is
  reproducible and tamper-evident (`INVALID_POSTHOC` on any post-freeze edit, as in B0).

## 3. Freeze artifact set

### A. Lexicon artifact
- `b1_1_experimental_contrastive_lexicon_draft.json` · validator **18/18** · **sha256 required**.

### B. Bridge pool artifact
- `b1_1_bridge_pool_draft.json` · **68 phrases** · `PASS_BRIDGE_DRAFT` · status **FALLBACK_QUALIFIED** ·
  **sha256 required**.

### C. Arm construction config — *future file* `b1_1_arm_construction_config.json`
Must define: **A / D / S / R_same / R_deranged / R_domain / C / X** construction; exclusion rules; sampling
rules; **no-target-self rule** for R_same/R_deranged; style/length normalization; **deterministic seeds**.

### D. Generation config — *future file* `b1_1_generation_config.json`
Must define: generation **model ID(s)**; provider/runtime; **version/revision** where available;
temperature; top_p; max tokens; number of samples; prompt templates; task templates; decoding params;
retry policy; failure policy.

### E. Seeds config — *future file* `b1_1_seeds_config.json`
Must define: arm-construction seeds; task-order seeds; prompt-order seeds; generation seeds (where
supported); judge-packet shuffle seeds; scoring bootstrap seeds.

### F. Judge panel config — *future file* `b1_1_judge_panel_config.json`
Must define: judge **model IDs**; judge prompt; output schema; parser rules; QC rules; replacement policy;
exclusion policy; **no post-hoc judge selection**.

### G. Scorer config — *future file* `b1_1_scorer_config.json`
Must define: pairwise comparison plan; **primary** = A vs **R_deranged**, A vs **R_domain**, A vs
**R_same**; **secondary** = A vs D / S / C / X; confidence intervals; multiplicity correction; task-level
diagnostics; correctness tracking; verdict-label rules.

### H. Leak scan & packet persistence config — *future file* `b1_1_leak_and_packet_config.json`
Must define: leak checks; forbidden label leakage; **varṇa/Sanskrit leakage** checks; blinded packet format;
packet hashing; **packet persistence sample** (incl. R-beats-A); raw-output persistence; judge-output
persistence.

### I. Freeze manifest — *future file* `b1_1_freeze_manifest.json`
Must include: **sha256 of all freeze artifacts**; artifact paths; **generation authorization status**;
**fallback qualification status**; **embedding gate status**; **B1 verdict anchor**; **Track B blocked
anchor**; created_at timestamp; commit hash; explicit **"not ontology validation"** statement.

## 4. Required validators before freeze

- lexicon validator · bridge-pool validator · arm-config validator · generation-config validator ·
  seed-config validator · judge-config validator · scorer-config validator · leak/packet-config validator ·
  **freeze-manifest hash verifier** (re-hashes every bound artifact and fails on any mismatch).

All must pass before the freeze state may advance past `READY_FOR_FREEZE_REVIEW`.

## 5. Freeze decision states

- **`NOT_READY_FOR_FREEZE`** — required configs missing or failing validation.
- **`READY_FOR_FREEZE_REVIEW`** — all configs exist and validate; awaiting explicit freeze approval.
- **`FROZEN_NOT_AUTHORIZED_FOR_GENERATION`** — manifest signed; generation **not** yet authorized.
- **`FROZEN_AND_AUTHORIZED_FOR_GENERATION`** — separate authorization granted (see §6).
- **`BLOCKED`** — a hard blocker (e.g. dependency/egress) prevents progress.

**Default remains `NOT_READY_FOR_FREEZE`** until all required configs exist and validate. **Current state:
`NOT_READY_FOR_FREEZE`** (configs C–I do not yet exist).

## 6. Generation authorization rule

**Generation may NOT run merely because artifacts are frozen.** Generation requires a **separate explicit
authorization gate: `B1_1_GENERATION_AUTHORIZATION`.** Even `FROZEN_NOT_AUTHORIZED_FOR_GENERATION` does not
permit a model call.

## 7. Embedding-gate relationship

- The embedding gate remains **`BLOCKED_DEPENDENCY_UNAVAILABLE`** and **owed**.
- If still unavailable at freeze, the **manifest must mark `FALLBACK_QUALIFIED`** and the prereg's elevated
  R-risk caveat must be preserved.
- If **embedding access returns before freeze**, re-run the real embedding gate and **update status before
  freezing** (path A supersedes path B).

## 8. Required no-rescue anchors (must appear in the manifest)

- B1 verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`**.
- Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, A_vs_R −0.1917, A_vs_X −0.075).
- Track B remains **BLOCKED**.
- A **failure cannot be reinterpreted** as ontology signal.
- A **positive can only be `LIMITED_GENERATION_UTILITY`** (in-architecture, this frozen design).

## 9. Next gate after this spec

**`B1_1_FREEZE_ARTIFACTS_IMPLEMENTATION_PLAN`** — create concrete **config templates and validators**
(files C–I + their validators), **not** run generation. Each config authored + validated, shown, and
committed under gate discipline before the freeze manifest is built.

## 10. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Prereg:                COMMITTED DRAFT (9d474f2)
Freeze status:         NOT_READY_FOR_FREEZE
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (still owed)
Generation/scoring/judging: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. Contrastivity / non-synonymy repair remains **necessary but not sufficient**;
**`R_deranged` remains the crux**.

**Structure, not validated meaning.** Spec only; the B1 verdict stands and Track B remains BLOCKED.
