# B1.3 — v3-Authoritative Rebuild (source-integrity correction)

## 1. Scope

Source-integrity rebuild only. The lexicon-source audit found B1.3 v2 was built on a **FALLBACK_QUALIFIED**
bridge pool (derived from `b1_1_experimental_contrastive_lexicon_draft.json`), not the authoritative lexicon.
This rebuilds the study on `varna_lens/lexicon_authoritative_varna.json`. **No EVIDENCE_FREEZE · no run · no
scoring · no model/judge/scorer call · authoritative lexicon not edited · v2 preserved · no prior negative
reinterpreted as positive · Track B remains BLOCKED · no ONTOLOGICAL_SIGNAL · no Sanskrit privilege. This is a
source-integrity rebuild, not a rescue.** **Structure, not validated meaning.**

## 2. Authoritative bridge pool

`b1_3_authoritative_varna_bridge_pool.json` — built **directly** from the authoritative lexicon:
- all **34** consonant keys preserved;
- **pole direction preserved by construction** (`binding_state`→`binding_bridge`,
  `liberating_state`→`liberating_bridge`) → **no flips**;
- local rewrite = authoritative `english_sharpened` with **Sanskrit-label parentheticals stripped** for the
  experimental packet; source englishes retained as provenance;
- provenance: `source_lexicon: varna_lens/lexicon_authoritative_varna.json` · `source_status: AUTHORITATIVE` ·
  `bridge_status: source_preserved_counter_rewritten` · `not_validated_meaning: true` ·
  `not_ontological_evidence: true`.

## 3. Regenerated v3 stimuli

`b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl` — **371 records = 53 objects × 7
comparisons**, same deterministic pipeline as v2 (same 53-object set, same controls near/mid/far deranged /
scrambled / random / neutral / semantic baseline, same balancing, same global register polish), only the
**bridge pool source** swapped to authoritative. Seed `b1_3_concrete_object_stimgen_v3_authoritative`. v1/v2
**not overwritten**.

The source correction changes the varṇa-derived tags (e.g. `knife`: authoritative `envy, fear, others,
release` vs v2 `sting, flight, spell, stands`; the 5 drifted varṇas `ca/va/ha/ra/sa` now read from the
authoritative source). Design, controls, balancing, and audit outcomes are unchanged.

## 4. Re-audit (v3) — all PASS

**Mechanical** (`…style_audit_report_v3_authoritative.json/.md`): style-parity · style-tell **0.529 ≤ 0.55** ·
denotation-leakage · quality-parity · semantic-baseline · forbidden-token (0 Sanskrit, 0 over-band) ·
duplicate-tag · tag-length parity — all PASS → `V3_AUTHORITATIVE_AUDIT_PASS`.

**Source/provenance** (`b1_3_v3_authoritative_source_audit.json`), all PASS:
- all **34** keys covered; **0 pole flips** (provenance traces each bridge to the authoritative pole);
- **no construct drift beyond documented local paraphrase** (parenthetical strip only);
- **every object routes through authoritative-sourced entries** (53/53);
- **controls present** for every object (7/7);
- **no leakage**; **no target-label/arm-label exposure** in options;
- judge-facing vs answer fields separable (**blinding supported**); answer fields kept for scorer only;
- **no four-sphere integration** (the track_e four-sphere file is not used);
→ `V3_AUTHORITATIVE_SOURCE_AUDIT_PASS`.

## 5. Tests / validation

Deterministic build + audit checks run (`audit_v3.py`): 12 provenance/structure checks + 8 mechanical audits,
all green. Confirmed: **v2 preserved** (only new `*_v3_authoritative*` files created); **v3 generated
separately**; **authoritative source used**; **no scoring**; **no model call**; **no evidence freeze**.

## 6. Freeze review

See `B1_3_CONCRETE_OBJECT_LLM_FREEZE_REVIEW_V3_AUTHORITATIVE.md` +
`b1_3_concrete_object_llm_freeze_review_manifest_v3_authoritative.json` (16 active artifacts hash-bound).
Decision: `FREEZE_REVIEW_V3_AUTHORITATIVE_READY_AWAITING_OPERATOR_CONFIRMATION` (freeze **not** declared here).

## 7. Honest note (no rescue)

Pole direction was already intact in v2, so this rebuild is **unlikely to change the study's outcome** — the
semantic baseline still names object-function directly and the prior stays low. The rebuild is about using the
**correct authoritative source**, and it must be run whichever way the result lands.

## 8. Final status block

```
document:                    B1.3 v3-AUTHORITATIVE REBUILD (source-integrity correction)
authoritative bridge pool:   b1_3_authoritative_varna_bridge_pool.json (34 keys, 0 flips, AUTHORITATIVE)
v3 stimuli:                  371 records / 53 objects / 7 comparisons (authoritative-sourced)
mechanical audit:            V3_AUTHORITATIVE_AUDIT_PASS (style-tell 0.529; 0 Sanskrit; 0 over-band)
source/provenance audit:     V3_AUTHORITATIVE_SOURCE_AUDIT_PASS (34 keys, 0 flips, 53/53 route, controls present)
v2 preserved:                YES (only new *_v3_authoritative* files)
authoritative lexicon edited: NO
ran model / scorer:          NO
EVIDENCE_FREEZE:             NOT declared
freeze review:               FREEZE_REVIEW_V3_AUTHORITATIVE_READY_AWAITING_OPERATOR_CONFIRMATION
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL / MAPPING_FIDELITY_SIGNAL / ONTOLOGICAL_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**B1.3 v3-authoritative rebuild completed as a source-integrity correction only. No evidence freeze declared.
Nothing run or scored. Track B remains blocked. Structure, not validated meaning.**
