# B1.9 — Generation Probe with Corrected Distant-Source-Word Control (PREREGISTRATION)

**Status:** preregistration + implemented, mock-tested driver. **No real generation run. No judging. No ratings
freeze. No `GENUTILITY_*` terminal label.**

**Readiness label: `B1_9_GENERATION_DRIVER_READY_MOCK_TESTED`.**

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. No ontology, no Sanskrit
privilege, no semantic-truth claim. Structure, not validated meaning.

---

## 0. Honest gating caveat (read first)

This is a **generation-utility** test (ladder claim 4), and it is being run **after** the B1.9 embedding
content-distance gate returned **null on its corrected primary control** (`distant_source_word_mapping`:
mean_delta −0.0178, perm p 0.578, sign 7/5). The preregistered gating logic says generation utility should not
be *promoted* on a null upstream signal. This probe is therefore run as a **confirmatory re-test** of the B1.8
generation result with the **corrected control** substituted — at the operator's explicit direction to judge
correctness from the generation experiment. Interpretation rules (§9) are fixed **in advance** and are
asymmetric: a **null** is the expected, consistent outcome; a **positive** is treated as *not credible* until it
survives blinding, register, and leakage scrutiny and a separately-preregistered powered run. No result here may
emit a terminal verdict.

## 1. Purpose

Repeat the B1.8 generation+judging design, but replace the confounded within-pool "scramble" control with the
**corrected distant-source-word control**: for each target word `W`, the primary control arm reads a **different
real word `W′`'s OWN authentic varṇa-derived facets** (`W′` chosen semantically distant from `W` by
target/context distance only, frozen before outcomes). This asks, at the generation level: *does a reading built
from `W`'s own varṇa facets get judged as more appropriate to `W` than a reading built from a distant real
word's own varṇa facets?*

## 2. Relationship to prior work (what this is based on)

- **Design/harness:** B1.8 generation pipeline (`run_b1_8_context_resolved_generation.py`) — reused structurally.
- **Items:** the frozen 12 B1.9 targets (`frozen/b1_9_targets.json`), themselves extracted from B1.8.
- **Facet content:** each varṇa's `named_attribute` from the v2 named-vṛtti table — the **same field** the B1.9
  embedding test aggregated (so the generation and embedding tracks test the same corrected control).
- **W→W′ map:** `frozen/b1_9_gen_distant_source_map.json`, frozen verbatim from the B1.9 embedding run's
  `_freeze_distant_source_map` (target/context distance only; commit `c05a443`).
- **Judges + aggregation:** the B1.6-v2 3-judge panel and `judge_b1_6_pilot_outputs.aggregate`, **reused
  unchanged** (arm-agnostic).

## 3. Arms (6)

Every arm receives the **identical `CONTEXT_TEXT`** for a given item; only the scaffold varies.

| arm | facet content | role |
|---|---|---|
| **`AUTHENTIC_MAPPING`** | `W`'s own varṇa `named_attribute` facets | authentic |
| **`DISTANT_SOURCE_MAPPING`** | `W′`'s own varṇa `named_attribute` facets (`W′` = frozen distant source) | **PRIMARY control (corrected)** |
| `SCRAMBLED_WITHIN_POOL` | seeded within-pool derangement of `W`'s varṇas | old B1.8-style control, comparison only |
| `PLAIN_PROMPT_BASELINE` | none | floor |
| `GENERIC_STRUCTURED_PROMPT_BASELINE` | none | structure without varṇa content |
| `SEMANTIC_LLM_BASELINE` | none | strong content ceiling |

## 4. Primary contrast (make-or-break)

**`AUTHENTIC_MAPPING` vs `DISTANT_SOURCE_MAPPING`**, paired by item. Both share the same context, same plane,
same facet-construction pipeline and register; they differ in **exactly one thing** — whether the facets are
`W`'s own or a *distant real word's* own. Endpoints: penalty-adjusted composite (primary) and
`specificity_to_target` (pre-registered secondary — the one dimension that leaned in B1.6).

## 5. Secondary contrasts

- `AUTHENTIC_MAPPING` vs `SCRAMBLED_WITHIN_POOL` — new control vs old within-pool control (B1.8 comparability).
- `AUTHENTIC_MAPPING` vs `PLAIN` / `GENERIC` / `SEMANTIC` — floor, structure-only, content-ceiling.
- `DISTANT_SOURCE_MAPPING` vs `SCRAMBLED_WITHIN_POOL` — do the two control types behave differently?

