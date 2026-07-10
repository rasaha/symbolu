# B1.8 — Three-Layer Data Wiring, with Concrete Frozen Samples (docs-only)

**Status:** explanatory walkthrough of how the **actual frozen B1.8 data** flows across the three layers. Every
field name and value below was read directly from the committed frozen files (not from memory). **No code built,
no frozen data modified, no generation, no evidence freeze, no judging, no `GENUTILITY_*`.**

**Readiness label: `B1_8_DATA_WIRING_EXPLAINED`.**
**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. Structure, not validated meaning.

Sources audited: `frozen/b1_8_context_resolved_targets_scaffolds.json`,
`frozen/b1_8_context_resolved_randomized_control_manifest.json`,
`frozen/b1_8_context_resolved_scaffold_manifest.json`, `track_g_varna_polarity_table_v2_named_vritti.json`.

---

## 1. Layer 0 — Source / varṇa content (inert)

File: `track_g_varna_polarity_table_v2_named_vritti.json`, key `varnas` (25 source-supported varṇas). **Actual**
per-varṇa fields: `named_attribute`, `worldly_binding_distortion`, `spiritual_liberating_reading`,
`interpretive_gloss`, `varna`, `root_source`, `atom_id`, `source_binding_gloss_verbatim`, `spheres`
(physical/mental/intellectual/spiritual), `source_path`, `source_hash`, `leak_risk`, `coverage`, `notes`.

Three distinct text kinds (real examples):

| varṇa | `named_attribute` (root) | `worldly_binding_distortion` | `spiritual_liberating_reading` |
|---|---|---|---|
| `sa` | mokṣa; sattva-guṇa; clarity; peace; release | escapism; premature static withdrawal; inert | sattva; clarity; peace; release; mokṣa; unqualified liberation |
| `va` | dharma; holding (dhṛ='to hold'); jala-tattva; Varuṇa | rigid holding; stuck ensconcement; over-holding; clinging | dharma; sustaining flow; alignment with sustaining principle; movement toward subtlety |
| `ra` | agni-tattva, prana-shakti, vitality; sarvanasha | defeatist annihilation-thought ('everything is gone…') | fire of life-force; can become defeatism or spiritual energy |

**Layer 0 stores *both* poles for every varṇa and chooses neither.** It is inert data with source hashes. (Audit
note: `sa`'s 'goodness/purity' and `va`'s 'order/right order' live only in `interpretive_gloss` as *tagged*
glosses — they are **not** in the pole text; the frozen pole text above is what gets used.)

## 2. Layer 1 — Context resolver (deterministic; pre-generation)

Rule: `B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md`. In the frozen scaffold each target carries the **actual** fields:
`TARGET_TEXT`, `CONTEXT_TEXT`, `STRATUM`, `VARNA_SEQUENCE`, `SELECTED_PLANE`, `RESOLVER_CUE_COUNTS`
(`{binding, liberating, binding_hits[], liberating_hits[]}`), `RESOLVER_DECISION`, `REFUSAL_STATUS`.

- **cue counts:** whole-word BINDING vs LIBERATING lexeme hits in `CONTEXT_TEXT`.
- **decision:** `binding > liberating` → `worldly_binding_distortion`; `liberating > binding` →
  `spiritual_liberating_reading`; tie → `REFUSE_AMBIGUOUS` (excluded).
- **selected plane:** from `STRATUM` (physical/mental/intellectual/spiritual) — picks which `spheres` gloss to
  foreground; orthogonal to pole.
- **applied per item:** one selected pole is used for *all* varṇas of that item.

**Context is fixed and frozen; the LLM does not choose the pole.** `RESOLVER_DECISION` is a pure function of the
frozen text + frozen lexicon, computed and hash-frozen before any model runs.

## 3. Layer 2 — Generation scaffold / arm rendering

Each target carries `SELECTED_POLE_PROFILE_TABLE` and `KCPR_LAYER1_SELECTED_FRAME` (per varṇa: `selected_pole`,
`text`, `named_attribute`, `plane`, `plane_gloss` — **one pole only**) and, retained on the same item, an
`UNRESOLVED_BOTH_POLES_FRAME` (both poles, for the B1.6-style control). The scrambled control lives in the
randomized file with `SCRAMBLED_SELECTED_POLE_FRAME` (+ `content_from_varna` per varṇa) and
`varna_content_map`. **`KCPR_SELECTED_POLE`** renders the authentic frame; **`SCRAMBLED_SELECTED_POLE`** renders
the deranged frame — same everything else. Resolver metadata (cue counts, pole labels, arm names, varṇa names)
is hidden from judges (§10).

---

## Sample A — `grief` (b18-03) · BINDING · plane `mental`

**Layer 0** — varṇas `["ga","ra"]`; both poles at source:
- `ga`: bind = "effort / striving" · lib = "effort as path to mundane development and spiritual…"
- `ra`: bind = "defeatist annihilation-thought ('everything is gone, I am undone')" · lib = "fire of life-force; can become defeatism or spiritual energy"

