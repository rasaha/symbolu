# DOCS_ONLY — TRACK B B0 MODEL DECODE SEED POLICY — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only policy draft. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed. **All model IDs/seeds are placeholders; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; G2P resolvability audit `16266b4` (`G2P_READY_FOR_FREEZE` on resolvability only); B0 freeze manifest template `6fce2e9`; B1 approval request `7569210`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only policy draft** — defines how model/decode/seed will be *locked* at a future freeze; it does not lock them.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no B0 freeze · no B1 approval · no Track B unblock.**
- Everything below is `DRAFT_NOT_FROZEN`; freeze discipline (`INVALID_POSTHOC`) applies only *after* a future signed freeze.

## 2. Model-selection principle

- **≥ 2 distinct model families** — a result on one family is not a conclusion; **no single-model conclusion allowed** (`NOT_ROBUST` kill otherwise).
- **Exact model IDs and revision hashes must be frozen later** (§4), recorded in the B0 manifest.
- **No model substitution after freeze.**
- **Unavailability rule:** if a locked model becomes unavailable after freeze, **B0 is voided and refrozen** with new hashes — **never silently replaced** (silent replacement ⇒ `INVALID_POSTHOC`).

## 3. Candidate model set (bounded, placeholders)

Final selection **not** claimed here; runtime availability confirmed at freeze.

| Slot | Role | ID + revision | Runtime (draft) |
|---|---|---|---|
| `MODEL_A_OPEN_WEIGHT` | open-weight instruct, family 1 | `<TBD_AT_FREEZE>` | `<GPU class / VRAM TBD>` |
| `MODEL_B_DISTINCT_FAMILY` | second open-weight **or** API/frontier instruct, **distinct family** | `<TBD_AT_FREEZE>` | `<GPU or API access TBD>` |
| `MODEL_C_OPTIONAL` | optional third model (only if budget/runtime allows) | `<TBD_AT_FREEZE>` | `<TBD>` |

- Families must be **distinct** (A and B not the same base lineage); C is additive robustness only.
- Hardware/runtime notes are **draft only**; no procurement or run implied.
- **No final model selection is asserted.**

## 4. Model-version lock rule (fields to be filled at freeze)

For each locked model:
```
model_lock:
  slot: <MODEL_A_OPEN_WEIGHT | MODEL_B_DISTINCT_FAMILY | MODEL_C_OPTIONAL>
  exact_id: <TBD_AT_FREEZE>
  provider_or_source: <TBD_AT_FREEZE>
  revision_hash_or_snapshot_or_api_version: <TBD_AT_FREEZE>
  tokenizer_version: <TBD_AT_FREEZE if available>
  inference_backend_and_version: <TBD_AT_FREEZE if relevant>
  date_locked: <TBD_AT_FREEZE>
  content_hash_in_b0_manifest: <computed later; PLACEHOLDER>
```
No field may remain `TBD` at freeze; any post-freeze edit ⇒ `INVALID_POSTHOC`.

## 5. Decode-parameter draft (`DRAFT_NOT_FROZEN`)

```
temperature:       0.7        # draft — confirm at freeze
top_p:             0.95       # draft
max_tokens:        300        # draft
frequency_penalty: 0          # if applicable
presence_penalty:  0          # if applicable
stop_sequences:    none       # unless frozen later
system_prompt:     none       # unless frozen later
identical_across_all_arms: true
arm_specific_decoding: forbidden
```
Same parameters for **every** arm on a given item. These values remain **draft until freeze**.

## 6. Seed policy draft (`DRAFT_NOT_FROZEN`)

```
seeds_per_item: 2            # minimum
exact_seed_list: <TBD_AT_FREEZE>
same_seed_list_across_all_arms_for_same_item: true
rerun_until_pass: forbidden
best_of_N: forbidden
failed_calls: logged (not replaced) unless the §7 infrastructure-failure rule applies
```
The seed list is **fixed and recorded at freeze**; identical seeds across arms isolate the conditioning slot as the only variable.

## 7. Infrastructure-failure rule

- **Allowable rerun:** only for a **documented API/network/runtime failure that occurs before any output is produced** (e.g., timeout, 5xx, OOM crash with no completion).
- **No rerun** for low-quality outputs. **No rerun** for unfavorable outputs.
- **Any post-output rerun attempt ⇒ `INVALID_POSTHOC`** (the run/request is void).
- **All failures logged** (timestamp, item, arm, model, seed, error) and reported; a rerun is permitted only under the documented pre-output-failure condition and is itself logged.

## 8. Output-count formula

```
N_outputs = N_words × N_tasks × N_arms × N_models × N_seeds
```
Current **draft** example (final counts frozen later):
- N_words = **20** primary (privative-stratum **5** words analyzed **separately**, not summed into the primary count)
- N_tasks = **6** (T1–T6)
- N_arms = **6** (A/R/S/C/X/D)
- N_models = **≥ 2**
- N_seeds = **≥ 2**

Draft primary estimate: `20 × 6 × 6 × 2 × 2 = 2,880` outputs (primary set, 2 models, 2 seeds). Privative stratum adds `5 × 6 × 6 × 2 × 2 = 1,440` outputs, **reported separately**. Totals are illustrative and **frozen later**.

## 9. Cost/runtime estimate placeholder

- **Rough placeholder only** — e.g., ~2,880 primary (+1,440 privative) generations × 2 models; wall-clock/cost depend on the (unlocked) models and backend. **No numeric budget asserted.**
- **No budget approval implied. No run authorized.**
- A **final cost/runtime estimate must be computed before B1 approval** (against the locked models).

## 10. Freeze requirements (all must be final before B0 freeze)

- [ ] Model IDs (exact) for all locked slots.
- [ ] Revision hashes / snapshot IDs / API versions.
- [ ] Tokenizer / inference-backend versions (where applicable).
- [ ] Decode params (temperature, top_p, max_tokens, penalties, stop, system prompt).
- [ ] Seed list (exact) + seeds-per-item.
- [ ] Infrastructure-failure rule acknowledged.
- [ ] Output-count estimate (final counts).
- [ ] **Model availability check** (each locked model reachable at freeze time).

Until every box is final and hashed into the B0 manifest, this policy stays `DRAFT_NOT_FROZEN`.

## 11. Current status

- `MODEL_DECODE_SEED_POLICY_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 12. Recommendation

**`PERSIST_MODEL_DECODE_SEED_POLICY_DRAFT`.**

This is the pre-freeze policy document only. Exact model IDs, revision hashes, seed list, and the final output-count/cost estimate are all `TBD_AT_FREEZE`, so **do not `FREEZE_B0_NOW`** (multiple §10 boxes remain open) and **do not `REQUEST_B1_APPROVAL`** (gated behind a completed, signed B0 freeze). `REVISE_MODEL_SET_BEFORE_FREEZE` is the fallback only if review rejects the candidate structure. Recommended path: persist this draft docs-only; locking model IDs/hashes, confirming decode/seeds, and computing the cost estimate + availability check remain a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label.

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
