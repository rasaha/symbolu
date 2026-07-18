# B1.6 — Pilot Blind Judging Runbook (Two-Phase; Mock-Tested)

**Status:** Operator runbook + gated two-phase judging harness (mock-tested). **No real judging. No external LLM
API call. No generation. No ratings freeze created by the assistant. No `GENUTILITY_*` terminal label.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

**Readiness label: `B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED`.**

Harness: `judge_b1_6_pilot_outputs.py`. Tests: `test_judge_b1_6_pilot_outputs.py` (17/17).
Schema: `frozen/b1_6_pilot_judging_schema.json`. Consumes the generation driver's outputs (`cc56eb1`).

---

## 1. Purpose

Make pilot judging **mechanical and blinded**: verify the generated outputs carry no arm identity, hand judges a
rating template, and — **only after ratings are frozen** — join ratings with the hidden arm metadata to compute
arm-level composites and pairwise preferences. **The pilot emits only plumbing labels; it never emits a
`GENUTILITY_*` verdict.**

## 1b. After a v2 panel/sequential generation — exact next steps

The multi-model / sequential path writes **`panel_*`** files (not the single-model names). The judging harness
now auto-detects them via `locate_generation_package(gen_dir)`:

- `panel_judge_visible_outputs.jsonl` (100 outputs for the 10-sample probe),
- `panel_hidden_arm_generator_metadata.json` (carries `true_arm` **and** `generator_code`/`generator_id`),
- `panel_run_manifest.json` (`representation_version: v2_named_vritti`).

Next steps: **(1) verify the generation package** (§13 checks: 100 outputs, no arm/generator leak);
**(2) export the blind rating template** with Phase A pointed at the panel judge-visible file;
**(3) collect ratings** — from a **manual/CSV** panel or an operator-run **LLM-judge** (a model **different**
from the generators; the harness does **not** run LLM judges itself — ratings are operator-supplied);
**(4) freeze ratings** (operator `RATINGS_FROZEN` declaration); **(5) aggregate/unblind** with
`representation_version="v2_named_vritti"` and the panel hidden metadata. Aggregation then emits **arm-level**,
**generator-level**, and **arm×generator** summaries plus the pairwise contrasts — exploratory labels only.

```bash
cd experiments/primitive_sequence_recovery
GEN=run_out/b1_6_10_sample_probe/generation
# Phase A on the panel judge-visible file:
python3 -c "import judge_b1_6_pilot_outputs as J, pathlib; \
info=J.locate_generation_package(pathlib.Path('$GEN')); print(info['kind'], info['representation_version']); \
print(J.phase_a_blind_package(info['judge_visible'], out_dir=pathlib.Path('run_out/b1_6_pilot_judging'), write=True)['label'])"
# ... then collect + freeze ratings (operator), then aggregate (Phase B) with the panel hidden metadata.
```

## 2. Blind rating workflow (Phase A)

```bash
cd experiments/primitive_sequence_recovery
python3 judge_b1_6_pilot_outputs.py --phase A
```

Phase A reads `run_out/b1_6_pilot_generation/judge_visible_outputs.jsonl`, runs the **blindness check** (§ Blind
checks), and writes `run_out/b1_6_pilot_judging/judge_rating_template.csv` +
`blindness_check_report.json`. If the outputs are not blind, it returns `B1_6_PILOT_JUDGING_INVALID_BLINDING`
and writes no template. If the outputs file is missing, it returns
`B1_6_PILOT_JUDGING_BLOCKED_NO_GENERATED_OUTPUTS`.

**Blind checks (reject if any present):** arm names; `Symbol-U`/`varṇa`/`KCPR` labels; scaffold metadata
fields (`VARNA_PROFILE_TABLE`, `VARNA_SEQUENCE`, `KCPR_DUAL_POLE_FRAME`, …); hidden-metadata fields
(`true_arm`, `prompt`, `scaffold_hash`, `randomization_seed`); generator prompt text; any field revealing the
true arm; forbidden tokens in `generation_text`. **Target text and neutral context MUST be present** (needed
for specificity scoring).

## 3. Human judge workflow

