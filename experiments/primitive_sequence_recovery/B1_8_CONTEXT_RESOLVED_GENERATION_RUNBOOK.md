# B1.8 — Context-Resolved KCPR Layer-1 Generation Runbook (specification, docs-only)

**Status:** execution specification for the B1.8 context-resolved KCPR Layer-1 probe. **Docs-only. No
generation. No evidence freeze. No judging. No `GENUTILITY_*`.** Defines how the frozen B1.8 selected-pole
scaffolds are rendered, gated, generated, blinded, judged, and aggregated.

**Readiness label: `B1_8_GENERATION_RUNBOOK_READY`** (spec complete). **The driver is now implemented and
mock-tested** — `run_b1_8_context_resolved_generation.py` (`B1_8_GENERATION_DRIVER_READY_MOCK_TESTED`, 16
tests), commands in §13b. Execution remains gated on an operator evidence-freeze declaration; no real
generation has run.

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. Structure, not validated meaning.

Provenance: prereg `7d149a9`, resolver rulebook `433cf03`, scaffold freeze `c3b7f05`.

---

## 1. Purpose

Specify execution for the B1.8 probe: `context → frozen deterministic resolver → one selected pole per varṇa →
blind generation → blind judging → aggregation`. This is the mechanism B1.6-v2 never tested (it showed both
poles and let the LLM resolve implicitly). All B1.8 results are **conditional on the frozen resolver + context
package** (rulebook §12); the scrambled-selected control is the sole test of whether the *specific* varṇa
content matters.

## 2. Inputs (frozen; hashes pinned in the freeze declaration)

| input | file | sha256 |
|---|---|---|
| prereg | `B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md` | `87456bfcfbcda2076377fd249c4afbae62a0711a10d41742728ecf85deb84b35` |
| resolver rulebook | `B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md` | `a7c53b8ecf9902671a8a4457e5d4b4912f59f4d756b95078b5393d09212f2f2a` |
| selected-pole scaffold | `frozen/b1_8_context_resolved_targets_scaffolds.json` | `b7925ff2aa19a77276b81043d8a019a1c34e8fa754c7fd264e658440edb25015` |
| randomized selected-pole control | `frozen/b1_8_context_resolved_randomized_control_manifest.json` | `eef41543bdfec63acd4dc118cf78ecd7930fe20fbf2e0b8e52e656d148f121f6` |
| scaffold manifest | `frozen/b1_8_context_resolved_scaffold_manifest.json` | `1e94dbaa8123538316e79079461c6349e7f76b1e1579774e16222661f75cfe64` |
| v2 named-vṛtti table | `track_g_varna_polarity_table_v2_named_vritti.json` | `7bc0b7c8c11c68c80d76ac974657611946e076a839f2a053bce9f639cd4a2694` |
| prompt/rubric | `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` | `080a67086c8631568c53c57a02d76f75a8a25f5ce3f8f8bc4f3205655b0ecc5b` |
| phoneme bridge | `frozen/b1_6_phoneme_to_varna_bridge_manifest.json` | `d1851c4abd431ead6ded545e1d2a6ecea29b0638d7f1c34394957439342d87ed` |

## 3. Arms (7)

`KCPR_SELECTED_POLE`, `SCRAMBLED_SELECTED_POLE`, `UNRESOLVED_BOTH_POLES`, `SCRAMBLED_UNRESOLVED`,
`PLAIN_PROMPT_BASELINE`, `GENERIC_STRUCTURED_PROMPT_BASELINE`, `SEMANTIC_LLM_BASELINE`. **Every arm receives the
identical `CONTEXT_TEXT`** for a given item, so context is held constant and only the scaffold varies.

## 4. Primary contrast (make-or-break)

**`KCPR_SELECTED_POLE` vs `SCRAMBLED_SELECTED_POLE`.** Both apply the *same* context, the *same* deterministic
pole-selection rule, and therefore the *same* selected pole polarity per item; they differ in **exactly one
thing** — whether the selected pole's text is the target varṇa's authentic content or a deranged other varṇa's.
This isolates authentic varṇa content **after** the resolution step, which B1.6-v2 could not do. Endpoints:
penalty-adjusted composite (primary) and `specificity_to_target` (pre-registered secondary; the one dimension
that leaned in B1.6).

## 5. Secondary contrasts

- `KCPR_SELECTED_POLE` vs `UNRESOLVED_BOTH_POLES` — does context-conditioned resolution beat the both-poles dump
  (the B1.6-v2 condition), holding context constant?
