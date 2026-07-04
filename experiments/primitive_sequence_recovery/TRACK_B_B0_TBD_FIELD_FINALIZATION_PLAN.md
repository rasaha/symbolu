# DOCS_ONLY — TRACK B B0 TBD-FIELD FINALIZATION PLAN — NOT HASHED — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only finalization plan. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed, no manifest population. **Proposes/decides pre-freeze values; nothing is hashed or frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: `c824a7a` · `16266b4` · `4c8122a` · `916e00a` · `bcb604e` · `fae078d` · `031f609` · `27bf8db` · `93ecb46` (rollup) · `6fce2e9` (manifest template) · `7569210` (B1 request) · Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only finalization plan** — converts open `TBD_AT_FREEZE` choices into proposed final values, and flags what still needs runtime/provider confirmation.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no manifest population · no B0 freeze · no B1 approval · no Track B unblock.**

## 2. Finalization goal

- Convert open `TBD_AT_FREEZE` choices into **final pre-freeze values** where they can be decided from documents alone.
- Identify fields that **still require provider/runtime verification** (and must not be guessed).
- Prepare the package for a **later, separately-approved hash/freeze step**.
- **This plan itself does not freeze anything.**

## 3. Model lock finalization plan

**Constraint:** this environment cannot reach model providers (firewalled; PyPI only). Therefore **no model ID is decided here** — model slots are marked `REQUIRES_RUNTIME_CONFIRMATION`, not silently chosen.

| Slot | Candidate family (illustrative, not locked) | Provider/source | Exact ID | Revision/snapshot/API ver | Tokenizer ver | Backend/ver | Availability check | Final status |
|---|---|---|---|---|---|---|---|---|
| `MODEL_A_OPEN_WEIGHT` | an open-weight instruct model (family 1) | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | required | `REQUIRES_RUNTIME_CONFIRMATION` |
| `MODEL_B_DISTINCT_FAMILY` | open-weight **or** API/frontier instruct, **distinct family** | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | required | `REQUIRES_RUNTIME_CONFIRMATION` |
| `MODEL_C_OPTIONAL` | optional third model | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | required | `REQUIRES_RUNTIME_CONFIRMATION` |

**Rule:** do not lock any model until (a) its exact ID + revision/API version is confirmed and (b) an availability check succeeds at the operator's runtime. A/B **must be distinct families**. If a candidate is unavailable at lock time → `REPLACE_BEFORE_FREEZE` (never silently substitute).

## 4. Decode-parameter finalization

Proposed final values (decidable from documents; no runtime dependency):

```
temperature:       0.7
top_p:             0.95
max_tokens:        300
frequency_penalty: 0
presence_penalty:  0
stop_sequences:    none
system_prompt:     none
identical_across_all_arms: true
arm_specific_decoding: forbidden
```

Status: **`FINAL_READY_FOR_HASH`** (subject only to final review; some providers may not expose `frequency_penalty`/`presence_penalty` — if absent for a locked model, record "not-applicable" at lock, not a value change).

## 5. Seed and randomization finalization

Proposed **fixed, non-optimized** integer seeds (arbitrary constants, not tuned):

```
generation_seeds:            [1101, 2027]      # two fixed ints; SAME list across all arms
R_random_resonance_seed:     "R:{key_word}"    # existing per-word deterministic scheme (fae078d/916e00a)
S_scramble_seed:             7731              # fixed int
output_order_randomization_seed:   40411       # fixed int
judge_packet_randomization_seed:   50513       # fixed int
```

Rules: same generation-seed list across all arms; **no rerun-until-pass**; **no seed edits after freeze**; **seeds are not optimized** (chosen blind, never selected to help A).

Status: **`SEEDS_READY_FOR_HASH`** (values decidable now; the R/S schemes already exist in committed code — pinned by the arm-construction commit at freeze).

## 6. Judging-rule finalization

Proposed finals:

```
n_judges:            3 minimum, 5 preferred
eligibility:         fluent English readers; NO prior exposure to H2 materials
attention_checks:    included; a judge failing the predeclared threshold is EXCLUDED (only by that rule)
judge_exclusion:     ONLY via the attention-check rule; no discretionary removal
tie_no_preference:   0.5
both_bad:            0.5 AND separately flagged
low_agreement:       report; apply caution / possible NOT_ROBUST below a predeclared agreement threshold
```

Status: **`JUDGING_RULES_READY_FOR_HASH`** (values decidable now; final `n_judges` within the 3–5 range and the exact agreement threshold to be fixed at lock — both document-decidable, no runtime dependency).

## 7. Statistical-method finalization

Proposed finals:

```
primary_outcome:      pairwise A win-rate (blinded forced choice)
CI_method:            paired bootstrap over item-level clustered units
correction:           Holm-Bonferroni across the five co-primaries
success_threshold:    corrected CI lower bound > 0.5 for EACH co-primary (A_vs_D/R/S/X/C)
robustness:           positive effect must appear across >= 2 model families AND > 1 task type (and >= 2 seeds)
missing_data:         reported; NO discretionary imputation unless predeclared
```

Status: **`STATISTICAL_METHODS_READY_FOR_HASH`** (fully document-decidable; bootstrap iteration count + RNG seed for the bootstrap to be fixed at lock).

## 8. Length-parity and leak-check finalization

```
prerequisite:        conditioning artifacts for A/R/S/C/X/D must be MATERIALIZED (rendered to text) before a parity check
length_metric:       token count (if a locked tokenizer is available) ELSE character count; word count as fallback
imbalance_threshold: any arm whose median conditioning length differs from A by > 25% = PARITY_CONCERN
action_if_exceeded:  revise formatting UNIFORMLY across all arms, OR declare a confound before freeze — NEVER weaken D/R/S/C to help A
leak_check:          criteria inherited from fae078d §8; applied to conditioning text pre-freeze IF materialized
```

Status: **`PARITY_LEAK_RULES_REQUIRE_REVISION`** — the *rules* are decidable, but the *measurement* cannot run until the conditioning artifacts are materialized (which itself is a separate, deterministic, no-model step). So parity is **pending materialization**, not yet measured.

## 9. Artifact finalization checklist (standalone files needed before hashing)

- [ ] prompt set / task templates (T1–T6)
- [ ] key-word list (20 primary + 5 privative)
- [ ] held-out/dev split
- [ ] model/decode/seed policy (final, with locked IDs)
- [ ] arm-construction final (wrapper + generators pinned)
- [ ] D-arm dictionary table (final)
- [ ] judge/randomization/leak (final)
- [ ] analysis plan (final)
- [ ] failure-mode premortem
- [ ] approval-record template
- [ ] manifest-transition checklist
- [ ] freeze manifest

(Currently these exist as **drafts within docs**, not as finalized standalone frozen files.)

## 10. Hashing-readiness status (no hashes computed)

| Artifact/field group | Readiness |
|---|---|
| Decode params | `READY_FOR_HASH_AFTER_FINAL_REVIEW` |
| Seeds (gen/R/S/output/judge) | `READY_FOR_HASH_AFTER_FINAL_REVIEW` |
| Judging rules | `READY_FOR_HASH_AFTER_FINAL_REVIEW` |
| Statistical methods | `READY_FOR_HASH_AFTER_FINAL_REVIEW` |
| Prompt set / key-words / split | `READY_FOR_HASH_AFTER_FINAL_REVIEW` (structural; G2P confirmed `16266b4`) |
| D-arm table | `READY_FOR_HASH_AFTER_FINAL_REVIEW` (pending parity) |
| Model lock (A/B/C) | `REQUIRES_RUNTIME_CONFIRMATION` |
| Tokenizer/backend versions | `REQUIRES_RUNTIME_CONFIRMATION` |
| Length parity / leak dry-check | `REQUIRES_CONTENT_REVISION` (materialize conditioning first) |
| Standalone artifact files + freeze manifest | `NOT_READY` (not yet materialized/populated) |

**No hashes are computed.**

## 11. Remaining blockers

- Exact model IDs / revision / API versions (runtime).
- Model availability check (runtime).
- Tokenizer / backend versions (runtime).
- Length parity not yet measured (needs materialized conditioning).
- Conditioning artifacts not yet materialized (deterministic no-model render, separate step).
- Randomization config not yet materialized.
- Final standalone artifact files not yet created.
- Freeze manifest not populated; signed freeze record not created.

## 12. Current status

- `TBD_FIELD_FINALIZATION_PLAN_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 13. Recommendation

**`PERSIST_TBD_FIELD_FINALIZATION_PLAN`** — with the explicit next action **`MATERIALIZE_CONDITIONING_FOR_PARITY_CHECK`** (the largest document-decidable gap: rendering A/R/S/C/X/D conditioning text deterministically, no model, so length parity and a leak dry-check can run), **followed by** `FINALIZE_RUNTIME_FIELDS_NEXT` (model IDs/revisions/tokenizer/backend + availability — which require the operator's runtime and cannot be decided here).

Do **not** `COMPUTE_HASHES_NOW` (model lock + parity are unresolved), do **not** `FREEZE_B0_NOW`, and do **not** `REQUEST_B1_APPROVAL`. Rationale: decode/seed/judging/statistical fields are document-decidable and marked ready-for-review, but model lock is `REQUIRES_RUNTIME_CONFIRMATION` and parity is `REQUIRES_CONTENT_REVISION` — both hard prerequisites to hashing. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label the frozen design is built to detect.

## Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.
- Approval status remains `NOT_APPROVED`.

---

**Structure, not validated meaning.**
