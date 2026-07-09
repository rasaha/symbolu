# B1.8 — Deterministic KCPR Layer-1 Resolver Rulebook (candidate; docs-only)

**Status:** the **frozen candidate resolver rulebook** for the B1.8 context-resolved KCPR Layer-1 probe
(preregistered at `B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md`, commit `7d149a9`). **Docs-only.** No code, no
scaffold, no generation, no evidence freeze, no judging, no `GENUTILITY_*`.

**Readiness label: `B1_8_KCPR_RESOLVER_RULEBOOK_READY`.** All policy choices below are **decided and firm** so
this document can be hash-frozen as-is before any generation.

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. No ontology, no Sanskrit
privilege, no semantic-truth claim. **Structure, not validated meaning.**

---

## 1. Purpose

Define the **single, deterministic, frozen** function that performs KCPR Layer-1 for B1.8:
`resolve(target, context) → one selected pole per varṇa` (not both). It is a **researcher-authored candidate**
(the theory supplies no resolution procedure — `KCPR_EXPANSION_NOT_FOUND`); all B1.8 results are therefore
**conditional on this rulebook** (§12), which is why the scrambled-resolved control is mandatory. This rulebook
is the artifact that, once frozen, makes B1.8's `KCPR_SELECTED_POLE` arm reproducible and non-circular.

## 2. Input

The resolver receives, for each `(target, context)` pair, **only** frozen design-time data (no model, no output):

- `target_word` and `item_id`;
- `context_text` — the fixed rich context (§4, §7 of the prereg), frozen before run;
- `context_stratum` — one categorical tag from §4 (assigned at design time, blind to any output);
- `plane_tag` — optional; if plane-first is used (§5) it is **derived deterministically from the stratum**, not
  authored per item;
- the **v2 named-vṛtti table entry per varṇa** in the target's `supported_varna_sequence`
  (`track_g_varna_polarity_table_v2_named_vritti.json`): `named_attribute`, `worldly_binding_distortion`,
  `spiritual_liberating_reading`, `interpretive_gloss`, `spheres`, `coverage`.

The resolver does **not** receive: any generated output, any judge rating, any generator identity, or any
per-item human pole annotation.

## 3. Output

For each varṇa in the supported sequence, the resolver emits exactly one of:

- `selected_pole = worldly_binding_distortion` (verbatim text from the v2 entry), **or**
- `selected_pole = spiritual_liberating_reading` (verbatim text from the v2 entry);

plus, optionally, `selected_plane ∈ {physical, mental, intellectual, spiritual}` (the sphere gloss to emphasize,
§5); plus, when rules cannot resolve, a per-item `REFUSE_AMBIGUOUS` label with a reason code (§8). The generator
prompt (built separately, not here) then shows **only the selected pole's text per varṇa** — never both.

Output is a static table `{item_id → {varṇa → selected_pole (+ plane)}}`, produced and **frozen before
generation**.

## 4. Context strata (allowed set; frozen)

Every B1.8 context is authored under exactly one stratum (categorical; assigned blind to outputs):

1. `concrete_object` — physical use/setting;
2. `psychological_mental` — inner/felt scenario;
3. `ethical_action` — a choice, duty, or action under tension;
4. `spiritual_contemplative` — contemplative/existential setting;
5. `brand_name` — naming/identity scenario;
6. `emotional_nonclinical` — emotionally charged, non-clinical scenario.

Bare valence-neutral stubs (e.g. "A common noun.") are **disallowed** as B1.8 contexts (§7).

## 5. Plane-first rule (USED — Option C structuring Option A)

**Decision: plane-first selection is USED.** `context_stratum → selected_plane` is a fixed, frozen map; the
plane picks which `spheres` gloss the scaffold emphasizes (pole polarity is chosen separately, §6):

