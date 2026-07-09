# B1.6 — Multi-Model Orchestration Specification

**Status:** Multi-model orchestration spec + gated mock-tested code. Mirrors the B1.1 dual-generator + 3-judge
panel. **No real generation. No real judging. No external API call. No evidence/ratings freeze. No
`GENUTILITY_*` label.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_MULTI_MODEL_ORCHESTRATION_CODE_READY_MOCK_TESTED`.**

Code: `b1_6_model_panel.py`, `test_b1_6_model_panel.py` (12/12); driver threads `gen_code`
(`run_b1_6_pilot_generation.py`). Adapter: `b1_6_llm_adapter.py` (`96dd9ab`).

---

## 1. B1.1 model-panel audit (found)

`B1_6_MULTI_MODEL_ORCHESTRATION_BLOCKED_B1_1_PATTERN_NOT_FOUND` does **not** apply — the pattern was found:

- **Generators** (`b1_1_generation_config.json` → `generation_models`, sourced from
  `TRACK_B_RUNTIME_MODEL_LOCK.yaml`): `mistralai/Mistral-7B-Instruct-v0.3` (rev `c170c708…`),
  `Qwen/Qwen2.5-7B-Instruct` (rev `a09a3545…`); `provider_runtime: transformers`; decode `temperature 0.7,
  top_p 0.95, max_tokens 300`, `number_of_samples_per_cell: 2`, `generation_seeds: [1101, 2027]`.
- **Judges** (`b1_1_judge_panel_config.json` → `judge_model_ids`): `meta-llama/Llama-3.1-8B-Instruct`,
  `meta-llama/Meta-Llama-3-8B-Instruct`, `google/gemma-2-9b-it`; blinded pairwise, JSON-only, greedy;
  per-judge caveats + acceptance-required-before-freeze.
- **Storage/aggregation:** per-cell JSONL rows; judge verdicts aggregated with structured error rows + a frozen
  retry policy; different model families for generation vs judging.

## 2. Current B1.6 gap (confirmed)

Before this spec, B1.6 supported **one model at a time only**: `run()` takes a single adapter/settings; the
judging harness takes a single ratings list. **No** multi-generator orchestration, **no** multi-judge panel,
**no** model-panel manifest. This spec + `b1_6_model_panel.py` add the generator-panel orchestration and the
manifest; multi-judge aggregation is specified here and left to the judging step (per-judge ratings feed the
existing harness).

## 3. B1.6 model panel (modeled on B1.1; IDs operator-frozen at run time)

- **Generators:** a Mistral-family instruct model + a Qwen-family instruct model (e.g.
  `mistralai/Mistral-7B-Instruct-v0.3`, `Qwen/Qwen2.5-7B-Instruct`) — exact IDs/revisions **frozen by the
  operator**.
- **Judges:** two Meta-Llama-family judges + one Google-Gemma-family judge (e.g.
  `meta-llama/Llama-3.1-8B-Instruct`, `meta-llama/Meta-Llama-3-8B-Instruct`, `google/gemma-2-9b-it`) — exact IDs
  **frozen by the operator**. `b1_6_model_panel.B1_1_REFERENCE_PANEL` records this reference set with
  `revision: "<operator-frozen>"`.

## 4. No same-model judging (rule)

- **A model must not judge its own generated outputs.** `detect_same_model_conflicts()` flags any judge whose
  **id** equals a generator id (`SAME_MODEL`).
- **Judge family should differ from generator family** where possible; a shared family is flagged
  (`SAME_FAMILY`), recorded in the panel manifest, and — if unavoidable — the run is marked **exploratory
  only**. The reference panel (Mistral/Qwen generators vs Llama/Gemma judges) is **conflict-free**.

## 5. Model manifest schema

`b1_6_model_panel_manifest` (a config, not judge-visible) records: `generator_models[]` and `judge_models[]`
(each `id`, `family`, `revision`); `backend`; endpoint/`hardware notes` (operator); decode (`temperature`,
`max_tokens`, `seed`) via `GenerationSettings`; `generator_codes` (opaque `M1/M2 → id`); `same_model_conflicts`;
`n_generators`/`n_judges`/`n_arms`/`n_targets`/`expected_outputs`/`n_outputs`; `per_generator_counts`;
`reblind_seed`; `panel_sha256`; `declared_by`/`declared_at_utc` (operator); `judging_performed: false`;
`b1_4b_prime_status`.

## 6. 10-sample exploratory generation count

10 targets × 5 arms × **2 generators = 100** generated outputs. **Exploratory only** — mode
`exploratory_10_sample_generation_probe`, `run_label = B1_6_10_SAMPLE_EXPLORATORY_GENERATION_PROBE`; it **cannot**
emit a `GENUTILITY_*` verdict and does not masquerade as the full pilot (full pilot = 24 × 5 × 2 = 240).

## 7. Judging design (3-judge panel)

- Judges see **only** the blinded, **re-blinded** judge-visible package (§8) — no arm, no generator, no scaffold.
- **No hidden metadata is joined until ratings are frozen** (ratings-freeze gate in the judging harness).
- Each of the 3 judges rates **all** outputs (or a balanced subset); ratings are collected **per judge**.
- Aggregate **by judge and overall** (mean raw + penalty-adjusted composites, pairwise preferences).
- **Inter-judge agreement** (e.g. Krippendorff's α / ICC) computed where feasible; low agreement →
  inconclusive. **No model judges its own outputs** (§4).

## 8. Runner support (added, gated, mock-tested)

`b1_6_model_panel.run_panel(panel, adapter_factory, mock, mode, limit_items, decl_path, out_dir, write)`:

- iterates `generator_models`, assigning each an **opaque code** `M1/M2…`; runs the **gated** driver per
  generator (real adapter from `adapter_factory(gen)` on a model host, or `--mock`);
- **RE-BLINDS** the merged pool: final ids `F0001…` assigned in a deterministic hash order so **neither the arm
  nor the generator is inferable** from a judge-visible id;
- writes `panel_judge_visible_outputs.jsonl` (blinded), `panel_hidden_arm_generator_metadata.json`
  (`Fid → true_arm + generator_code + generator_id`), and `panel_run_manifest.json`.

CLI: `python3 b1_6_model_panel.py --model-panel-manifest <json> --mock --limit-items 10` (plumbing only). Real
panel generation refuses from the CLI (needs per-generator adapters on a model-access host + a matching operator
declaration). The gate + CUDA-readiness refusals from the driver apply per generator.

## 9. Tests (fake adapters only; 12/12)

Two fake generators → **100** outputs (10-sample) / **240** (full); generator id/code **only in hidden**
metadata, absent from judge-visible (`assert_blind`); re-blinding interleaves generators (not blocked M1|M2);
panel manifest `panel_sha256` recorded + `generator_codes` map; `SAME_MODEL`/`SAME_FAMILY` conflicts detected;
panel refuses without a declaration; no `GENUTILITY_*`; `judging_performed: false`; **no external API**.

## 10. Guardrails

No real generation; no real judging; no evidence/ratings freeze; no `GENUTILITY_*`; no semantic-truth claim; no
`ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains active;
**B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. **Structure, not validated
meaning.**

---

## Final report

- **Files created/modified:** created `b1_6_model_panel.py`, `test_b1_6_model_panel.py`,
  `B1_6_MULTI_MODEL_ORCHESTRATION_SPEC.md`; updated `run_b1_6_pilot_generation.py` (thread `gen_code` into
  hidden metadata). No frozen data or non-B1.6 artifact modified.
- **Commit hash:** (recorded on commit below).
- **B1.1 multi-model pattern found?** **Yes** — Mistral+Qwen generators; Llama×2 + Gemma judges; config + lock
  audited.
- **Did B1.6 already support it?** **No** — one model at a time; this **now specs + implements** the generator
  panel (mock-tested) and specifies the 3-judge aggregation.
- **Readiness label:** `B1_6_MULTI_MODEL_ORCHESTRATION_CODE_READY_MOCK_TESTED`.
- **Expected output count for the 10-sample panel:** **100** (10 × 5 × 2). Full pilot panel: 240.
- **No real generation or judging occurred.**

> B1.6 multi-model orchestration spec drafted/mocked only. No real generation. No real judging. No evidence
> freeze. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track
> B remains blocked. Structure, not validated meaning.
