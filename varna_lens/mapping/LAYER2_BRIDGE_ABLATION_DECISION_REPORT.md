# Layer-2 Synthesis Bridge — Ablation & Architecture Decision

## 1. Executive recommendation

**RETIRE.** The Layer-2 synthesis bridge (`layer2_bridge_vocab.json` + `synthesize`/`_bridge`/`_canon`)
should be retired as a synthesis mechanism. A bounded four-arm ablation over 12 frozen inputs shows the
legacy bridge is **strictly dominated on every metric** (0% coverage, 0% fidelity, 8.3% differentiation
— it emits a single `[unresolved]` payload for every word), while the **direct B1.12 vṛtti payload
(Arm A) is fully sufficient** (100% coverage, 100% fidelity, 100% differentiation, 0 unsupported
concepts). The bridge's own `_meta` states its only function is "one direct-English-paraphrase phrase
per canonical lexicon gloss" — i.e. compressing/relabeling text the authoritative source already
contains. That function is (a) needed by **no** production or scored runtime path, and (b) fully and
better served, if verbosity is ever a concern, by **deterministic compression (Arm C)** — 100%
fidelity at ~3.4× fewer tokens with **no second ontology** and **0 invented labels**. Retiring the
bridge removes a stale 64-entry authored vocabulary (keyed to the pre-B1.12 schema, currently 0/66) and
its maintenance/migration burden. The frozen vocab and its harness are **retained as clearly-marked
research-only artifacts** so prior NO_SIGNAL experiments remain reproducible; deterministic compression
is offered as an **optional, no-ontology** transform for any future consumer that finds the direct
payload too verbose. A rebuilt stable-ID bridge is **not justified** (Phase 5).

---

## 2. Consumer inventory

| Consumer | File | Runtime status | Depends on bridge? | Recommended action |
|---|---|---|---|---|
| PSE renderer | `varna_lens/pse_renderer.py` | **production runtime** | **No** (its `layer2_trajectory`/`layer3_reflection` are unrelated own-fields) | No change |
| PSE reflection tool | `varna_lens/reflect.py` | production runtime | **No** | No change |
| Concern bridge | `experiments/.../symbol_u_bridge/bridge_core.py` | production runtime | **No** | No change |
| Layer-2 sample-text renderer | `varna_lens/sample_text_rule_harness.py` | evaluation harness (inspection-only, "not scored, not evidence") | **Yes** (`synthesize`/`_bridge`/`_canon`/`BRIDGE`) | Retire bridge role; retain module as research-only |
| Layer-3 dictionary bridge | `varna_lens/layer3_dictionary_bridge.py` | evaluation harness (inspection-only, NO_SIGNAL) | Yes (reads Layer-2 synthesis) | Retain as research-only |
| Layer-4 attribute check | `varna_lens/layer4_attribute_check.py` | evaluation harness (inspection-only, NO_SIGNAL) | Yes (`_reconstruct` mirrors synthesize via `_bridge`) | Retain as research-only |
| Generation-conditioning demo | `varna_lens/generation_conditioning_prompt_demo.py` | experimental demo (NO MODEL, informed-negative: Track F CORRECTNESS_DEGRADED) | Yes (`H.synthesize`/`H.BRIDGE`) | Retain as research-only |
| B1 conditioning driver | `experiments/.../b1_real_conditioning.py` | experimental driver (NO MODEL, NO SCORING) | Yes (imports harness arms) | Retain as research-only |
| Layer-2/3/4 tests (6 files) | `varna_lens/test_*.py` | test harness | Yes | See §8 |
| `layer2_bridge_vocab.json` | `varna_lens/layer2_bridge_vocab.json` | frozen data (64 entries) | — | Freeze as research-only artifact; not runtime |

**No production or scored runtime path depends on the bridge.** Every dependent is an
inspection/demo/experiment component, each self-stamped "not scored, not evidence."

---

## 3. Arm comparison (12-word corpus; GENERATED — `tools/layer2_ablation/`, deterministic, no model)

| Metric | Arm A Direct | Arm B Legacy Bridge | Arm C Compression | Arm D None |
|---|---|---|---|---|
| Coverage % (mean poles represented) | **100.0** | 0.0 | **100.0** | 0.0 |
| Unresolved poles (total) | 0 | **34** | 0 | — |
| Fidelity: leading-concept retained % | **100.0** | 0.0 | **100.0** | 0.0 |
| Unsupported concepts introduced | 0 | 0 | **0** | 0 |
| Binding/liberating distinct (of 12) | 12 | **0** | 12 | 0 |
| Honesty: decode-claim tokens | 1* | 0 | **0** | 0 |
| Semantic additions | 0 | 0 | 0 | 0 |
| Differentiation % (distinct payloads) | **100.0** | **8.3** | **100.0** | 8.3 |
| Payload chars (mean) | 452 | 84 | 133 | 0 |
| Est. tokens (mean) | 114 | 21 | **33** | 0 |

