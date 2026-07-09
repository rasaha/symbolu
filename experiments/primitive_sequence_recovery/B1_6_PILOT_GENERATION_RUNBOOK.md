# B1.6 — Pilot Generation Runbook (Gated; Mock-Tested)

**Status:** Operator runbook + gated driver (mock-tested). **No real generation run. No external LLM API call.
No judging. No evidence freeze created by the assistant.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

**Readiness label: `B1_6_PILOT_GENERATION_DRIVER_READY_MOCK_TESTED`.**

Driver: `run_b1_6_pilot_generation.py`. Tests: `test_run_b1_6_pilot_generation.py` (22/22).
Schema: `frozen/b1_6_pilot_generation_schema.json`.

---

## 1. Purpose

Provide a **gated** driver that renders the B1.6 generation prompts for the five active arms over the 24 frozen
pilot targets, writes **blinded** output packages + a **hidden** arm-metadata file, and **never judges** — and
that **refuses to run** unless an operator has created an evidence-freeze declaration whose hashes match the
frozen inputs. The assistant does **not** create that declaration and does **not** run real generation.

## 2. Preflight

- Confirm the frozen inputs exist and are unchanged (the driver re-hashes them against the declaration):
  `frozen/b1_6_pilot_targets_scaffolds.json`, `frozen/b1_6_pilot_scaffold_manifest.json`,
  `frozen/b1_6_pilot_randomized_control_manifest.json`, `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md`.
- Run the tests (§ Validation).

## 3. Required frozen inputs

| Input | File |
|---|---|
| Targets + scaffolds | `frozen/b1_6_pilot_targets_scaffolds.json` |
| Scaffold manifest | `frozen/b1_6_pilot_scaffold_manifest.json` |
| Randomized control | `frozen/b1_6_pilot_randomized_control_manifest.json` |
| Prompt/rubric spec | `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` |

## 4. Evidence-freeze declaration schema

Operator creates `frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json` (**gitignored; never committed**):

```json
{
  "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": true,
  "mode": "pilot_generation",
  "scaffold_manifest_sha256": "<sha256 of frozen/b1_6_pilot_scaffold_manifest.json>",
  "target_scaffold_sha256": "<sha256 of frozen/b1_6_pilot_targets_scaffolds.json>",
  "randomized_control_manifest_sha256": "<sha256 of frozen/b1_6_pilot_randomized_control_manifest.json>",
  "prompt_rubric_sha256": "<sha256 of B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md>",
  "declared_by": "<operator id>",
  "declared_at_utc": "<ISO-8601>",
  "attestation": "B1.6 pilot generation only; no judging; no semantic truth claim; Symbol-U utility test only; B1.4b′ remains NULL_RETURN_BOTTOM."
}
```

The driver **refuses** on: missing declaration, `mode != pilot_generation`, any missing field, or any of the
four hash mismatches, or a wrong attestation string.

Compute the hashes:

```bash
cd experiments/primitive_sequence_recovery
sha256sum frozen/b1_6_pilot_scaffold_manifest.json \
          frozen/b1_6_pilot_targets_scaffolds.json \
          frozen/b1_6_pilot_randomized_control_manifest.json \
          B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md
```

## 5. Operator command sequence

```bash
cd experiments/primitive_sequence_recovery

# 1) validate plumbing (mock; uses a TEMP declaration inside the tests)
python3 -m pytest test_run_b1_6_pilot_generation.py -q

# 2) operator creates the evidence-freeze declaration (NOT the assistant)
#    write frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json per §4 (gitignored)

# 3a) MOCK run (deterministic placeholder text; plumbing only; still gated)
python3 run_b1_6_pilot_generation.py --mock

# 3b) REAL run — now supported via the local LLM adapter (b1_6_llm_adapter.py), on a
#     MODEL-ACCESS HOST (CUDA + transformers, or a local OpenAI-compatible server).
#     Still gated by the evidence-freeze declaration; see §13 (local LLM adapter).
```

## 12b. B1.6-v2 supersession (named-vṛtti) — READ BEFORE RUNNING