**Layer 1** — `CONTEXT_TEXT` = *"In his grief he stays clinging to what was, trapped by a loss he cannot
release."* · `STRATUM` = psychological_mental · `RESOLVER_CUE_COUNTS` = binding **3** {clinging, loss, trapped} /
liberating **1** {release} · `SELECTED_PLANE` = mental · `RESOLVER_DECISION` = **`worldly_binding_distortion`** ·
`REFUSAL_STATUS` = RESOLVED.

**Layer 2** — `KCPR_LAYER1_SELECTED_FRAME` (what `KCPR_SELECTED_POLE` receives, one pole each):
- `ga`: "effort / striving"  · `ra`: "defeatist annihilation-thought ('everything is gone, I am undone')"

`SCRAMBLED_SELECTED_POLE` (`varna_content_map` = `{ga→da, ra→ya}`; same binding polarity, content swapped):
- `ga ← da`: "peevishness / irritability"  · `ra ← ya`: "lack of confidence / wavering movement"

Judges see only: target `grief`, the context sentence, and the finished reading — **never** the pole, arm, cue
counts, or varṇa names.

## Sample B — `justice` (b18-05) · LIBERATING · plane `intellectual` · contains `sa`

**Layer 0** — varṇas `["ja","sa","ta","ka"]`. `sa` source: bind = "escapism; premature static withdrawal;
inert…" · lib = "sattva; clarity; peace; release; mokṣa; unqualified liberation".

**Layer 1** — `CONTEXT_TEXT` = *"She pursued justice with clarity, in alignment with a sustaining fairness, a
contemplative movement toward what is right."* · binding **0** / liberating **5** {clarity, contemplative,
alignment, sustaining, movement toward} · `SELECTED_PLANE` = intellectual · decision =
**`spiritual_liberating_reading`**.

**Layer 2** — `KCPR_SELECTED_POLE` frame (authentic liberating text):
- `ja`: "identity bondage; false doership" · **`sa`: "sattva; clarity; peace; release; mokṣa; unqualified
  liberation"** · `ta`: "spiritual inertness that discipline seeks to liberate from" · `ka`: "expressed
  universe, creation-field, emergence into manifestation"

`SCRAMBLED_SELECTED_POLE` (`{ja→na, sa→nya, ta→tha, ka→ssa}`; same liberating polarity, swapped content):
- `ja←na`: "bondage through infatuation…" · **`sa←nya`: "spiritual falseness; split between outer virtue and
  inner conduct"** · `ta←tha`: "depressive contraction; needs upward movement" · `ka←ssa`: "tamas-bound kama;
  physical / worldly longing"

Note the isolation: `sa`'s slot changes from `sa`'s own liberating reading to `nya`'s — **only the content
identity moves**; the pole stays liberating and the context is unchanged.

## Sample C — `wonder` (b18-11) · LIBERATING · plane `mental` · contains `va`

**Layer 0** — varṇas `["va","na","da","ra"]`. `va` source: bind = "rigid holding; stuck ensconcement…" · lib =
"dharma; sustaining flow; alignment with sustaining principle; movement toward subtlety".

**Layer 1** — `CONTEXT_TEXT` = *"The child's wonder opened into reflection and a bright clarity, a peace that let
the moment flow."* · binding **0** / liberating **4** {clarity, reflection, peace, flow} · `SELECTED_PLANE` =
mental · decision = **`spiritual_liberating_reading`**.

**Layer 2** — `KCPR_SELECTED_POLE` frame:
- **`va`: "dharma; sustaining flow; alignment with sustaining principle; movement toward subtlety"** · `na`:
  "bondage through infatuation; indifference and spiritual ideation free it" · `da`: "small egoic contraction;
  patience softens it" · `ra`: "fire of life-force; can become defeatism or spiritual energy"

`SCRAMBLED_SELECTED_POLE` (`{va→nga, na→dha, da→sa, ra→ya}`):
- **`va←nga`: "egoic obstruction; humility is its spiritual correction"** · `na←dha`: "bondage through endless
  acquisition…" · `da←sa`: "sattva; clarity; peace; release; mokṣa; unqualified liberation" · `ra←ya`: "unstable
  faith; needs trust and inner steadiness"

## 4. Real vs scrambled — the isolation (worked on `grief`)

| held constant | `KCPR_SELECTED_POLE` | `SCRAMBLED_SELECTED_POLE` |
|---|---|---|
| target | grief | grief |
| context | "…clinging…trapped…loss…release." | same |
| cue-count decision | binding (3 vs 1) | same |
| selected plane | mental | mental |
| selected pole polarity | worldly_binding_distortion | worldly_binding_distortion |
| **varṇa content** | `ga`="effort/striving", `ra`="defeatist annihilation…" | `ga←da`="peevishness/irritability", `ra←ya`="lack of confidence…" |

Everything is identical **except** whether the selected-pole text is the target varṇa's authentic content or a
deranged other varṇa's. Therefore a quality difference between these two arms **cannot** be attributed to:
- **context usefulness** — same context;
- **generic structure** — same one-facet-per-varṇa template;
- **selecting one pole** — same pole polarity chosen the same way;
- **LLM implicit resolution** — the pole was fixed before the model saw anything.

