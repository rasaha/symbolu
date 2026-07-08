# B1.6 — Mock End-to-End Dry Run

**Status:** Mock plumbing dry run (docs + mock-safe execution). Validates file paths, gates, blinding, mock
generation, mock ratings, and aggregation **mechanics only**. **This is NOT evidence.** **No real generation. No
external LLM API call. No real judging. No human ratings. No real evidence-freeze or ratings-freeze declaration.
No `GENUTILITY_*` terminal label.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

**Dry-run label: `B1_6_MOCK_END_TO_END_DRY_RUN_COMPLETE`.**

Exercises: generation driver (`cc56eb1`), operator commands (`3d41c52`), blind judging harness (`6b2b7da`).

---

## 1. Purpose

Confirm the B1.6 pipeline is mechanically sound end-to-end — paths resolve, gates refuse/pass correctly,
blinding holds, mock outputs render, mock ratings validate, and aggregation produces arm summaries + pairwise
contrasts **without** any real model, real judge, real freeze, or terminal verdict. Fabricated numbers are
**not reported and carry no meaning.**

## 2. Preflight

- Branch: `claude/symbolu-adversarial-eval-zevb4h`.
- Required commits present (ancestor of HEAD): **`cc56eb1`**, **`3d41c52`**, **`6b2b7da`** — all confirmed.

## 3. Tests

```bash
python3 -m pytest test_run_b1_6_pilot_generation.py test_judge_b1_6_pilot_outputs.py -q
```

Result: **39 passed** (22 generation-driver + 17 judging-harness).

## 4. Freeze-gate demonstration (real gate)

```bash
python3 run_b1_6_pilot_generation.py --mock
```

Result (**expected refusal**, recorded): `PermissionError: EVIDENCE_FREEZE gate refused: no
EVIDENCE_FREEZE_DECLARED file (operator must create it)`. **No real declaration was created**; the real gate
path `frozen/b1_6_pilot_EVIDENCE_FREEZE_DECLARED.json` remains absent. The gate works as designed: even mock
mode refuses without an operator declaration.

## 5. Mock-only declaration handling

To validate plumbing **without** touching the real gate, the dry run used **mock-only declarations under
`run_out/mock_only/`** (gitignored) and passed them explicitly to the driver/harness via their `decl_path` /
`freeze_path` arguments:

- `run_out/mock_only/MOCK_ONLY_EVIDENCE_FREEZE.json` (generation gate)
- `run_out/mock_only/judge/MOCK_ONLY_RATINGS_FROZEN.json` (judging gate)

**The real declaration paths (`frozen/...`, `run_out/b1_6_pilot_generation/b1_6_pilot_RATINGS_FROZEN.json`) were
NOT created.** The real gate is unchanged.

## 6. Mock generation

Driven as `run(mock=True, decl_path=<mock-only>, out_dir=run_out/mock_only/gen)`:

- **120 prompts rendered** (24 targets × 5 active arms); **120 judge-visible mock outputs**; **120 hidden
  arm-metadata records** written separately.
- Every output text is `MOCK_GENERATION_ONLY_DO_NOT_SCORE [<id>]` (fake; not scoreable).
- **Blinding verified:** no arm names in judge-visible output (`[]` leaked); no forbidden keys
  (`arm`/`true_arm`/`prompt`/`VARNA_PROFILE_TABLE`) present; hidden metadata is a separate file and retains
  `true_arm` for all 120.

## 7. Mock judging

- **Phase A blind check** on the mock judge-visible file → `B1_6_PILOT_JUDGING_BLIND_PACKAGE_OK` (`blind_ok:
  true`); rating template written under `run_out/mock_only/judge/`.
- **Deterministic mock ratings** generated (marked `MOCK_JUDGING_ONLY_DO_NOT_INTERPRET`), then a **mock-only**
  `RATINGS_FROZEN` declaration created under `run_out/mock_only/judge/` (not the real path).