\* The one Arm-A "decode" token is the ordinary English verb *means* inside the śānti source prose
("…rajasic energy… that means…"), **not** a "varṇa means the user" claim; deterministic compression
strips it (Arm C = 0). Neither payload makes a decode-claim — those are governed by the renderer's
honesty filter, which is untouched.

**Reading:** Arm B is dominated by A and C on every axis and collapses differentiation to a single
`[unresolved]` string. Arm A is faithful but verbose (~114 tok). Arm C matches A's coverage, fidelity,
and differentiation at ~29% of the tokens, introduces zero unsupported concepts, and requires no
ontology. Full per-word payloads: `tools/layer2_ablation/ABLATION_METRICS.md`.

---

## 4. Failure analysis — why coverage is 0/66

The collapse is **both a schema mismatch and an obsolete interface**, not a deep architectural
dependency:

* **Schema mismatch (primary).** `synthesize` keys the bridge via `_canon(state)`, which reads the
  pole's **Sanskrit label** from a `{sanskrit, english}` dict. B1.12 poles are **prose strings**, so
  `_canon` returns the whole gloss and the 64 vocab keys (short Sanskrit labels: `āśā`, `krūratā`, …)
  never match. Coverage is 0/66 poles.
* **Obsolete interface.** The vocab's `_meta` pins its source to `lexicon_authoritative.json
  consonants[].{binding_state,liberating_state}` — the retired pre-B1.12 lexicon. It is a frozen index
  over an artifact no longer authoritative.
* **Not a semantic mismatch of the varṇas.** The varṇa identities are unchanged; only the pole *carrier
  shape* and *wording* changed. The bridge could in principle be re-keyed by varṇa — but only by
  reading the old lexicon (forbidden) or re-authoring 64 phrases (forbidden). And the ablation shows
  re-keying would buy nothing: direct payload already covers 100%.

So the 0/66 is a stale-index failure, and the deeper finding is that the index was never necessary — it
only relabeled text the source already carries.

---

## 5. Stable-ID feasibility

A stable-ID bridge is **technically feasible but not justified.**

* **Mechanical assignment:** opaque IDs (`ka.binding.v1`, `ss.liberating.v1`) can be minted
  deterministically from `(varṇa_key, pole, version)` with no interpretation. ✅
* **Identity vs smuggled semantics:** opaque IDs carry identity only; **semantic** IDs (`EGO_RELEASE`,
  `LOVE_SYNTHESIS`) would smuggle an ontology and are explicitly out of bounds. ✅ avoidable.
* **Does downstream synthesis still need authored interpretation?** The ID is only a key. Its
  `display_text` must come from **either** the B1.12 source (then the ID wrapper is redundant with Arm
  A / Arm C) **or** authored text (forbidden). So the ID adds **no synthesis value beyond direct
  lookup**.
* **Value beyond direct lookup:** none for synthesis; at most provenance/versioning — which the
  canonical B1.12 mapping (`mechanical_metadata`, sha-pinned) already provides.
* **Migratable without the old lexicon at runtime?** **No.** Re-keying the old vocab from Sanskrit
  labels to varṇa keys requires the old lexicon's label↔varṇa association. That confirms the legacy
  vocab cannot be carried forward cleanly — and need not be.

**Verdict:** if future work ever needs provenance-stamped display strings, a *thin opaque-ID shim over
the B1.12 source* (`id`, `source_text`, `display_text = compress(source_text)`) is feasible with zero
authored interpretation — but that is a provenance wrapper, **not** a synthesis bridge, and is not
needed today.

---

## 6. Final architecture

**Before (legacy, now 0/66):**
```
varṇa sequence → B1.12 vṛtti (prose strings)
                        │
                        ▼
        layer2_bridge_vocab.json  (keyed by OLD Sanskrit labels)
                        │  0/66 match
                        ▼
                   [unresolved]  → Layer-3 / Layer-4 / conditioning
```

**After (recommended — bridge retired):**
```
varṇa sequence
      │
      ▼
authoritative B1.12 vṛtti payload  (ordered binding/liberating, verbatim, provenance-pinned)
      │
      ├───────────────► direct payload (Arm A)      ── default; full fidelity
      │
      └──(optional, if a consumer needs shorter)────► deterministic compression (Arm C)
                                                        · parenthetical removal
                                                        · first-clause selection
                                                        · punctuation normalization
                                                        · fixed max length
                                                        NO second ontology, NO authored labels
      ▼
downstream reflection / inspection / (future) conditioning