The only remaining explanation is the **authentic varṇa content** itself. That is the isolation B1.6-v2 could
not achieve.

## 5. Where context enters

- Context is **fixed in the frozen target scaffold** (`CONTEXT_TEXT`), authored blind to any output.
- Context is **not chosen by the LLM**.
- Context **determines the pole** through the frozen cue-count rule (`RESOLVER_CUE_COUNTS` → `RESOLVER_DECISION`).
- The generator receives an **already-resolved selected-pole scaffold** (one pole per varṇa) plus the target and
  context — never both poles (except in the explicitly-named unresolved control arms).
- Judges **do not see resolver metadata** (cue counts, decision, plane, poles, arms).

## 6. Utility logic

B1.8 is a **utility test**: it asks whether the selected-pole scaffold **raises blind-rated generation quality**
(coherence, specificity, usefulness, non-genericity, minus overclaim/hallucination). A positive result would say
the scaffold is a useful prompt **under this frozen resolver/context package**. It does **not** prove ontology,
semantic truth, that varṇas objectively contain meaning, or any Sanskrit privilege — utility of a prompt is
orthogonal to the truth of its content, and the resolver + contexts are researcher-authored candidates.

## 7. Contrast with B1.6-v2

- **B1.6-v2:** showed *both* poles per varṇa with a stub context and let the **LLM resolve implicitly** — so it
  tested only the *unresolved dump* (its null applies there).
- **B1.8:** selects **one** pole per varṇa from a **frozen rich context** via a deterministic rule **before**
  generation, and adds the scrambled-selected control.
- Therefore B1.8 is a **stronger test of the actual KCPR Layer-1 mechanism** (context → pole → generation).
- **But** B1.8 remains **conditional on the frozen, researcher-authored resolver + context set**; only the
  scrambled-selected contrast tests whether the *specific* varṇa content matters.

## 8. What is NOT wired yet

- B1.8 **generation driver:** **not built.**
- B1.8 **evidence-freeze gate:** **not built** (fields specified in the runbook only).
- B1.8 **RunPod commands:** **do not exist.**
- B1.8 **judging:** **not run** (the B1.6/B1.7 panel is reusable, but nothing has run).
- B1.8 **aggregation:** **not run.**

## 9. Validation status (from the frozen data)

- **Targets:** 12. **Strata coverage:** all 6 × 2 (concrete_object, psychological_mental, ethical_action,
  spiritual_contemplative, brand_name, emotional_nonclinical).
- **Selections:** 6 binding / 6 liberating. **Tie/refused contexts:** 0.
- **Scrambled control deranged:** yes — `derangement_no_fixed_points: true`, seed `20260709`.
- **No B1.6-v2 file modified;** **no generation outputs exist** (`run_out/` carries no B1.8 package).

## 10. Leakage / blinding

- **Generator may see (by arm):** target; context; and — for the varṇa arms — the selected-pole scaffold (or,
  for baselines, only target + context / generic-structure / semantic instruction).
- **Judges must NOT see:** arm names; selected-pole metadata; resolver cue counts; generator IDs; the
  `varna_content_map` / hidden mappings; or any Symbol-U / varṇa / scaffold labels. **Judges may see:** target,
  context, and the finished output. Enforcement reuses the shared whole-word leak matcher + Sanskrit-term filter;
  a leaking output is dropped (recorded), never the run.

## 11. Readiness label

**`B1_8_DATA_WIRING_EXPLAINED`** — Layer 0/1/2 wiring documented against real frozen fields and three concrete
samples; no field mismatch, no sample-lookup failure, no leakage introduced.

## 12. Guardrails

No code built; no frozen data modified; no generation run; no evidence freeze; no judging; no `GENUTILITY_*`; no
semantic-truth claim; no ontology; no Sanskrit privilege. **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b
blocked; Track B blocked. Structure, not validated meaning.

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_8_DATA_WIRING_THREE_LAYER_EXPLANATION.md`
  (docs-only). **No frozen data modified; no code built.**
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_8_DATA_WIRING_EXPLAINED`.
- **Sample targets documented:** `grief` (b18-03, binding), `justice` (b18-05, liberating, contains `sa`),
  `wonder` (b18-11, liberating, contains `va`) — plus the real-vs-scrambled isolation worked on `grief`.
- **Layer 0/1/2 wiring clear?** Yes — explained against actual field names (`RESOLVER_CUE_COUNTS`,
  `RESOLVER_DECISION`, `KCPR_LAYER1_SELECTED_FRAME`, `SCRAMBLED_SELECTED_POLE_FRAME`, `varna_content_map`).
- **B1.8 generation wired yet?** No — driver, freeze gate, RunPod commands, judging, and aggregation are all
  unbuilt/unrun.
- **No code / frozen-data / generation / evidence-freeze / judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 three-layer data wiring documented docs-only. No code built. No frozen data modified. No generation run. No
evidence freeze. No judging. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b
remains blocked. Track B remains blocked. Structure, not validated meaning.
