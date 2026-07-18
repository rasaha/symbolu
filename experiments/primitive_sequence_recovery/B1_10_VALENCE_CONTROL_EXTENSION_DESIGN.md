# B1.10 — Valence-Control Extension — DESIGN (docs-only)

**Docs-only design. No code, no scaffold, no run, no new experiment number, no B1.11 files, and NO modification of
the original frozen B1.10 pilot artifacts.** This stays inside the **B1.10 pole-context experiment** as a
*control extension*. The scientific question is unchanged:

> **Does the word-specific pole packet explain source-condition fit BEYOND generic positive/negative valence?**

Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth /
ontology / Sanskrit-privilege claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked.
**Structure, not validated meaning.**

## 0. Numbering note (standing decision)

Commit **`393c8d6`** introduced a document under a provisional **B1.11** label. The **standing decision is to keep
this work under B1.10** and **not** continue the B1.11 numbering. This extension supersedes that provisional
framing: the six shortlisted words and the replication concern are carried forward here as **B1.10 — valence-control
extension**, not as a separate experiment. (The `393c8d6` file is left on disk as history; no new B1.11 files are
created, and the design content that matters is restated here.)

## 1. What is preserved (original B1.10 pilot — untouched)

The original 3-word pilot stands as a completed record and is **not modified, overwritten, or re-run**:
- `frozen/b1_10_pole_context_microtest_items.json` (sha `9d70bb86…1832b3bd`) — original 3-word items;
- `frozen/b1_10_EVIDENCE_FREEZE_DECLARED.json` — original evidence-freeze declaration;
- `runs/b1_10_pole_context/b1_10_pole_context_run.json` — original real-run artifact (Opus + Sonnet);
- `B1_10_POLE_CONTEXT_RESULTS.md` — original results record (aggregate margin +9.0).

The extension, **when/if built later**, would live in **new, clearly-labeled files** (e.g.
`frozen/b1_10_valence_control_ext_items.json`, a separate `..._EXT_EVIDENCE_FREEZE_DECLARED.json`, and an
`..._ext_run.json`), leaving all four originals byte-unchanged. **None of that is built here.**

## 2. Words (the six shortlisted; no reuse of the original five)

pride, freedom, patience, courage, control, doubt. (happy / peace / love / longing / devotion remain excluded.)

## 3. The two packet types per word

Each word gets **four** packets across two *types* × two *poles*:

- **Specific packets** — the word's v3 binding/liberating facets (read-only from `frozen/varna_polarity_table_v3.json`
  via `varna_bridge_active`; quoted, not authored). These are the B1.10 packets.
- **Generic valence-matched control packets** — hand-authored, **word-agnostic and varṇa-agnostic** descriptions
  that carry only *negative* or *positive* inner-mood valence, matched in polarity and facet-count/length to the
  specific packet. They deliberately encode **no** other-conditioned-vs-self-grounded content — only bad-feeling vs
  good-feeling — so they isolate the pure valence baseline.

### 3a. Specific packets (v3, read-only)

| word | seq | specific binding (Pb_spec) — abridged | specific liberating (Pl_spec) — abridged |
|---|---|---|---|
| pride | pa,ra,da | ghṛṇā (contempt/revulsion) · sarvanāśa (defeat) · peevish reactivity | upward turn/goodwill · prāṇaśakti (vital resolve) · forbearance |
| freedom | ra,da,ma | sarvanāśa (defeat) · peevishness · praśraya (indulgence to dissolution) | prāṇaśakti · forbearance · disciplined containment |
| patience | pa,ta,na,ka | ghṛṇā · jāḍya (torpor) · moha (fixation) · grasping hope | upward turn · cessation of torpor/awakening · de-fascination · hope without attachment |
| courage | ka,ra,ga | grasping hope · sarvanāśa · restless striving | hope without attachment · prāṇaśakti · will-force |
| control | ka,na,tta,ra,la | grasping · moha · vitarka (over-talk) · sarvanāśa · kruratā (cruelty) | hope without attachment · de-fascination · pramita vāk (measured speech) · prāṇaśakti · compassion |
| doubt | da,ba,ta | peevishness · avajñā (neglect of worth) · jāḍya (torpor) | forbearance · regard for worth · awakening from torpor |

(Full facet text is in the frozen v3 table; the extension would quote it verbatim and hash-pin it, exactly as the
original B1.10 items did.)

### 3b. Generic valence-matched control packets (illustrative drafts — authored blind in the real build)