layer2_bridge_vocab.json + Layer-2/3/4 harness  →  RESEARCH-ONLY archive (repro of prior NO_SIGNAL runs)
```

---

## 7. Migration plan (retire)

Bounded and reversible. **Specified here; not executed in this task** beyond adding the ablation harness.

* **Deprecate (do not delete):** `layer2_bridge_vocab.json`, `sample_text_rule_harness.synthesize` /
  `_bridge` / `_canon`, `layer3_dictionary_bridge.py`, `layer4_attribute_check.py`,
  `generation_conditioning_prompt_demo.py`, `experiments/.../b1_real_conditioning.py`. Add a one-line
  `RESEARCH_ONLY / SUPERSEDED_BY: direct B1.12 payload (+ optional deterministic compression)` banner to
  each; keep them runnable for reproduction.
* **Compatibility shim:** none required — no production/scored consumer imports them. New consumers use
  `tools/layer2_ablation/ablation.py` (`pole_stream` + `render_arm("A_direct" | "C_compress")`).
* **Artifact-retention policy:** freeze `layer2_bridge_vocab.json` and the harness at their current
  hashes under a research-only marker; never re-key or re-author them. The B1.12 mapping remains the
  single authoritative varṇa→drive source.
* **Reproducibility:** because nothing is deleted and inputs are frozen, prior Layer-2/3/4 and B1
  dry-run experiments reproduce byte-for-byte under the old lexicon via the existing
  `VARNA_LENS_MAPPING` override; the ablation harness documents the post-B1.12 behavior.

---

## 8. Test disposition (each currently-failing Layer-2/3/4 assertion)

| Test | Failing assertion(s) | What it validates | Disposition |
|---|---|---|---|
| `test_layer2_bridge_vocab` | coverage ≥95%; love/mercy/anger/peace "no longer [unresolved]"; "resolution due to exhaustive coverage" (6) | that the **bridge covers/synthesizes** | **RETIRE** — validates the retired mechanism; move to a research-only regression pinned to the old lexicon |
| `test_layer3_dictionary_bridge` | love Layer-2 synthesis byte-identical (1) | frozen **bridge** synthesis string | **RETAIN AS HISTORICAL REGRESSION** (pin under old-lexicon fixture); the Layer-3 relate logic itself is unaffected |
| `test_layer4_attribute_check` | ≥1 SUPPORTED / ≥1 UNSUPPORTED for love/mercy/anger/peace + love L2 (11) | attribute evidence derived from **bridge** synthesis | **RETIRE** — depends on the retired bridge output |
| `test_sample_text_rule_harness` | love synthesis == required frozen text (1) | frozen **bridge** synthesis string | **RETAIN AS HISTORICAL REGRESSION** (old-lexicon fixture) |
| `test_vowel_positional_polarity` | love L2 synthesis byte-identical (default) (1) | **bridge** synthesis string (incidental to the vowel test) | **REPLACE** — drop the synthesis-string assertion; the vowel-positional pole assertions are valid and should stay (they read poles directly, not the bridge) |
| `test_generation_conditioning_prompt_demo` | conditioning texts differ across arms (1) | arm differentiation via **bridge** | **RETIRE** — arms collapse because the retired bridge yields identical `[unresolved]`; replace with an Arm A/C differentiation check if conditioning is revived |

The passing discipline assertions in these files (no-model, no-scoring, banner, role assignment,
honesty, no-fallback) are correct and **retained**. None of the failing assertions is UPDATE-able to a
non-degenerate golden without either masking `[unresolved]` or re-authoring the bridge — hence retire /
historical-regression, consistent with the RETIRE decision.

---

## 9. Final verdict

1. **Does Layer-2 synthesis add measurable value?** **No.** It is strictly dominated by the direct
   B1.12 payload on coverage, fidelity, and differentiation, and adds only compression/relabeling.
2. **Should `layer2_bridge_vocab.json` remain in runtime?** **No.** It has no production/scored consumer
   and is 0/66 under B1.12. Retain it as a frozen research-only artifact only.
3. **Is a second authored semantic vocabulary justified?** **No.** It duplicates the authoritative
   source, carries maintenance/migration burden, and cannot be migrated without the old lexicon.
4. **Is the direct B1.12 payload sufficient?** **Yes** — 100% coverage, 100% fidelity, 100%
   differentiation, 0 unsupported concepts.
5. **Is deterministic compression beneficial?** **Yes, as an optional utility** — full fidelity at ~29%
   of the tokens with no ontology; useful only if/when a real consumer needs shorter payloads.
6. **What is the smallest justified next implementation?** Mark the bridge and Layer-2/3/4 harness
   `RESEARCH_ONLY` (banners + retention freeze) and expose `render_arm("A_direct")` (with optional
   `"C_compress"`) as the payload path for any future consumer. Do **not** rebuild a bridge, mint
   semantic IDs, re-author the 66 entries, or re-key the vocab.

---

### Evidence discipline honored
Test existence was not treated as architectural value; no component was preserved merely for prior
investment; direct payload is recommended on measured downstream fidelity/cost, not coverage alone;
compression is recommended on measured fidelity, not brevity alone; **no new semantic labels were
created**; the B1.12 mapping, parser normalization, renderer honesty rules, and concern bridge were not
modified.