- `KCPR_SELECTED_POLE` vs `PLAIN_PROMPT_BASELINE` — floor.
- `KCPR_SELECTED_POLE` vs `GENERIC_STRUCTURED_PROMPT_BASELINE` — structure without varṇa content.
- `KCPR_SELECTED_POLE` vs `SEMANTIC_LLM_BASELINE` — strong content ceiling.
- (Support) `SCRAMBLED_SELECTED_POLE` vs `SCRAMBLED_UNRESOLVED`, and `UNRESOLVED_BOTH_POLES` vs
  `SCRAMBLED_UNRESOLVED`, to check the scramble behaves symmetrically to B1.6-v2.

## 6. Prompt rendering (per arm; identical output format)

Shared header (all arms): *"You are an interpreter using a structural lens as a heuristic scaffold — NOT as
truth. Read the item in the given context. Do NOT claim this proves meaning, is true, ancient, or authoritative.
Do NOT mention any system name."* Shared output format (frozen B1.6 rubric): `Title / Interpretation (120–180w) /
Practical reflection (2 bullets) / Caution`.

**`KCPR_SELECTED_POLE`** — fields: `TARGET_TEXT`, `CONTEXT_TEXT`, `SELECTED_PLANE`, `RESOLVER_DECISION` (as an
internal directive, not printed as a label), and the `KCPR_LAYER1_SELECTED_FRAME` rendered as **one facet per
varṇa** (the selected pole's text + the selected plane's sphere gloss). Instruction: *"Emphasize the
{SELECTED_PLANE} plane. Read each element through the single facet given below; synthesize a specific reading of
THIS item in THIS context."* Both poles are **never** shown.

**`SCRAMBLED_SELECTED_POLE`** — **identical** template, same `SELECTED_PLANE` and same selected-pole polarity,
but the frame is `SCRAMBLED_SELECTED_POLE_FRAME` (deranged varṇa→content). Indistinguishable in format from
`KCPR_SELECTED_POLE`.

**`UNRESOLVED_BOTH_POLES`** — **B1.8-specific unresolved rendering** (NOT the B1.6-v2 driver, so context is held
constant): same `TARGET_TEXT` + `CONTEXT_TEXT` + `SELECTED_PLANE`, but renders `UNRESOLVED_BOTH_POLES_FRAME`
(both `worldly_binding_distortion` and `spiritual_liberating_reading` per varṇa) with the B1.6-style *"both
poles shown; do not treat either as correct; let each pole-pair color the reading as a tension field."* This is
the "no Layer-1" comparison under the identical context.

**`SCRAMBLED_UNRESOLVED`** — same as `UNRESOLVED_BOTH_POLES` but with `SCRAMBLED_UNRESOLVED_BOTH_POLES_FRAME`
(deranged both-poles content).

**`PLAIN_PROMPT_BASELINE`** — `TARGET_TEXT` + `CONTEXT_TEXT` only: *"Interpret '{target}' in this context:
{context}."* No varṇa content, no plane.

**`GENERIC_STRUCTURED_PROMPT_BASELINE`** — `TARGET_TEXT` + `CONTEXT_TEXT` + a generic, content-free structural
instruction (*"consider opposing tensions and multiple facets; synthesize a specific reading"*). No varṇa
content.

**`SEMANTIC_LLM_BASELINE`** — `TARGET_TEXT` + `CONTEXT_TEXT` + *"Interpret the word using its ordinary
dictionary/semantic meaning in this context."* Strong content ceiling; no varṇa content.

Rendered prompts are hidden (never judge-visible). Resolver cue counts, pole labels, plane labels, arm names,
and varṇa names are **never** placed in the prompt as printed metadata that could survive into output.

## 7. Evidence-freeze declaration (operator action; NOT created here)

Required fields:
- `artifact`: `b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED`
- `evidence_freeze_declared`: `true`
- `mode`: `b1_8_context_resolved_generation_probe`
- `representation_version`: `B1.8_context_resolved_layer1`
- hashes of **all** §2 frozen inputs (prereg, rulebook, selected-pole scaffold, randomized control, scaffold
  manifest, v2 table, prompt/rubric, bridge) **and** the model-panel manifest
- `declared_by`, `declared_at_utc`
- `attestation` (exact): *"B1.8 context-resolved KCPR Layer-1 generation probe only; context-conditioned
  deterministic pole selection; results conditional on the frozen resolver; no semantic-truth claim; no
  GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM."*

The gate refuses unless mode, representation, every hash, and the attestation match. The declaration and all
`run_out/` artifacts are gitignored (never committed).

## 8. Generation model policy

Reuse the B1.6-v2 model panel (no reason to change): generators **Mistral-7B-Instruct-v0.3** (M1) and
**Qwen2.5-7B-Instruct** (M2); backend `transformers` (direct-load, no vLLM); **sequential single-GPU** preferred
(one model live at a time; per-arm generation; merge + re-blind). Frozen `revision` per operator at run time.

**Expected output count: 12 targets × 7 arms × 2 generators = 168 outputs** (of which the 4 varṇa arms = 96, the
3 baselines = 72). A handful may drop to output-format/blindness filters (recorded as failures, never the run).

## 9. Blinding

**Judges must NOT see:** arm names, generator IDs, resolver cue counts, selected poles / pole labels as
metadata, scaffold labels, varṇa names, or any hidden metadata. **Judges MAY see:** `target_text`,
`context_text`, and the `generation_text`. Because the **same context is used across all arms** for a given
item, context is a constant and does not distinguish arms. Enforcement reuses the shared whole-word leak matcher
(`run_b1_6_pilot_generation.leaked_tokens`) plus the Sanskrit-term filter (as in `perspective_lens_probe.leaked`);
a leaking output is dropped (recorded), never the whole run. Blind judge-visible schema is B1.6-compatible:
`{item_id, target_text, neutral_context:=context_text, blinded_output_id, generation_text, output_format}`;
hidden metadata `{blinded_output_id → true_arm, resolver_decision, selected_plane, generator_code, item_id}` is
withheld until ratings freeze.

## 10. Judging

Reuse the B1.6-v2 3-judge LLM panel unchanged (blind package is field-compatible): **Llama-3.1-8B-Instruct**,
**Meta-Llama-3-8B-Instruct**, **Gemma-2-9b-it** — families (Llama/Gemma) differ from generators (Mistral/Qwen),
so no model judges its own output. Same frozen 1–7 rubric (8 positive + 2 penalty dimensions), JSON output with
retry-on-unparseable, complete-grid merge. **Expected ratings: 168 × 3 = 504.** Judges read only the blind file;
ratings-freeze declaration required before unblinding.

## 11. Aggregation

Reuse `judge_b1_6_pilot_outputs.aggregate` (generic over `true_arm`). Outputs:
- **arm-level** summaries (n, penalty-adjusted composite + bootstrap CI, raw composite, mean penalties) for all 7
  arms;
- **generator-level** summaries (M1/M2);
- **arm × generator** summaries;
- **primary contrast** `KCPR_SELECTED_POLE vs SCRAMBLED_SELECTED_POLE` (arm means + paired-by-item win-rate on
  penalty-adjusted composite and on `specificity_to_target`);
- **secondary contrasts** (§5);
- **exploratory labels only** (`B1_8_PROBE_*` plumbing); descriptive stats, not a powered test at this N.

## 12. No terminal GENUTILITY

This is an **exploratory** probe. It **cannot** emit any prereg `GENUTILITY_*` terminal verdict. A terminal
verdict would require a later, full-scale, separately-preregistered confirmatory run that explicitly authorizes
it (fixed N and the primary endpoint pre-committed before looking). Until then, B1.8 emits only descriptive
`B1_8_PROBE_*` labels.

## 13. Implementation plan (reuse vs new wiring)

**Reused unchanged:** `b1_6_llm_adapter` (transformers/openai_compat_local/fake + retry/greedy fixes);
`b1_6_llm_judge_panel` + `run_b1_6_v2_llm_judge_panel` (3-judge panel); `judge_b1_6_pilot_outputs.aggregate`
(generic arm summary); the shared blindness matcher; the sequential merge/re-blind pattern.

**New wiring required (NOT implemented here):**
1. **`run_b1_8_context_resolved_generation.py`** — the B1.8 driver: per-arm `render_prompt` for the 7 arms
   (reading the frozen B1.8 targets + randomized control), a gated `run()` (B1.8 freeze gate, §7), blinding via
   the shared matcher, and writing the B1.6-compatible blind package + hidden metadata.
2. **B1.8 freeze gate** — `verify_freeze_gate` for `mode=b1_8_context_resolved_generation_probe`,
   `representation_version=B1.8_context_resolved_layer1`, hashing the §2 inputs + panel manifest + attestation.
3. **Sequential 7-arm panel wrapper** — analogous to `run_b1_6_v2_sequential_panel_generation.py` but iterating
   the B1.8 arms and the B1.8 driver (`part` per generator → `merge` re-blind).
4. **Mock tests** — a `test_run_b1_8_context_resolved_generation.py` (FakeAdapter; no model) covering arm
   rendering (selected vs scrambled vs both-poles vs baselines), blinding (no arm/pole/varṇa leak), gate
   refusal, and record counts (12×7=84 records per generator).

The B1.6-v2 generation driver **cannot** be reused directly for the resolved arms — it renders both poles from
`KCPR_DUAL_POLE_FRAME`, does not know B1.8's 7 arms, the `CONTEXT_TEXT` field, or the B1.8 frozen files. Hence a
new driver, but built entirely on the reused adapter/judge/scorer stack.

## 13b. Driver commands (IMPLEMENTED, mock-tested)

Driver: `run_b1_8_context_resolved_generation.py` (+ `test_run_b1_8_context_resolved_generation.py`, 16 tests).
Subcommands `part` (one generator over all 12×7 records → 84 outputs) and `merge` (re-blind parts → final
package). Reuses `b1_6_llm_adapter` (transformers/openai_compat_local/fake) and the shared leak matcher.

**Mock plumbing (no model, no gate — plumbing only):**
```bash
python3 run_b1_8_context_resolved_generation.py part --mock --gen-code M1 --out run_out/b1_8/M1   # n_outputs 84
python3 run_b1_8_context_resolved_generation.py part --mock --gen-code M2 --out run_out/b1_8/M2   # n_outputs 84
python3 run_b1_8_context_resolved_generation.py merge --parts run_out/b1_8/M1 run_out/b1_8/M2 \
        --out run_out/b1_8/generation                                                             # n_outputs 168
