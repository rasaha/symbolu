# B1.8 — Context-Resolved KCPR Layer-1 Scaffold Freeze Report (data-only)

**Status:** freeze report for the B1.8 selected-pole scaffold package. **Data/docs only. No generation. No
evidence freeze. No judging. No `GENUTILITY_*`.** The resolver rulebook
(`B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md`, commit `433cf03`) was applied **mechanically** to a preregistered
target/context set; the frozen outputs are the three JSON files below.

**Readiness label: `B1_8_CONTEXT_RESOLVED_SCAFFOLD_READY`.**
**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. Files

- `frozen/b1_8_context_resolved_targets_scaffolds.json` — 12 targets, each with `CONTEXT_TEXT`, `STRATUM`,
  `VARNA_SEQUENCE`, `SELECTED_PLANE`, `RESOLVER_CUE_COUNTS`, `RESOLVER_DECISION`, `REFUSAL_STATUS`,
  `SELECTED_POLE_PROFILE_TABLE`, `KCPR_LAYER1_SELECTED_FRAME`, `UNRESOLVED_BOTH_POLES_FRAME`,
  `REPRESENTATION_VERSION: B1.8_context_resolved_layer1`.
- `frozen/b1_8_context_resolved_randomized_control_manifest.json` — the scrambled selected-pole control
  (seeded derangement; per-item `SCRAMBLED_SELECTED_POLE_FRAME` + `SCRAMBLED_UNRESOLVED_BOTH_POLES_FRAME`).
- `frozen/b1_8_context_resolved_scaffold_manifest.json` — arms, contrasts, seeds, hashes, validation summary,
  readiness label.

## 2. Source inputs

`B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md`, `B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md`,
`track_g_varna_polarity_table_v2_named_vritti.json` (v2 named-vṛtti, 25 varṇas), and the frozen
`frozen/b1_6_phoneme_to_varna_bridge_manifest.json` (varṇa sequences of the 4 added-vocabulary targets were
already decomposed via the A_PRIME_EN decomposer + this bridge in B1.7). **No B1.6-v2 file was modified.**

## 3. Targets and mechanical resolver decisions (12 items, 2 per stratum)

| item | target | stratum | plane | binding cues | liberating cues | decision |
|---|---|---|---|---|---|---|
| b18-01 | bridge | concrete_object | physical | 0 | 4 | liberating |
| b18-02 | lantern | concrete_object | physical | 4 | 0 | binding |
| b18-03 | grief | psychological_mental | mental | 3 | 1 | binding |
| b18-04 | longing | psychological_mental | mental | 0 | 3 | liberating |
| b18-05 | justice | ethical_action | intellectual | 0 | 5 | liberating |
| b18-06 | balance | ethical_action | intellectual | 5 | 0 | binding |
| b18-07 | lotus | spiritual_contemplative | spiritual | 0 | 4 | liberating |
| b18-08 | sacred | spiritual_contemplative | spiritual | 4 | 0 | binding |
| b18-09 | Lumen | brand_name | mental (+physical) | 0 | 3 | liberating |
| b18-10 | Nova | brand_name | mental (+physical) | 4 | 0 | binding |
| b18-11 | wonder | emotional_nonclinical | mental | 0 | 4 | liberating |
| b18-12 | dread | emotional_nonclinical | mental | 4 | 0 | binding |

All decisions are **non-tie** (§9 validation). Pole balance: **6 binding / 6 liberating.** Strata coverage:
all 6 strata × 2. Refused/tie contexts: **0.** No neutral "common noun" stubs (rulebook §7 enforced).

## 4. Selected-pole scaffold (per item)

For each varṇa, `KCPR_LAYER1_SELECTED_FRAME` carries **one** pole (`worldly_binding_distortion` xor
`spiritual_liberating_reading`, verbatim v2 text) plus the stratum-selected plane's sphere gloss — **never both
poles**. The `UNRESOLVED_BOTH_POLES_FRAME` (both poles, B1.6-v2 style) is retained on the same items so the
`UNRESOLVED_BOTH_POLES` control arm draws from the identical source without a separate build.

## 5. Controls (arms)

Declared in the manifest: `KCPR_SELECTED_POLE`, `SCRAMBLED_SELECTED_POLE`, `UNRESOLVED_BOTH_POLES`,
`SCRAMBLED_UNRESOLVED`, `PLAIN_PROMPT_BASELINE`, `GENERIC_STRUCTURED_PROMPT_BASELINE`, `SEMANTIC_LLM_BASELINE`
(the three baselines carry no varṇa content; their prompts derive from `target + context` at generation time).