## 8. Mock aggregation

Driven as `aggregate(..., require_freeze=True, freeze_path=<mock-only>)`:

- Label: **`B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED`**.
- **Arm summaries produced** for all 5 arms (`SYMBOLU_SCAFFOLD`, `PLAIN_PROMPT_BASELINE`,
  `GENERIC_STRUCTURED_PROMPT_BASELINE`, `RANDOMIZED_SYMBOLU_CONTROL`, `SEMANTIC_LLM_BASELINE`) — raw +
  penalty-adjusted composites, CIs, variance, penalties.
- **Pairwise summaries produced** for all four Symbol-U-vs-baseline contrasts.
- **`terminal_genutility_label_emitted: false`**; no `GENUTILITY_[A-Z]` verdict token anywhere in the result.
- **The numeric values are fabricated and are NOT reported here** — they mean nothing.

## 9. Output handling

All mock artifacts remain under `run_out/mock_only/` (verified **gitignored**). **Nothing** was committed from
the run: no mock generated outputs, no mock ratings, no hidden metadata, no declarations, no run manifests.
`git status --porcelain` after the run was **empty**.

## 10. Dry-run label

**`B1_6_MOCK_END_TO_END_DRY_RUN_COMPLETE`.** Not `..._BLOCKED_BY_REAL_FREEZE_GATE_AS_DESIGNED` (the real gate
refusal was demonstrated *and* the mock-safe path completed via mock-only declarations). Not
`..._INVALID_BLINDING` / `..._INVALID_LEAKAGE` (blindness held; no arm/token leakage).

## 11. Report

- **Tests passed:** yes — **39/39** (22 + 17).
- **Real freeze gate refused as expected:** yes — recorded `PermissionError` without a real declaration.
- **Mock generation run:** yes — 120 prompts, mock-only declaration under `run_out/mock_only/`.
- **Mock judging/aggregation run:** yes — Phase A blind OK; aggregation via mock-only ratings freeze.
- **Number of mock outputs:** **120** judge-visible (+ 120 hidden-metadata records).
- **Blinding checks passed:** yes — no arm names, no forbidden keys, no forbidden tokens in judge-visible.
- **Any `GENUTILITY_*` label emitted:** no.
- **Any real evidence files created:** no (mock-only declarations under `run_out/`; real paths untouched).
- **Any outputs committed:** no (`run_out/` gitignored; only this doc is committed).

## 12. Guardrails

No real generation; no external API calls; no real judging; no evidence freeze; no ratings freeze (real paths);
no generated outputs committed; no semantic-truth claim; no `ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; KCPR
caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains active; **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original
B1.4b remains blocked; Track B remains blocked. **Structure, not validated meaning.**

---

## Final report

- **Files created:** `experiments/primitive_sequence_recovery/B1_6_MOCK_END_TO_END_DRY_RUN.md` (this doc only).
  No code, data, declaration, or runtime output committed. No prior artifact modified.
- **Commit hash:** (recorded on commit below).
- **Dry-run label:** `B1_6_MOCK_END_TO_END_DRY_RUN_COMPLETE`.
- **Tests run:** `test_run_b1_6_pilot_generation.py` + `test_judge_b1_6_pilot_outputs.py` → **39/39 passed**.
- **Mock generation executed:** yes (120 outputs, mock-only gate under `run_out/`).
- **Mock judging/aggregation executed:** yes (Phase A blind OK; aggregation via mock-only ratings freeze).
- **No real generation occurred.**
- **No real judging occurred** (fabricated ratings only, marked not-to-interpret).
- **No real evidence/rating freeze was declared** (mock-only declarations under `run_out/`; real paths absent).
- **No `GENUTILITY_*` terminal label was emitted.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 mock end-to-end dry run documented/executed only in mock-safe form. No real generation. No real judging.
> No evidence freeze. No ratings freeze. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM.
> Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