A fixed **negative pool** and **positive pool**; each word's control packet takes the first *N* items to match its
specific packet's facet count (pride/freedom/courage/doubt → 3; patience → 4; control → 5).

**Generic NEGATIVE pool (valence-only; word/varṇa-agnostic):**
1. a heavy, contracted mood that pulls downward
2. restless dissatisfaction that will not settle
3. a sense of things going wrong and slipping away
4. a tight, grasping unease that does not loosen
5. a sinking, sour heaviness colouring everything

**Generic POSITIVE pool (valence-only; word/varṇa-agnostic):**
1. a light, open mood that lifts upward
2. a settled ease that rests without strain
3. a sense of things going well and holding together
4. a spacious, unforced steadiness
5. a warm, clear lightness colouring everything

These carry **only** negative/positive mood valence — no other/self source-condition, no varṇa content, no
system/pole/Sanskrit terms. They pass the same blinding filter as the specific packets.

## 4. Contexts (same word, two contexts — drafts for review; authored blind in the real build)

Same two-context structure as B1.10 (binding / other-conditioned vs liberating / self-grounded). Drafts:

| word | binding context (Cb) | liberating context (Cl) |
|---|---|---|
| pride | "His pride fed on looking down at those beneath him, and curdled to contempt when outshone." | "Her pride was a quiet self-respect that needed no one's inferiority to stand." |
| freedom | "His freedom was license: he indulged every impulse until nothing held together." | "Her freedom was inner and self-possessed, needing no escape and breaking nothing." |
| patience | "His patience was grudging, a resentful waiting that seethed under a still surface." | "Her patience was alert and willing, resting easily in the pace of things." |
| courage | "His courage was bravado to be seen, driven by dread of looking weak before others." | "Her courage rose quietly from within, acting rightly whether or not anyone watched." |
| control | "His control gripped every detail of her life, tightening whenever she slipped his hold." | "Her control was calm self-mastery: she governed her reactions and let others be free." |
| doubt | "His doubt corroded everything, dismissing worth and sinking him into dull paralysis." | "Her doubt was honest inquiry that weighed things fairly and woke her mind up." |

Per Failure Mode F7, in the real build these are **authored blind to the packets** and pre-registered.

## 5. Cell structure

Per word: **2 contexts × 4 packets = 8 cells** →

| # | context | packet | notation |
|---|---|---|---|
| 1 | Cb | Pb_spec | fit(Pb_spec\|Cb) |
| 2 | Cb | Pl_spec | fit(Pl_spec\|Cb) |
| 3 | Cl | Pl_spec | fit(Pl_spec\|Cl) |
| 4 | Cl | Pb_spec | fit(Pb_spec\|Cl) |
| 5 | Cb | Pb_gen  | fit(Pb_gen\|Cb) |
| 6 | Cb | Pl_gen  | fit(Pl_gen\|Cb) |
| 7 | Cl | Pl_gen  | fit(Pl_gen\|Cl) |
| 8 | Cl | Pb_gen  | fit(Pb_gen\|Cl) |

6 words × 8 = **48 rating cells.** Same judge question, same 0–6 scale, same blinding (pole labels / varṇa tags /
system names / expected-answer markers stripped; **packet *type* — specific vs generic — is also hidden**), same
deterministic seeded shuffle, same compliance-one-liner-for-audit. Judges are blind to which packet is specific and
which is the control.

## 6. Primary statistic

Per word:
```
specific_margin(w)    = [fit(Pb_spec|Cb) - fit(Pl_spec|Cb)] + [fit(Pl_spec|Cl) - fit(Pb_spec|Cl)]   # B1.10 statistic
generic_margin(w)     = [fit(Pb_gen |Cb) - fit(Pl_gen |Cb)] + [fit(Pl_gen |Cl) - fit(Pb_gen |Cl)]   # valence baseline
incremental_margin(w) = specific_margin(w) - generic_margin(w)                                        # PRIMARY
```
Report per-word `specific_margin`, `generic_margin`, `incremental_margin`, all eight cell means, and the **aggregate
mean incremental_margin** over the six words. (Also report the two directional halves of each margin separately, as
in B1.10.)

## 7. Interpretation rules (pre-specified)

- **`specific_margin > 0` alone may be generic valence matching** — it is the B1.10-style result and, on its own,
  does not separate word/varṇa-specific content from "negative packet fits negative context."