**Primary control — `SCRAMBLED_SELECTED_POLE`:** same resolver, same contexts, **same selected pole polarity**
(pole is context-driven, so it is identical to the real arm), **shuffled varṇa→vṛtti content** via a seeded
derangement (no fixed points), same sequence length and selected-pole count. Verified example (b18-03 grief,
binding): real `ga→"effort / striving"`, `ra→"defeatist annihilation-thought…"`; scrambled `ga←da→"peevishness
/ irritability"`, `ra←ya→"lack of confidence / wavering movement"` — **only the content identity differs.**
This isolates whether the *specific* varṇa content matters once a selection is made
(`KCPR_SELECTED_POLE` vs `SCRAMBLED_SELECTED_POLE`), the make-or-break contrast of the B1.8 prereg.

## 6. Randomized selected-pole control

Deterministic seed `20260709`; full 25-varṇa derangement recorded (`full_derangement_map`); **no varṇa maps to
itself** (verified); per item the sequence length and selected-pole count match the real arm; content never
revealed to generator or judges (scaffold data only).

## 7. Manifest hashes

| input | sha256 |
|---|---|
| prereg | `87456bfcfbcda2076377fd249c4afbae62a0711a10d41742728ecf85deb84b35` |
| resolver rulebook | `a7c53b8ecf9902671a8a4457e5d4b4912f59f4d756b95078b5393d09212f2f2a` |
| v2 named-vṛtti table | `7bc0b7c8c11c68c80d76ac974657611946e076a839f2a053bce9f639cd4a2694` |
| target scaffolds | `b7925ff2aa19a77276b81043d8a019a1c34e8fa754c7fd264e658440edb25015` |
| randomized control | `eef41543bdfec63acd4dc118cf78ecd7930fe20fbf2e0b8e52e656d148f121f6` |
| phoneme bridge | `d1851c4abd431ead6ded545e1d2a6ecea29b0638d7f1c34394957439342d87ed` |
| prompt/rubric | `080a67086c8631568c53c57a02d76f75a8a25f5ce3f8f8bc4f3205655b0ecc5b` |
| derangement seed | `20260709` |

## 8. Validation (§9 of the build spec)

- Every included item has **non-tie** cue counts ✓
- Every included item has a **selected pole** ✓ and a **selected plane** ✓
- **No neutral context** included ✓
- All reachable varṇas are **`SOURCE_SUPPORTED`** in the v2 table ✓ (`ba,ra,da,ga,la,na,ta,ja,sa,ka,nga,ma,va`)
- Scrambled control is **deranged, no fixed points** ✓
- **No B1.6-v2 file modified** ✓ · **no generation output created** ✓ · **no evidence freeze created** ✓

## 9. Non-circularity note (carried from the rulebook)

Resolution is deterministic and frozen before any generation; no LLM and no post-hoc human choice select poles.
The resolver, cue lexicon, contexts, and seed are researcher-authored candidates the theory does not supply, so
any positive B1.8 result licenses only "context-resolved utility **under this frozen package**." The
`SCRAMBLED_SELECTED_POLE` control is the sole test of whether the *specific* varṇa content carried signal.

## 10. Guardrails

No generation run; no evidence freeze; no judging; no `GENUTILITY_*`; no semantic-truth claim; no ontology; no
Sanskrit privilege. **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b blocked; Track B blocked. Structure,
not validated meaning.

---

## Final report

- **Files created:** `frozen/b1_8_context_resolved_targets_scaffolds.json`,
  `frozen/b1_8_context_resolved_randomized_control_manifest.json`,
  `frozen/b1_8_context_resolved_scaffold_manifest.json`, and this report. **No B1.6-v2 file modified.**
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_8_CONTEXT_RESOLVED_SCAFFOLD_READY`.
- **Number of targets:** 12 (2 per stratum).
- **Strata coverage:** concrete_object, psychological_mental, ethical_action, spiritual_contemplative,
  brand_name, emotional_nonclinical (all 6).
- **Refused/tie contexts:** 0 (expected 0 — ready).
- **Scrambled selected-pole control deranged?** Yes — seed 20260709, no fixed points, verified.
- **No generation / evidence freeze / judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 context-resolved selected-pole scaffold frozen docs/data-only. No generation run. No evidence freeze. No
judging. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B
remains blocked. Structure, not validated meaning.
