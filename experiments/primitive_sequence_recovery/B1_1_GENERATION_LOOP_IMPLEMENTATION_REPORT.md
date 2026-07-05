# B1.1 Generation Loop Implementation Report (code only; no generation)

## 1. Scope and non-claims

Implements the model-calling generation loop in `run_b1_1_generation.py`, preserving all freeze, approval,
leakage, and output safeguards. **Code implementation only.** No real generation, no model download, no
HuggingFace call, no LLM call, no judging, no scoring, no raw model outputs; no frozen artifact modified; the
final freeze manifest is not edited. Does **not** change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) or
unblock Track B (**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim.
**Structure, not validated meaning.**

## 2. What was implemented

- **`TransformersAdapter`** — real adapter reusing B1's committed pattern
  (`run_b1_generation.TransformersAdapter`): frozen model id + revision, `torch.float16`, `device_map=auto`,
  user-turn only (no system prompt), `apply_chat_template(return_dict=True)`, `set_seed` per row, frozen
  decode (temp 0.7 / top_p 0.95 / max_new_tokens 300). Imports torch/transformers **lazily in `__init__`**;
  instantiated **only inside the loop on a model-access host** — never reached in this environment.
- **`MockAdapter`** (`MOCK_ONLY`) — deterministic non-model placeholder for local CI of the loop mechanics.
  No model, no network; output is never B1.1 evidence.
- **`expand_generation_rows`** — the full frozen matrix (word × arm × task × model × seed = **4800 rows**).
  Prompts built **only** from the frozen generation config (`prompt_template` + `task_templates`); the arm
  conditioning comes from `builder.core(...)` over the frozen bridge pool. No post-hoc edits.
- **`run_generation_loop`** — verifies leakage over **every** prompt first (abort on any leak), then writes
  one JSONL row per generation, appended + flushed per row, with structured error rows on failure and a
  `--resume` that skips completed keys and never overwrites.
- **`main`** wiring — new `--mock-generation` mode; `--out` now required for execute/mock; the previous
  unconditional `REFUSED_HF_EGRESS` stub is replaced by the real loop **behind** the full gate stack, which
  still refuses in this environment.

## 3. Generation loop status

**Implemented and dry-checked via mock.** The real loop is code-complete and will run on a model-access
host; in this egress-denied environment it is **refused** before any model is contacted (no CUDA / HF
egress). The mock path proved the loop end-to-end (4800 rows, complete schema, 0 leakage, resume).

## 4. Adapter / source reused from B1

`TransformersAdapter` mirrors the committed **B1** runner `run_b1_generation.py` (chat wrapping, no system
prompt, `set_seed`, `apply_chat_template(return_dict=True)`, locked decode). Model ids/revisions/decode/seeds
come from the frozen B1.1 configs (which carry the B1 runtime lock values).

## 5. Frozen config loading result

Models, revisions, decode params, generation seeds, task templates, and the prompt template are loaded
**only** from the frozen configs (`b1_1_generation_config.json` via the verified manifest). Render-only
confirmed the arm construction and prompts build cleanly (200 cores, leak_total 0).

## 6. Manifest verification result

`run_b1_1_freeze_manifest_verifier.py b1_1_freeze_manifest.json` → **`MANIFEST_VERIFIED`**. The runner
re-verifies the manifest first (INVALID_POSTHOC abort on any bound-artifact mismatch); execute mode requires
the **FROZEN** manifest.

## 7. Render-only result

**`PASS_RENDER_ONLY`** (200 conditioning cores, leak_total 0, 0 empty arms). Render-only remains the
default-safe mode.

## 8. Refusal-path test results

- `--execute-generation` **without** `B1_1_GENERATION_APPROVED=YES` → **REFUSED**.
- `--execute-generation` **without** `--out` → **REFUSED**.
- `--execute-generation` with approval + `--out` → render/leak validated (leak_total 0), then **REFUSED** at
  the no-CUDA / egress gate — **no model contacted**.
- existing output **without** `--resume` → **REFUSED** (never overwrites).
- (mock) `--mock-generation` requires an `--out` whose filename contains `mock`.

## 9. Output JSONL schema summary

One line per generation, with: `run_id, manifest_sha256, manifest_path, freeze_commit, model_id,
model_revision, task_id, target_word, arm, prompt_id, prompt_text, conditioning_text, generation_text,
decoding{temperature,top_p,max_tokens}, seed, timestamp, status, error, key, mock, is_b1_1_evidence`.
Appended + flushed per row; structured `status:"error"` rows on failure (never silently skipped); `--resume`
skips completed keys.

## 10. Mock-generation added?

**Yes** — `--mock-generation`, clearly `MOCK_ONLY`: no model, no network; requires a `mock`-named `--out`;
every row stamped `mock=true`, `status=MOCK_ONLY`, `is_b1_1_evidence=false`; written to a scratchpad path,
**not committed**, and **never** acceptable as B1.1 evidence.

## 11–17. Confirmations

- **11. Real model called:** NO.
- **12. Generation executed:** NO.
- **13. Raw outputs created (in repo):** NO (mock output went to scratchpad only).
- **14. Judge/scoring run:** NO.
- **15. Frozen artifacts modified:** NO (manifest re-verified `MANIFEST_VERIFIED`; only the runner code +
  new report/dry-check files changed).
- **16. B1 verdict:** `RANDOM_OR_SCRAMBLED_MATCHES` (unchanged).
- **17. Track B:** `BLOCKED` (unchanged). Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) preserved; crux
  `R_deranged`; positive cap `LIMITED_GENERATION_UTILITY`; `FALLBACK_QUALIFIED` / embedding gate
  `BLOCKED_DEPENDENCY_UNAVAILABLE`.

## 18. Next recommended gate

**`B1_1_RUNPOD_GENERATION_OPERATOR_APPROVAL`** — operator sign-off to run the (now-implemented) loop on a
model-access host per `B1_1_RUNPOD_GENERATION_EXECUTION_PLAN.md`.

## Final status block

```
generation_loop:       IMPLEMENTED (real TransformersAdapter + MOCK_ONLY), dry-checked
real_model_called:     NO
generation_executed:   NO
raw_outputs_in_repo:   NO
judging/scoring:       NO
frozen_artifacts:      UNMODIFIED (MANIFEST_VERIFIED)
render_only:           PASS_RENDER_ONLY (leak_total 0)
refusal_paths:         ALL REFUSE (approval / --out / CUDA-egress / overwrite)
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
**Structure, not validated meaning.** Loop implemented; generation not executed, the B1 verdict stands, and
Track B remains BLOCKED.