```

**Evidence-freeze declaration template** (operator action; gitignored; NOT created here):
```bash
python3 - <<'PY'
import hashlib, json, os, pathlib
import run_b1_8_context_resolved_generation as D
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
decl = {"artifact": "b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION,
        "declared_by": os.environ.get("USER","operator"), "declared_at_utc": "2026-07-09T00:00:00Z",
        "attestation": D.ATTESTATION,
        **{k: sha(v) for k, v in D.HASH_INPUTS.items()}}
pathlib.Path("run_out/b1_8/b1_8_EVIDENCE_FREEZE_DECLARED.json").write_text(json.dumps(decl, indent=2))
print("declared")
PY
```

**Real RunPod run (transformers; sequential single-GPU; gated):**
```bash
export HF_HOME=/workspace/.cache/huggingface; export DECL=run_out/b1_8/b1_8_EVIDENCE_FREEZE_DECLARED.json
python3 run_b1_8_context_resolved_generation.py part --decl "$DECL" --gen-code M1 \
        --backend transformers --model-id mistralai/Mistral-7B-Instruct-v0.3 --out run_out/b1_8/M1   # 84
python3 run_b1_8_context_resolved_generation.py part --decl "$DECL" --gen-code M2 \
        --backend transformers --model-id Qwen/Qwen2.5-7B-Instruct --out run_out/b1_8/M2             # 84