- Judges receive **only** `judge_rating_template.csv` (blinded id + target + empty rating columns).
- Each row rated on the **1–7** rubric: positive dims — coherence, specificity_to_target, interpretive_richness,
  practical_usefulness, non_genericity, creativity_aesthetic, internal_consistency, caution_epistemic_humility;
  penalty dims — overclaim_penalty, hallucination_penalty (1 = none/best, 7 = worst).
- Judges do **not** see arm identity, the scaffold, or the hidden metadata. Randomize row order per item before
  handing out. ≥3 independent judges recommended for a real run; IRR reported.

## 4. LLM-as-judge pilot-only workflow (automated; sequential single-GPU)

An automated 3-judge LLM panel is available: `b1_6_llm_judge_panel.py` + `run_b1_6_v2_llm_judge_panel.py`
(verified subcommands `judge`, `merge`). Judges read **only** the blind judge-visible file (never hidden
metadata), rate each output on the frozen 1-7 rubric, return strict JSON, and the runner merges the three parts
into scorer-ready ratings. Judges (Llama×2 + Gemma) must differ in **model and family** from the generators
(Mistral/Qwen) — `detect_judge_generator_conflicts` refuses a same-model judge. **No terminal claim** may be
drawn from an LLM-judge pilot; ratings still go through the §5 ratings-freeze gate before §6 unblinding.

**Sequential single-GPU** (one judge server live at a time; blind judge-visible file = the panel output):

```bash
cd experiments/primitive_sequence_recovery
PROBE=run_out/b1_6_10_sample_probe
JV=$PROBE/generation/panel_judge_visible_outputs.jsonl
JPANEL=$PROBE/judge_panel.json     # {"judge_models":[{id,family,endpoint}...], "generator_models":[...]}

# for each judge index 0,1,2:  start its vLLM server, run one part, stop it
python3 -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct --port 8101 & JPID=$!
python3 run_b1_6_v2_llm_judge_panel.py judge --panel "$JPANEL" --judge-index 0 \
        --judge-visible "$JV" --out "$PROBE/judging_partial_J1"    # 100 ratings
kill $JPID
#   ...repeat --judge-index 1 (port 8102) -> judging_partial_J2, --judge-index 2 -> judging_partial_J3...

# merge the three judge parts into scorer-ready ratings (refuses on duplicate judge / incomplete grid)
python3 run_b1_6_v2_llm_judge_panel.py merge \
        --parts "$PROBE/judging_partial_J1" "$PROBE/judging_partial_J2" "$PROBE/judging_partial_J3" \
        --out "$PROBE/judging"                                     # 300 ratings (100 x 3)
```

Then create the §5 `RATINGS_FROZEN` declaration over `$PROBE/judging/llm_judge_ratings_raw.jsonl` and the
judge-visible file, and aggregate/unblind (§6) with the panel hidden metadata + `representation_version=
v2_named_vritti`.

## 5. Ratings-freeze declaration

Operator creates `run_out/b1_6_pilot_generation/b1_6_pilot_RATINGS_FROZEN.json` (**NOT committed**) **before**
unblinding:

```json
{
  "artifact": "b1_6_pilot_RATINGS_FROZEN",
  "ratings_frozen": true,
  "mode": "pilot_judging",
  "judge_visible_outputs_sha256": "<sha256 of judge_visible_outputs.jsonl>",
  "ratings_file_sha256": "<sha256 of the frozen ratings file>",
  "declared_by": "<operator id>",
  "declared_at_utc": "<ISO-8601>",
  "attestation": "B1.6 pilot ratings frozen before unblinding; pilot only; no terminal GENUTILITY verdict; no semantic truth claim."
}
```

> **⚠ OPERATOR ACTION — DO NOT RUN UNLESS AUTHORIZING UNBLINDING.** The assistant never creates this.

The harness refuses Phase B on: missing declaration, `mode != pilot_judging`, any missing field, wrong
attestation, or a hash mismatch on the judge-visible outputs or the ratings file.

## 6. Unblinding step (Phase B)

Phase B is not CLI-runnable without an operator ratings file + freeze declaration. In an operator harness:

```python
from judge_b1_6_pilot_outputs import aggregate
import json, pathlib
ratings = json.loads(pathlib.Path("run_out/b1_6_pilot_generation/ratings.json").read_text())
hidden  = json.loads(pathlib.Path("run_out/b1_6_pilot_generation/hidden_arm_metadata.json").read_text())
res = aggregate(ratings, hidden, require_freeze=True, write=True)   # gated on RATINGS_FROZEN
print(res["label"])
```

Hidden arm metadata is joined **only here**, after the freeze. Before the freeze the refusal result contains no
arm mapping and no summary.

## 7. Aggregation commands / outputs

After freeze, Phase B writes to `run_out/b1_6_pilot_judging/` (NOT committed):

- `pilot_judging_summary.json` — per-arm mean **raw** composite + mean **penalty-adjusted** composite, bootstrap
  95% CIs, item-level variance, mean penalties; `terminal_genutility_label_emitted: false`.
- `pairwise_preference_summary.json` — Symbol-U vs plain / generic-structured / randomized-Symbol-U /
  semantic-LLM (win/tie/loss + win rate, paired by item on the penalty-adjusted composite).
- `unblinded_arm_summary.json` — the `blinded_output_id → true_arm` map used for aggregation (marked
  `MOCK_JUDGING_ONLY_DO_NOT_INTERPRET` in mock runs).

## 8. What must not be committed

- `run_out/` (gitignored) — templates, reports, summaries, unblinded map.
- The ratings-freeze declaration.
- Any ratings file, generated output, or hidden metadata.
- Verify with `git status --short` before any commit.

## 9. Why the pilot cannot emit `GENUTILITY_*`

Per prereg §13/§15, the pilot validates **plumbing and rubric discrimination only**. It has too few items/judges
for a real claim, may use an LLM-judge triage, and (in mock) uses fabricated ratings. The harness therefore
emits only `B1_6_PILOT_JUDGING_*` plumbing labels and sets `terminal_genutility_label_emitted: false`. A real
`GENUTILITY_*` verdict requires the **full run**: frozen targets/prompts/scaffold, an evidence freeze, a
generator **independent** of the judge, blind (preferably human) judges with adequate IRR, and the prereg's
thresholds and multiple-comparison correction.

## 10. Guardrails

No real judging; no external API; no generation; no evidence freeze; no ratings freeze created by the assistant;
no generated outputs committed; no semantic-truth claim; no `ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; no
target-specific pole selection; KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains active; **B1.4b′ remains
`NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked. **Structure, not validated
meaning.**

## Validation

```bash
python3 -m pytest test_judge_b1_6_pilot_outputs.py -q      # 17 passed
python3 -m pytest test_run_b1_6_pilot_generation.py -q     # 22 passed (generation driver)
```

Judging tests prove: blind package passes when clean; fails on arm-name key, on scaffold field, and on
Symbol-U/KCPR token in text; blocked when no generated outputs; complete rating validates; incomplete and
out-of-range ratings rejected; penalty reduces the adjusted composite; aggregation refuses before the freeze;
succeeds after a mock freeze; hash mismatch refuses; incomplete ratings raise in aggregation; hidden metadata
used only after freeze; no `GENUTILITY_*` verdict emitted; pairwise contrasts present; B1.4b′ referenced as
`NULL_RETURN_BOTTOM`.

---

## Final report

- **Files created:** `judge_b1_6_pilot_outputs.py`, `test_judge_b1_6_pilot_outputs.py`,
  `B1_6_PILOT_BLIND_JUDGING_RUNBOOK.md`, `frozen/b1_6_pilot_judging_schema.json`. No prior artifact modified.
- **Commit hash:** (recorded on commit below).
- **Readiness label:** **`B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED`**.
- **Tests run:** `test_judge_b1_6_pilot_outputs.py` **17/17**; `test_run_b1_6_pilot_generation.py` **22/22**.
- **No real judging was performed.**
- **No generation was run.**
- **No ratings freeze was declared.**
- **No `GENUTILITY_*` terminal label was emitted.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 blind judging harness/runbook drafted and mock-tested only. No generation run. No real judging. No ratings
> freeze. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B
> remains blocked. Structure, not validated meaning.