## 6. Prompt rendering & blinding

Shared header + output format identical to B1.8 (Title / Interpretation 120–180w / 2 bullets / Caution). Facet
arms render `Emphasize the {plane} plane. Read each element through the facets below (a lens only): - …`. Judges
see only `{item_id, target_text, neutral_context, blinded_output_id, generation_text, output_format}`. Arm names,
generator IDs, planes, varṇa names, and the distant-source id are withheld to hidden metadata. Blinding reuses
the shared whole-word method/arm leak matcher; general Sanskrit content words are **not** filtered (they appear
in authentic facets but not baselines, so filtering would cause differential attrition and bias the primary
contrast — same policy as B1.8). A leaking output is dropped and recorded, never the whole run.

## 7. Models

Generators **Mistral-7B-Instruct-v0.3** (M1) and **Qwen2.5-7B-Instruct** (M2); judges **Llama-3.1-8B-Instruct**,
**Meta-Llama-3-8B-Instruct**, **Gemma-2-9b-it** (families disjoint from generators; no model judges its own
output). Backend `transformers` (no vLLM), sequential single-GPU. **Expected: 12 items × 6 arms × 2 generators =
144 outputs; × 3 judges = 432 ratings.** A few may drop to format/blindness filters (recorded as failures).

## 8. Freeze gate (operator action; NOT created here)

`artifact: b1_9_generation_EVIDENCE_FREEZE_DECLARED`, `evidence_freeze_declared: true`,
`mode: b1_9_generation_corrected_control_probe`, `representation_version: B1.9_generation_corrected_control`,
`attestation` = the exact §1 string in `run_b1_9_generation.ATTESTATION`, plus sha256 of each of the six frozen
inputs (prereg, scaffold, distant-source map, targets, v2 table, prompt/rubric) and the model-panel manifest.
The gate refuses any B1.6/B1.8/B1.9-content-distance mode, wrong representation, missing attestation, or hash
mismatch. Declaration and all `run_out/` artifacts are gitignored (never committed).

## 9. Interpretation rules (fixed in advance; asymmetric per §0)

- **Null** (`AUTHENTIC` ≈ `DISTANT_SOURCE`, paired win-rate ≈ 0.5, composite diff ≈ 0): the corrected control is
  not beaten at the generation level — **consistent with B1.4b′ and the B1.9 embedding null.** Expected outcome.
- **Authentic > DISTANT_SOURCE:** a *candidate* generation-level signal — but **not credible** until (a) blinding
  is re-audited for leakage, (b) it is not explained by facet count / length / Sanskrit-echo, and (c) a
  separately-preregistered powered run with fixed N confirms it. Still **no** ontology / truth / privilege.
- **Authentic < DISTANT_SOURCE:** authentic underperforms even a distant word's mapping — a strong null/negative.
- **Under no outcome** emit `ONTOLOGICAL_SIGNAL` or `GENUTILITY_*`. Descriptive `B1_9_GEN_PROBE_*` labels only.

## 10. Guardrails

No real generation / judging performed in this commit. No `run_out/` committed. No `GENUTILITY_*`; no
semantic-truth, ontology, or Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b
blocked; Track B blocked. Structure, not validated meaning.

---

## Final report

- **Files:** created `B1_9_GENERATION_PREREG.md`, `run_b1_9_generation.py`,
  `test_run_b1_9_generation.py`, `build_b1_9_gen_scaffold.py`, `frozen/b1_9_gen_distant_source_map.json`,
  `frozen/b1_9_gen_targets_scaffolds.json`; RunPod commands in `B1_9_GENERATION_RUNPOD_COMMANDS.md`.
- **Readiness label:** `B1_9_GENERATION_DRIVER_READY_MOCK_TESTED`.
- **Primary contrast:** `AUTHENTIC_MAPPING` vs `DISTANT_SOURCE_MAPPING` (corrected distant-source control).
- **Expected outputs / ratings:** 144 / 432.
- **Real generation run?** No. **Judging?** No. **`run_out/` committed?** No. **B1.10 created?** No.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.9 generation probe (corrected distant-source control) preregistered and driver mock-tested. No real
generation. No judging. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated
meaning.