python3 run_b1_8_context_resolved_generation.py merge --parts run_out/b1_8/M1 run_out/b1_8/M2 \
        --out run_out/b1_8/generation                                                               # 168
```
Expected total: **12 × 7 × 2 = 168 outputs**. The `part` command **refuses** without a valid declaration
(mode `b1_8_context_resolved_generation_probe`, representation `B1.8_context_resolved_layer1`, matching B1.8
hashes, exact attestation) — a B1.6-v2 declaration is rejected loudly.

**Next step: blind judging only after generation** — reuse `run_b1_6_v2_llm_judge_panel.py` on
`run_out/b1_8/generation/panel_judge_visible_outputs.jsonl` (Llama/Gemma judges ≠ Mistral/Qwen generators),
then a ratings-freeze, then `judge_b1_6_pilot_outputs.aggregate` with the B1.8 hidden metadata. **168 × 3 = 504
ratings.** No judging is performed here.

## 14. Readiness labels

**`B1_8_GENERATION_RUNBOOK_READY`** — this specification is complete and internally consistent. Execution-phase
labels reserved: `B1_8_GENERATION_BLOCKED_DRIVER_WIRING` (driver not yet implemented — the current execution
state, §13), `B1_8_GENERATION_BLOCKED_ARM_RENDERING`, `B1_8_GENERATION_BLOCKED_FREEZE_GATE`,
`B1_8_GENERATION_INVALID_LEAKAGE`.

## 15. Guardrails

No generation run; no evidence freeze; no judging; no `GENUTILITY_*`; no semantic-truth claim; no ontology; no
Sanskrit privilege. **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. Structure,
not validated meaning.

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_8_CONTEXT_RESOLVED_GENERATION_RUNBOOK.md`
  (docs-only). **No B1.8 frozen scaffold data modified; no B1.6-v2 file modified** (B1.6-v2 referenced only as
  reused harness).
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_8_GENERATION_RUNBOOK_READY` (spec complete); execution
  `B1_8_GENERATION_BLOCKED_DRIVER_WIRING` until the §13 driver is built.
- **Expected generation output count:** **168** (12 targets × 7 arms × 2 generators).
- **Expected rating count:** **504** (168 × 3 judges).
- **Reuse vs wiring:** adapter, judge panel, scorer, blindness matcher, sequential merge **reused unchanged**;
  a **new B1.8 generation driver + freeze gate + 7-arm sequential wrapper + mock tests** must be wired (§13),
  not implemented here.
- **No generation / evidence freeze / judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 generation runbook specified docs-only. No generation run. No evidence freeze. No judging. No GENUTILITY
terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked.
Structure, not validated meaning.
