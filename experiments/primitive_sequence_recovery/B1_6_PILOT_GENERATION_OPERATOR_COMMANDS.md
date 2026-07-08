# B1.6 — Pilot Generation Operator Commands

**Status:** Operator command reference (docs only). **This document executes nothing.** It records the exact
shell commands an operator runs to verify inputs, declare the evidence freeze, run mock generation, and (via an
operator-supplied adapter) run real generation — then locate outputs while preserving blinding and git safety.
**No generation run, no judging, no evidence freeze declared here.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `GENUTILITY_*` label. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_PILOT_GENERATION_OPERATOR_COMMANDS_DOCUMENTED`.**

Driver: `run_b1_6_pilot_generation.py` (`cc56eb1`). Runbook: `B1_6_PILOT_GENERATION_RUNBOOK.md`.

---

## 1. Purpose

Give the **operator command sequence only**. The assistant does **not** run these commands, does **not** create
the evidence-freeze declaration, and does **not** perform generation or judging. Running the real pilot is an
operator action (e.g. on RunPod) with the operator's own model + network.

## 2. Current status

- Commit: **`cc56eb1`** (driver + runbook + schema).
- Driver: **ready, mock-tested** (`B1_6_PILOT_GENERATION_DRIVER_READY_MOCK_TESTED`; 22/22 tests; 120 prompts =
  24 targets × 5 active arms in mock validation).
- **No evidence freeze declared.** **No generation run.** **No judging performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

## 3. Checkout / preflight

```bash
# from the repo root
git fetch origin claude/symbolu-adversarial-eval-zevb4h
git checkout claude/symbolu-adversarial-eval-zevb4h
git log --oneline -1                      # expect cc56eb1 (or a later commit) present
git merge-base --is-ancestor cc56eb1 HEAD && echo "cc56eb1 present" || echo "cc56eb1 MISSING"

cd experiments/primitive_sequence_recovery

# driver plumbing tests (mock; no real generation, no external API)
python3 -m pytest test_run_b1_6_pilot_generation.py -q          # expect 22 passed

# Stage A' sanity (lightweight; no outputs written)
python3 -m pytest test_stage_a_prime_coverage.py -q             # expect 11 passed
```

## 4. Frozen input verification

```bash
cd experiments/primitive_sequence_recovery
sha256sum \
  frozen/b1_6_pilot_targets_scaffolds.json \
  frozen/b1_6_pilot_scaffold_manifest.json \
  frozen/b1_6_pilot_randomized_control_manifest.json \
  B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md \
  frozen/b1_6_pilot_generation_schema.json
```

**Reference hashes at `cc56eb1`** (recompute on your checkout; must match before declaring the freeze):

| File | sha256 |
|---|---|
| `frozen/b1_6_pilot_targets_scaffolds.json` | `6a76825fc87481ce465d60cfda6ec7a18ad39c945b9277f6e11629b583ae1c19` |
| `frozen/b1_6_pilot_scaffold_manifest.json` | `e51885f15584bea43bd3ef60a30e8daf576c52b982605ff65b0275b6e67aeb61` |
| `frozen/b1_6_pilot_randomized_control_manifest.json` | `3a9cac7ef50e85ab66fdfb5ecb001ea55329fe95392fb9caa86016f1cc951c3c` |
| `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` | `080a67086c8631568c53c57a02d76f75a8a25f5ce3f8f8bc4f3205655b0ecc5b` |
| `frozen/b1_6_pilot_generation_schema.json` | `7b22930263edf0bae79f1f36e7fa7e4ef0e35c3aee43e685f9b1b759e85c0eb8` |

*(The driver re-hashes the first four against the declaration and refuses on any mismatch. The schema file is
descriptive and is not gate-checked.)*

## 5. Evidence-freeze declaration schema

Path (operator-created; **gitignored; never committed**): `frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json`

Required fields:

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
  "declared_at_utc": "<ISO-8601, e.g. 2026-07-08T12:00:00Z>",
  "attestation": "B1.6 pilot generation only; no judging; no semantic truth claim; Symbol-U utility test only; B1.4b′ remains NULL_RETURN_BOTTOM."
}
```

The attestation string must be **exactly** as above (the driver compares it verbatim).

## 6. Command to create the declaration

> **⚠ OPERATOR ACTION — DO NOT RUN UNLESS AUTHORIZING GENERATION.**
> The assistant must never run this. It commits you to a pilot generation run.