**B1.6-v1 (directional-axis) is superseded before execution and was never run.** The active representation going
forward is **B1.6-v2 named-vṛtti** (`B1_6_V1_SUPERSEDED_V2_REFREEZE_REPORT.md`). Future runs should target the
**v2** files:

- `frozen/b1_6_pilot_targets_scaffolds_v2_named_vritti.json`
- `frozen/b1_6_pilot_randomized_control_manifest_v2_named_vritti.json`
- `frozen/b1_6_pilot_scaffold_manifest_v2_named_vritti.json`
- table: `track_g_varna_polarity_table_v2_named_vritti.json`

**v1 files are preserved unchanged for audit.** The generation driver/gate currently default to the **v1**
constants; wiring them to accept the v2 paths (and hashing the v2 files in the evidence-freeze declaration) is a
**separate, not-yet-done** step. **No run has occurred on either v1 or v2.** Do not run v1; when v2 wiring lands,
point all generation commands and the declaration hashes at the v2 files above.

## 13. Local LLM adapter (real generation on a model host)

Real generation is provided by `b1_6_llm_adapter.py` (modeled on the B1.1 run pattern):
`TransformersAdapter` (HF model at a frozen revision), `OpenAICompatLocalAdapter` (a **local** vLLM/OpenAI-style
server), and a deterministic `FakeAdapter` for tests. Output-format validation (`Title` / `Interpretation` /
`Practical reflection` / `Caution`, rough length) + a frozen retry policy apply; malformed generations are
**failed, never edited**.

**10-sample exploratory probe** (separate declaration `mode: "exploratory_10_sample_generation_probe"`):

```bash
# operator writes run_out/.../EVIDENCE_FREEZE with mode "exploratory_10_sample_generation_probe"
python3 run_b1_6_pilot_generation.py --local-model <hf_id_or_path> \
        --mode exploratory_10_sample_generation_probe --limit-items 10
# emits run_label B1_6_10_SAMPLE_EXPLORATORY_GENERATION_PROBE; 10 balanced targets x 5 arms = 50.
```

**Full pilot** (`mode: "pilot_generation"`):

```bash
python3 run_b1_6_pilot_generation.py --local-model <hf_id_or_path> --mode pilot_generation
# 24 targets x 5 arms = 120.
```

**Local OpenAI-compatible server** instead of transformers:

```bash
python3 run_b1_6_pilot_generation.py --base-url http://localhost:8000 --local-model <served_model> \
        --mode pilot_generation
```

**RunPod example** (transformers backend): provision a CUDA pod, `pip install torch transformers`, place a
model, write the mode-matched evidence-freeze declaration, then run the full-pilot command above. The driver
**REFUSES** if there is no CUDA/transformers backend (as it does in this environment). The **same fixed model +
settings are used for every arm** (`GenerationSettings`: temperature, top_p, max_tokens, seed) — parity is not
optional. All artifacts land under `run_out/` (gitignored). **Generation never judges**; next step is blind
ratings (`B1_6_PILOT_BLIND_JUDGING_RUNBOOK.md`).

**Failure/retry policy:** each generation is validated for the required sections + rough length; on failure the
adapter retries up to `max_attempts` (frozen), then records a `format_invalid` / `error` failure in the run
manifest and **omits** that output from the judge-visible package — it is never silently edited to look valid.

## 6. Mock-mode command

`python3 run_b1_6_pilot_generation.py --mock` — renders all 120 prompts (24×5), emits
`MOCK_GENERATION_ONLY_DO_NOT_SCORE [<id>]` as each output, writes to `run_out/b1_6_pilot_generation/`. Still
requires a valid declaration (the gate applies in mock mode too).

## 7. Real-mode placeholder command

Real generation is intentionally **not** wired: the CLI refuses without `--mock`, and `run(mock=False, ...)`
raises unless an operator passes an explicit `generator` callable. **No external LLM API call exists in this
module.** An operator supplies the adapter in their own harness.