- **`incremental_margin > 0` is REQUIRED for packet-specific value beyond generic valence** — the specific packet
  must out-discriminate the valence-matched control.
- **`incremental_margin ≈ 0` means generic valence explains the result** — the varṇa-derived packet adds nothing
  beyond good/bad mood-matching.
- **`incremental_margin < 0` means the specific packet performs WORSE than the generic control** — the varṇa content
  actively hurts discrimination (e.g. off-axis facets confusing the judge).
- Direction + consistency read only (6 words × judges is still a **descriptive** extension, not a powered
  inferential test). No verdict label is emitted by the run.

## 8. Failure modes specific to the control

- **C1 — Register / style confound (the main new risk).** Specific packets are Sanskrit-laden, em-dashed, ornate;
  the generic controls are plain English. A judge may up- or down-rate on **register/exoticism**, not
  source-condition — inflating or deflating `incremental_margin` for reasons unrelated to varṇa content. **Mitigation
  (required in the real build):** register-match the two packet types — either paraphrase the specific facets into
  plain English (strip Sanskrit) **or** give the generic controls matched ornamentation/pseudo-technical phrasing —
  and pre-register which. Without this, `incremental_margin` is confounded.
- **C2 — Generic packet leaks source-condition.** If a "generic" facet accidentally encodes other-vs-self framing
  (not just valence), it absorbs the effect and deflates `incremental_margin` artificially. The drafts in §3b are
  pure mood-valence by construction; each generic facet must be audited to contain **no** other/self, agency, or
  relational content.
- **C3 — Tier-2 control still missing (recommended addition).** A generic *valence* control isolates from good/bad
  feeling, but the specific packets also encode a generic **other-conditioned vs self-grounded** axis that is not
  itself varṇa-specific. To isolate *varṇa-specific* content fully, add a **second control tier**: a *generic
  self/other source-condition* packet (word-agnostic, e.g. "a state that leans on others' response" vs "a state that
  rests in itself"), and compute `incremental_over_selfother = specific_margin - selfother_generic_margin`. If
  `incremental_margin > 0` but `incremental_over_selfother ≈ 0`, the signal is the generic self/other framing, not
  the varṇas. Strongly recommended for the definitive version.
- **C4 — Varṇa-set overlap across the six words (non-independence).** The shortlist shares varṇas heavily —
  `ra` in pride/freedom/courage/control; `da` in pride/freedom/doubt; `ka` in courage/control/patience;
  `ta` in patience/doubt. So the six specific packets are **not** independent facet-sets; a positive
  `incremental_margin` could ride on one or two recurring facets (`ra` prāṇaśakti, `da` forbearance). Report the
  per-varṇa contribution and treat the six as partially correlated, not six independent replications.
- **C5 — Facet coarseness (inherited).** control's `[tta]` (speech) and freedom/pride's coarse facets may score low
  on their own merits; a low `specific_margin` there would be about facet fit, not about the valence control.
- **C6 — Correlated / same-family judges (inherited F9).** Two Claude judges are correlated; the definitive control
  run should add **cross-family** judges.
- **C7 — Experimenter degrees of freedom (inherited F7).** Contexts and generic packets both carry expected-pole
  knowledge; author them blind and pre-register before any run.

## 9. Attribution ceiling (unchanged)

Even a clean `incremental_margin > 0` (surviving C1–C3) would show only that **word-specific packet content adds
source-condition legibility beyond generic valence, to judges** — a resonance-legibility result. It would **not**
establish ontology, semantic truth, Sanskrit privilege, generation utility, or **individual-varṇa** mapping (the
packet remains a bag of constituent-varṇa readings; even here the design cannot credit a single varṇa). B1.4b′
remains `NULL_RETURN_BOTTOM`.

## 10. What a later build would add (only on approval — NOT done here)

New, separately-labeled files that leave the four B1.10 originals byte-unchanged: a `b1_10_valence_control_ext`
items file (48 cells; specific + generic packets; hash-pinned to v3), a register-matched render, a separate
evidence-freeze declaration, a mock-tested runner reusing the B1.10 blinding + aggregation with the
`incremental_margin` statistic added, and cross-family judges. **None of that exists yet — this is design only.**

## 11. Guardrails
Docs-only — no code, no scaffold, no run, no new experiment number, no B1.11 files, no modification of the original
B1.10 frozen artifacts, B1.10 not re-run. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege claim. **B1.4b′ remains
`NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**
