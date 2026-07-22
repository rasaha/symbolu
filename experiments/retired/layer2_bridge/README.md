# RETIRED — Layer-2 Synthesis Bridge (research-only archive)

This directory archives the obsolete **Layer-2 synthesis bridge** and its data after the B1.12 varṇa
mapping migration. Retention is for **reproducibility only**. Nothing here is on any production path.

## Original purpose

The Layer-2 bridge (`layer2_bridge_vocab.json`, consumed by
`varna_lens/sample_text_rule_harness.py::synthesize`/`_bridge`/`_canon`, and read downstream by
`layer3_dictionary_bridge.py`, `layer4_attribute_check.py`, and
`generation_conditioning_prompt_demo.py`) mapped each varṇa pole's **old Sanskrit-label gloss** to one
terse English paraphrase ("one direct-English-paraphrase phrase per canonical lexicon gloss,
parentheticals stripped … coverage engineering only — NOT evidence, NOT ontology"). It filled a fixed
"X moves toward Y, and Z is the resolving principle" template for inspection-only Layer-2/3/4 harnesses.
All of these were explicitly stamped *no model / not scored / not evidence / NO_SIGNAL*.

## Why it was retired

* **Dependency on the old pole schema.** The bridge is keyed by `_canon(state)`, which reads a pole's
  **Sanskrit label** from a `{sanskrit, english}` dict. B1.12 poles are **prose strings**, so `_canon`
  returns the whole gloss and no key matches.
* **Measured 0/66 coverage under B1.12.** Every pole resolves to `[unresolved]`; synthesis collapses to
  a single degenerate payload (`differentiation 8.3%`). See
  `varna_lens/tools/layer2_ablation/` and `varna_lens/mapping/LAYER2_BRIDGE_ABLATION_DECISION_REPORT.md`.
* **No production dependency.** `pse_renderer.py`, `reflect.py`, and the concern bridge never imported
  it; every consumer was an inspection/demo/experiment harness.
* **A four-arm ablation** showed the direct B1.12 payload (Arm A) is fully sufficient (100% coverage,
  fidelity, differentiation) and, if shorter payloads are ever wanted, deterministic compression (Arm C)
  matches it at ~29% of the tokens with **no second ontology** — so the bridge added no independent
  value beyond compress/relabel.

## Replacement

Symbolic state is now produced once by the **canonical Symbolic Profile**
(`varna_lens/symbolic_profile.py::build_symbolic_profile`) directly from the authoritative B1.12
mapping. Downstream consumers (reflection renderer, Arm D / conditioning, future evaluators) read the
profile's verbatim B1.12 pole `text` (optionally via the deterministic compression in
`varna_lens/tools/layer2_ablation/ablation.py`). No Sanskrit-label bridge, no authored paraphrase
vocabulary.

## Contents & reproducibility

* `layer2_bridge_vocab.json` — the frozen 64-entry paraphrase vocabulary (moved here from `varna_lens/`).
* The harness modules remain in `varna_lens/` marked `RETIRED (research-only)`; they still load this
  archived vocab (with an inline fallback) so prior experiments run unchanged.
* The legacy Layer-2/3/4 tests remain in `varna_lens/` as **historical regressions**: they skip under
  the active B1.12 mapping and run their original assertions only under the old-lexicon fixture, e.g.

  ```bash
  VARNA_LENS_MAPPING=$PWD/varna_lens/lexicon_authoritative.json \
      python3 varna_lens/test_sample_text_rule_harness.py
  ```

Historical evidence is retained, not deleted.
