# DOCS_ONLY — TRACK B B0 CONDITIONING MATERIALIZATION PARITY LEAK PLAN — DRAFT ONLY — NOT MATERIALIZED — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only materialization/parity/leak plan. No commit of results, no code change, no model call, no LLM generation, no scoring, no result files, no hashes computed, no manifest population. **Plan only; nothing is materialized or frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: `c824a7a` · `16266b4` · `4c8122a` · `916e00a` · `bcb604e` · `fae078d` · `031f609` · `27bf8db` · `93ecb46` · `f8fe42e` (TBD plan) · `6fce2e9` (manifest template) · `7569210` (B1 request) · Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only materialization/parity/leak plan** — defines how conditioning text *would* be rendered; it renders nothing.
- **No model call · no LLM generation · no scoring · no result files.**
- **No hash computation · no manifest population · no B0 freeze · no B1 approval · no Track B unblock.**

## 2. Materialization goal

- Render **only the conditioning-slot text** for A/R/S/C/X/D (the middle of the wrapper), so length parity and a leak dry-check can run **before** freeze.
- Use **deterministic committed rules only** (the existing L1/L2 harness + arm generators).
- **No model outputs. No judging packets. No scores.**
- Purpose is strictly **parity/leak hygiene**, not evidence.

## 3. Inputs to materialize

- **20 primary natural key words** + **5 privative-stratum words** (`bcb604e` / eval list; G2P-confirmed `16266b4`).
- **A/R/S/C/X/D arm rules** from `916e00a`.
- **D-arm dictionary table** from `bcb604e`.
- **G2P path** verified by `16266b4` (true cmudict, hard-abort otherwise).
- **Default vowel mode = `field_only`.**
- **Proposed seeds** from the TBD plan (`f8fe42e`):
  - generation seeds `[1101, 2027]` — **not needed** for conditioning text (they govern model decoding, which is not run here);
  - R random-resonance seed scheme `"R:{key_word}"`;
  - S scramble seed `7731`.
- **Wrapper text** from the arm lock (used only to confirm the conditioning slot boundary; the wrapper itself is constant across arms and not part of parity comparison).

## 4. Outputs to materialize (intended table fields)

| Field | Meaning |
|---|---|
| `key_word` | eval word |
| `stratum` | `primary` or `privative` |
| `arm_code` | A / R / S / C / X / D |
| `conditioning_text` | the rendered slot text (no wrapper, no task, no model output) |
| `generator_source` | which committed rule produced it (e.g. `L2.synthesize`, `R:seed`, `S:7731`, `surface`, `neutral`, `D-table`) |
| `unresolved_terms_count` | count of `[unresolved]` markers (A/S) |
| `character_count` | primary parity metric |
| `word_count` | secondary parity metric |
| `token_count` | `NOT_AVAILABLE_PRE_MODEL_LOCK` until a tokenizer is locked |
| `leak_hits` | forbidden-phrase matches in conditioning text (§8) |
| `parity_status` | `PARITY_OK` / `PARITY_CONCERN` / `PARITY_FAIL` |
| `caveats` | e.g. `~approx` varṇa mapping, privative `EY`→`e` |

- This table is a **pre-freeze conditioning artifact, not a result file.**
- **No model output is included.**

## 5. Deterministic rendering rules

- **A:** `H.synthesize(H.profile(word, vowel_mode="field_only"))` → L2 process paraphrase.
- **R:** random resonance from bridge values via the fixed per-word seed `"R:{key_word}"`.
- **S:** scrambled resonance via fixed scramble seed `7731`.
- **C:** surface-only facts (onset ARPAbet / vowel-nucleus count / final ARPAbet / consonant-position count).
- **X:** the constant neutral line.
- **D:** dictionary-only sentence from the `bcb604e` table.
- **`[unresolved]` must be preserved** (A/S never fabricate an unmapped gloss).
- **No manual rewriting** — output is exactly what the committed rules emit.

## 6. Length-parity metric

- **Primary metric:** character count (until a model tokenizer is locked).
- **Secondary metric:** word count.
- **Token count** added later only if a tokenizer is available after runtime model lock.
- **Comparison:** each arm vs **A**, within each key word; then aggregate the **median by arm and by stratum**.

Thresholds:
- `PARITY_OK`: median arm length within **±25%** of A.
- `PARITY_CONCERN`: median arm length differs from A by **>25%**.
- `PARITY_FAIL`: arm is **clearly guessable** by length or formatting.

## 7. Parity action rule

If a parity concern/fail occurs **before freeze**:
- **revise formatting uniformly across all arms**, **or**
- **declare a confound before freeze.**

Hard constraints:
- **Do not weaken D semantically** (length-only adjustment).
- **Do not make R/S awkward.**
- **Do not tune A to win.**
- **No post-freeze parity fixes** (any post-freeze change ⇒ `INVALID_POSTHOC`).

## 8. Leak dry-check rule

Runs **only on conditioning text**, never on model outputs (there are none). Forbidden phrases (case-insensitive):
- `ontology` / ontological validation
- `Sanskrit proves` / Sanskrit privilege
- `semantic truth` / `validated meaning`
- `therefore means`
- `the word means` **when used as symbolic proof** (D's dictionary-sense usage is allowed)
- `varṇas prove` / `varnas prove`
- `phonemes encode true meaning`
- `Track B support` / `Track G rescue` / `rescue`
- any **arm label** visible to a judge
- any **conditioning-source label** visible to a judge

Rules:
- **Isolated conditioning leak** → flag and revise **before freeze**.
- **Systematic conditioning leak** → `LEAKAGE_FAIL_RISK`.
- **After freeze, a leak is not silently patched** (report it; a new B0 is required).

## 9. Non-evidence statement

- Materialized conditioning text is **not evidence**.
- The parity/leak check is **hygiene only**.
- **No conclusion about A's utility** is drawn.
- **No semantic validation.**
- **No Track B support.**

## 10. Implementation boundary

- **This document is a plan only.**
- **No code changes** unless separately approved.
- If a script is later created, it must be **deterministic, no-model**, and **separately reviewed**.
- **Any materialized artifact must be explicitly approved before creation.**
- **No output may be named as a result or score** (it is a conditioning artifact / parity-leak hygiene table).

## 11. Current status

- `CONDITIONING_MATERIALIZATION_PARITY_LEAK_PLAN_DRAFTED`
- `CONDITIONING_NOT_MATERIALIZED`
- `PARITY_NOT_MEASURED`
- `LEAK_DRY_CHECK_NOT_RUN`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 12. Recommendation

**`PERSIST_CONDITIONING_MATERIALIZATION_PARITY_LEAK_PLAN`** — with the explicit next action **`MATERIALIZE_CONDITIONING_NEXT`** (a deterministic, no-model render of the A/R/S/C/X/D conditioning slots for the 25 eval words, producing the §4 table for parity/leak hygiene — **separately approved before any file/script is created**).

Do **not** `COMPUTE_HASHES_NOW` (parity unmeasured, model lock unresolved), do **not** `FREEZE_B0_NOW`, and do **not** `REQUEST_B1_APPROVAL`. `FINALIZE_RUNTIME_FIELDS_NEXT` (model IDs/tokenizer/backend) remains the parallel runtime-gated track that this environment cannot complete. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label the frozen design is built to detect.

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