| stratum | selected_plane | sphere emphasis |
|---|---|---|
| `concrete_object` | physical | physical/functional |
| `psychological_mental` | mental | mental/affective |
| `ethical_action` | intellectual | intellectual / alignment-with-principle (dharma/action) |
| `spiritual_contemplative` | spiritual | spiritual/contemplative |
| `brand_name` | mental (primary) + physical (secondary) | mixed functional/affective |
| `emotional_nonclinical` | mental | mental/affective |

Plane and pole are **orthogonal**: plane selects *which sphere gloss to foreground*; pole (§6) selects *binding
vs liberating framing*. `brand_name` uses a mixed emphasis but still selects a **single pole** per varṇa via §6.

## 6. Pole-selection rule (deterministic; frozen)

**Decision: a frozen lexical-cue rule over the fixed `context_text`.** No model. No per-item human pole choice.

Two frozen cue sets:

- **BINDING cues:** obstacle, distortion, compulsion, conflict, fear, fixation, avoidance, limitation, clinging,
  cling, stuck, rigid, over-holding, withdrawal, withdraw, escape, escapism, blocked, loss, grip, trapped,
  inert, defeat.
- **LIBERATING cues:** aspiration, aspire, integration, integrate, clarity, dharma, release, releasing,
  reflection, reflective, healing, contemplation, contemplative, alignment, align, sustaining, sustain, peace,
  letting go, let go, movement toward, subtlety, flow.

**Rule (applied to the whole context, same selection used for every varṇa of that item):**
1. Count whole-word BINDING-cue matches (`b`) and LIBERATING-cue matches (`l`) in `context_text` (case-insensitive).
2. If `b > l` → `selected_pole = worldly_binding_distortion`.
3. If `l > b` → `selected_pole = spiritual_liberating_reading`.
4. If `b == l` (including `0 == 0`) → **`REFUSE_AMBIGUOUS`** (§8) — never default, never both poles, never LLM.

Pole polarity is thus a function of the **context**, identical across the real and scrambled arms (§10); only
the varṇa *content* differs between them. Per-varṇa refinement (a varṇa whose own polarity axis contradicts the
context) is **not** used in this candidate — kept deliberately simple and auditable; noted as a possible
future variant requiring a new freeze.

## 7. Neutral-context policy (firm recommendation)

**Recommendation: EXCLUDE neutral contexts from B1.8.** Every B1.8 context must carry a determinate valence
direction by design; valence-neutral stubs are disallowed (§4). If, despite this, the §6 rule yields
`b == l`, the item is **`REFUSE_AMBIGUOUS`** and is **excluded from the resolved arms** — it is **not**
defaulted to a pole, **not** shown both poles, and **not** handed to an LLM to resolve.

Rationale: B1.8 exists precisely to test *context-conditioned* resolution. A neutral context provides no cue, so
"resolution" over it is undefined and would silently collapse back to the B1.6-v2 ambiguity (both poles / LLM
resolves) this probe is designed to eliminate. Excluding neutral contexts keeps the manipulated variable clean.
(The `SYMBOLU_UNRESOLVED_DUAL` control arm still exists to represent the both-poles condition, so nothing is
lost — it is measured as a *named arm*, not smuggled in as a default.)

## 8. Ambiguity / refusal policy

The resolver emits `REFUSE_AMBIGUOUS` with a reason code, and the item is **excluded** from the resolved arms
(logged, never defaulted, never silently dropped from the record), when:

- `AMBIGUOUS_MIXED_CUES` — `b == l > 0` (context frames both binding and liberating);
- `AMBIGUOUS_NO_DIRECTION` — `b == l == 0` (no cue; e.g. a neutral stub that slipped through §7);
- `UNSUPPORTED_VARNA` — a varṇa is not `SOURCE_SUPPORTED` in the v2 table / is `UNSUPPORTED_NO_VARNA`;
- `INSUFFICIENT_COVERAGE` — the target's supported-varṇa coverage falls below the frozen threshold set in the
  B1.8 target design;