## 8. Output files (all under `run_out/b1_6_pilot_generation/`; NOT committed)

- `judge_visible_outputs.jsonl` — blinded packages (§9).
- `hidden_arm_metadata.json` — `blinded_output_id → true_arm`, item id, prompt hash, scaffold hash, seed.
- `rendered_prompts_hidden.jsonl` — full prompts (hidden; contain arm/scaffold detail).
- `generation_run_manifest.json` — counts, arms, seed, `judging_performed: false`,
  `b1_4b_prime_status: NULL_RETURN_BOTTOM`.

## 9. Blinding rules

Judge-visible packages contain **only** `item_id`, `target_text`, `neutral_context`, `blinded_output_id`,
`generation_text`, `output_format`. **No** arm name, **no** scaffold metadata, **no** system label. The driver
asserts blindness (`assert_blind`) and raises `INVALID_BLINDING` / `INVALID_LEAKAGE` if a forbidden key or token
appears. **Target text IS shown** to judges (needed for specificity/non-genericity scoring), identical across
arms. Output order should be randomized by the judging harness before rating.

## 10. What may / may not be committed

- **May commit:** the driver, tests, this runbook, the schema doc.
- **Must NOT commit:** the evidence-freeze declaration, any judge-visible outputs, hidden metadata, rendered
  prompts, or any generated text. `run_out/` and the declaration file are **gitignored**.

## 11. Next step after generation

**Blind judging per the rubric — NOT interpretation of the outputs by the runner.** The next artifact is a
blinded judging harness (a different, separately-gated step) that applies the 1–7 rubric (§10 of the prompt/
rubric spec) with the overclaim/hallucination penalties, computes the composite + pairwise preferences, and only
then maps blinded ids back to arms via the hidden metadata. **No terminal `GENUTILITY_*` label may be emitted
from a mock run, and none from a pilot at all** (prereg §13, §15).

## 12. Guardrails

No real generation; no external API; no judging; no evidence freeze created by the assistant; no generated
outputs committed; no semantic-truth claim; no `ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; no target-specific
pole selection (dual-pole, both shown); KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains recorded;
**B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked. **Structure,
not validated meaning.**

## Validation

```bash
python3 -m pytest test_run_b1_6_pilot_generation.py -q      # 22 passed
```

Tests prove: missing-declaration refusal; wrong-mode refusal; all four hash-mismatch refusals; attestation
mismatch; valid-declaration pass; real-mode-requires-adapter; prompt rendering covers 24×5 = 120; Symbol-U
prompt includes the KCPR dual-pole frame; randomized control uses the randomized (not real) scaffold; no
CSR/STL or Kosha in active prompts; judge-visible packages are blind; no arm names in judge-visible outputs;
hidden metadata retains the arm mapping; leakage guard fires; mock outputs are marked not-to-score; no real
generation / no judging; B1.4b′ status referenced as `NULL_RETURN_BOTTOM`.

---

## Final report

- **Files created:** `run_b1_6_pilot_generation.py`, `test_run_b1_6_pilot_generation.py`,
  `B1_6_PILOT_GENERATION_RUNBOOK.md`, `frozen/b1_6_pilot_generation_schema.json`; `.gitignore` updated (ignore
  the evidence-freeze declaration). No prior artifact modified; frozen scaffold data untouched.
- **Commit hash:** (recorded on commit below).
- **Readiness label:** **`B1_6_PILOT_GENERATION_DRIVER_READY_MOCK_TESTED`**.
- **Tests run:** `test_run_b1_6_pilot_generation.py` — **22/22 passed**.
- **Prompts rendered in mock validation:** **120** (24 targets × 5 active arms).
- **Output blinding works?** **Yes** — judge-visible packages carry no arm name/scaffold/system label; guard
  raises on leakage; hidden metadata retains the mapping.
- **No real generation run was performed.**
- **No evidence freeze was declared.**
- **No judging was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 pilot generation driver/runbook drafted and mock-tested only. No real generation run. No judging. No
> evidence freeze. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked.
> Structure, not validated meaning.