```bash
cd experiments/primitive_sequence_recovery
python3 - <<'PY'
import hashlib, json, datetime, pathlib
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
decl = {
  "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": True,
  "mode": "pilot_generation",
  "scaffold_manifest_sha256": sha("frozen/b1_6_pilot_scaffold_manifest.json"),
  "target_scaffold_sha256": sha("frozen/b1_6_pilot_targets_scaffolds.json"),
  "randomized_control_manifest_sha256": sha("frozen/b1_6_pilot_randomized_control_manifest.json"),
  "prompt_rubric_sha256": sha("B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md"),
  "declared_by": "REPLACE_WITH_OPERATOR_ID",
  "declared_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "attestation": "B1.6 pilot generation only; no judging; no semantic truth claim; "
                 "Symbol-U utility test only; B1.4b′ remains NULL_RETURN_BOTTOM.",
}
pathlib.Path("frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json").write_text(json.dumps(decl, indent=2, ensure_ascii=False))
print("declaration written (gitignored). Set declared_by before use.")
PY
```

## 7. Mock generation command

```bash
cd experiments/primitive_sequence_recovery
python3 run_b1_6_pilot_generation.py --mock          # still gated: requires the §6 declaration
```

- **Mock output is NOT evidence.** Every output is `MOCK_GENERATION_ONLY_DO_NOT_SCORE [<id>]`.
- **Mock outputs must NOT be judged.** Mock mode validates plumbing only (rendering, blinding, packaging).
- Without a valid declaration the driver **refuses** even in mock mode.

## 8. Real generation command (placeholder — no external API wired)

**The current driver cannot run real generation from the CLI.** `python3 run_b1_6_pilot_generation.py` (without
`--mock`) exits with a refusal; there is **no** external LLM API in the module. A real run requires an
**operator-supplied adapter** — a callable `generator(record) -> str` — invoked from the operator's own harness:

```python
# operator harness (NOT part of this repo module); pseudo-shape only
from run_b1_6_pilot_generation import run
def my_adapter(record):
    # record["prompt"] -> operator's chosen model (frozen model/temp/max_tokens);
    # return the model's text. Same model/settings for ALL arms (parity).
    ...
res = run(mock=False, generator=my_adapter)   # gated: requires the §6 declaration
```

Parity requirements (prompt/rubric spec §5): **same model, temperature, max tokens, output format, and token
budget across all five arms; no arm labels in output.**

## 9. Expected output files

Under `run_out/b1_6_pilot_generation/` (created at run time; **NOT committed**):

- `judge_visible_outputs.jsonl` — blinded packages (§10).
- `hidden_arm_metadata.json` — `blinded_output_id → true_arm`, item id, prompt hash, scaffold hash, seed.
- `rendered_prompts_hidden.jsonl` — full prompts (hidden; contain arm/scaffold detail).
- `generation_run_manifest.json` — counts, arms, seed, `judging_performed: false`,
  `b1_4b_prime_status: NULL_RETURN_BOTTOM`.

## 10. Blinding rules

- The **judge-visible** file must contain **no arm names**, **no Symbol-U / varṇa / KCPR labels**, and **no
  scaffold metadata** — only `item_id`, `target_text`, `neutral_context`, `blinded_output_id`,
  `generation_text`, `output_format`. (The driver asserts this and raises on violation.)
- **Hidden metadata must be withheld from judges** until after scoring.
- **Target text MAY be visible to judges** — required for specificity / non-genericity scoring.
- The judging harness should **randomize output order** per item before rating.

## 11. Git safety

```bash
git status --short          # inspect BEFORE any add/commit
```

- **Do NOT commit** `run_out/` (gitignored).
- **Do NOT commit** the evidence-freeze declaration `frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json`
  (gitignored).
- **Do NOT commit** generated outputs, hidden metadata, or rendered prompts.
- Confirm `git status --short` shows none of the above before committing anything.

## 12. After generation

The next step is a **blind judging harness / judge package** — **not** interpretation of the outputs by the
runner, **not** any terminal claim. **No `GENUTILITY_*` label may be emitted from the pilot** (prereg §13, §15);
the pilot validates plumbing and rubric discrimination only. A real utility claim requires the full run with
blind (preferably human) judges and a generator independent of the judge.

## 13. Guardrails

- **No generation executed by this document.** **No evidence freeze declared by this document.** **No judging.**
- No semantic-truth claim; no `ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; no target-specific pole selection
  (dual-pole, both poles shown); the KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains active.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b remains blocked. Track B remains blocked. **Structure,
  not validated meaning.**

## 14. Readiness label

**`B1_6_PILOT_GENERATION_OPERATOR_COMMANDS_DOCUMENTED`.**

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_6_PILOT_GENERATION_OPERATOR_COMMANDS.md`. No
  prior artifact modified; no code, no data, no declaration written.
- **Commit hash:** (recorded on commit below).
- **Readiness label:** `B1_6_PILOT_GENERATION_OPERATOR_COMMANDS_DOCUMENTED`.
- **Commands were documented only** — none executed by this document.
- **No evidence freeze was declared.**
- **No mock or real generation was run.**
- **No judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 pilot generation operator commands documented only. No generation run. No judging. No evidence freeze.
> B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not
> validated meaning.