- `TARGET_SEMANTICALLY_OVERLOADED` — flagged at design time when the target's dictionary meaning would dominate
  any reading regardless of context (excluded to avoid confounding).

Refusals are reported in the run manifest; a refused item is absent from **all** resolved arms equally (so no
arm gains from selective refusal).

## 9. No LLM resolver (hard constraints)

- The **generator LLM must not select poles** — it receives the already-selected pole text and only writes prose.
- The **judge LLM must not select poles** — judges never see poles, arms, or resolver output (§9 of the prereg).
- **No researcher per-target hand selection** of poles, and **no** edits to poles/contexts/rule after seeing any
  output.
- The resolver output table is **produced and hash-frozen before generation**. Violation ⇒
  `B1_8_KCPR_RESOLVER_INVALID_CIRCULARITY`.

## 10. Scrambled-resolved control

The `SCRAMBLED_SELECTED_POLE` arm applies **this identical resolver** to a scrambled varṇa→vṛtti mapping:

- **same** `context_text`, `context_stratum`, `plane_tag`;
- **same** §6 pole-selection rule → therefore the **same pole polarity** (binding vs liberating) is chosen per
  item (pole is context-driven, so it does not change under scrambling);
- **shuffled** varṇa→content: each varṇa's v2 entry is replaced by a **different** varṇa's entry via a seeded
  derangement (`randomization_seed`, frozen before run; no fixed points);
- **same** selected-pole count and output format (one pole text per varṇa).

Thus `KCPR_SELECTED_POLE` and `SCRAMBLED_SELECTED_POLE` differ in **exactly one thing**: whether the selected
pole's text is the target varṇa's authentic content or a random other varṇa's. This is the primary make-or-break
isolation (§10 of the prereg).

## 11. Worked examples (verbatim v2 wording; audit-compliant)

Pole text is quoted **verbatim** from the frozen v2 entries; interpretive glosses are shown **only as tagged
glosses**, never as source (per `B1_6_VA_SA_SOURCE_AUDIT.md`). Illustrative contexts are placeholders for the
frozen B1.8 context set.

**va — binding context.** Context (stratum `ethical_action`): *"He keeps **clinging** to the original plan he
cannot **release**, **stuck** and **over-holding**."* → BINDING cues {clinging, stuck, over-holding} > LIBERATING
{release} ⇒ **`worldly_binding_distortion`**:
> "rigid holding; stuck ensconcement in original stance; over-holding; clinging to holding"
(Audit: binding sense is *holding / ensconcement*, non-moral; **'possession' is removed** — never used.)

**va — liberating context.** Context (stratum `spiritual_contemplative`): *"She **aligns** her choices with what
**sustains**, a quiet **movement toward** what is right."* → LIBERATING cues {align, sustains, movement toward}
⇒ **`spiritual_liberating_reading`**:
> "dharma; sustaining flow; alignment with sustaining principle; movement toward subtlety"
(Audit: **'order / right order'** may appear only as a **tagged interpretive gloss** of dharma / rightness /
sustaining principle — *not* as source text.)

**sa — binding context.** Context (stratum `emotional_nonclinical`): *"He **withdraws** early, an **escapist**
**avoidance** of the work, going **inert**."* → BINDING cues {withdraw, escapism, avoidance, inert} ⇒
**`worldly_binding_distortion`**:
> "escapism; premature static withdrawal; inert / static withdrawal"

**sa — liberating context.** Context (stratum `spiritual_contemplative`): *"A clear, **peaceful** **letting go**;
**clarity** and **release**."* → LIBERATING cues {peace, letting go, clarity, release} ⇒
**`spiritual_liberating_reading`**:
> "sattva; clarity; peace; release; mokṣa; unqualified liberation"
(Audit: **'goodness / purity'** may appear only as a **tagged interpretive gloss** of sattva-guṇa — *not* as
source text.)

## 12. Non-circularity statement

This resolver reduces circularity but does **not** eliminate it, and must not be over-read:

- It is **researcher-authored** — the theory supplies no context→pole procedure, so the strata map (§5), cue
  lexicon (§6), thresholds (§8), and contexts (§7) are all candidate choices.
- It is **deterministic and frozen before generation** — no LLM resolves at run time, no post-hoc human pole
  choice (§9). This removes the two acute failure modes (model-knowledge; post-hoc tuning).
- Therefore **any positive B1.8 result is conditional on this specific resolver + context set** — it licenses
  "context-resolved utility *under this rulebook*," never ontology, Sanskrit privilege, or objective varṇa
  meaning.
- The **scrambled-resolved control (§10)** is what tests whether the *specific* varṇa content matters: only if
  `KCPR_SELECTED_POLE > SCRAMBLED_SELECTED_POLE` did the authentic content carry signal beyond "any selection
  under this rule." See also `CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`.

## 13. Compatibility with the B1.8 prereg

Implements §3 (Layer-1 definition), §5 Option A + Option C, §6 controls (supplies the `KCPR_SELECTED_POLE` and
`SCRAMBLED_SELECTED_POLE` arm content), §7 strata/contexts, and §8 no-post-hoc constraints of
`B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md`. Uses the frozen `track_g_varna_polarity_table_v2_named_vritti.json`
and `track_e_varna_sphere_lexicon.json` unchanged; **no B1.6-v2 file is modified.** This rulebook must be
hash-frozen in the B1.8 evidence-freeze declaration (a future, separate operator action) before any generation.

## 14. Readiness label

**`B1_8_KCPR_RESOLVER_RULEBOOK_READY`** — neutral-context policy decided (EXCLUDE, §7), pole-selection rule
decided (frozen lexical-cue count, §6), ambiguity/refusal policy decided (§8), plane-first decided (USED, §5),
scrambled control defined (§10), no-LLM/no-post-hoc constraints stated (§9). Failure labels reserved for the
execution phase: `B1_8_KCPR_RESOLVER_BLOCKED_NEUTRAL_CONTEXT`, `B1_8_KCPR_RESOLVER_BLOCKED_AMBIGUITY_POLICY`,
`B1_8_KCPR_RESOLVER_INVALID_CIRCULARITY`, `B1_8_KCPR_RESOLVER_INVALID_LEAKAGE`.

## 15. Guardrails

- **No code built. No scaffold created. No generation run. No evidence freeze. No judging. No `GENUTILITY_*`.**
- No semantic-truth claim; no ontology; no Sanskrit privilege; no varṇa meaning invented; no target tuning.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked.
- **Structure, not validated meaning.**

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_8_KCPR_LAYER1_RESOLVER_RULEBOOK.md` (docs-only).
  **No B1.6-v2 file modified; no code/scaffold created.**
- **Commit hash:** recorded on the commit below.
- **Readiness label:** `B1_8_KCPR_RESOLVER_RULEBOOK_READY`.
- **Chosen neutral-context policy:** **EXCLUDE** — B1.8 contexts must carry a determinate valence direction;
  neutral/ambiguous items are `REFUSE_AMBIGUOUS` and excluded from resolved arms (never defaulted, never both
  poles, never LLM-resolved).
- **Chosen pole-selection rule:** deterministic **frozen lexical-cue count** over the fixed context text
  (BINDING vs LIBERATING cue sets); `b>l`→binding, `l>b`→liberating, tie→refuse; same polarity applied to real
  and scrambled arms.
- **va/sa examples follow the audit?** **Yes** — verbatim v2 pole text; 'possession' not used for va;
  'order/right order' and 'goodness/purity' shown only as tagged interpretive glosses (dharma; sattva).
- **No code / scaffold / generation / evidence freeze / judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.8 deterministic KCPR Layer-1 resolver rulebook drafted docs-only. No code built. No scaffold created. No
generation run. No evidence freeze. No judging. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM.
Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
