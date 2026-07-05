# B1.1 Proposal — Open-Item Resolution (before JSON)

## Scope and non-claims

Resolves the five open items in `B1_1_EXPERIMENTAL_CONTRASTIVE_LEXICON_PROPOSAL.md` (7c8fbfa) **before** any
JSON is drafted, so Na/Ra/Śa ambiguity cannot leak into a frozen experimental lexicon. **No JSON modified ·
no model run · no generation · no scoring.** Does **not** modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology validation, Sanskrit
privilege, or semantic-truth claim. **Structure, not validated meaning.** Rewritten counter-poles remain
**experimental interpretive renderings**, not classical Sanskrit meanings.

---

## Decision 1 — Na rendering (must not duplicate Ca's protected Viveka)

**Decision:** keep a rendering in the *de-fascination / spell-breaking* family; **do not** use "discernment",
"clarity", "discrimination" (those belong to Ca's protected Viveka), and **do not** use "renunciation"
(that is the Ka/Gha/Dha release family) or "disgust". Adopt the operator's candidate wording as the working
rendering, and **retain the prior "disenchantment" phrasing as a documented human-readable alternative** so
the final choice is a human call at JSON time.

**Working rendering (adopted):**
- source-attested pole: **Moha** — blind attachment / infatuation (binding, preserved)
- experimental counter-pole: **de-fascination from false attraction**
- functional operation: **breaks the spell of blind attachment by making the attractive object lose its
  compulsive grip**
- contrast boundary: **not Ca/Viveka (discrimination), not general clarity, not renunciation (Ka/Gha/Dha),
  not disgust/revulsion (Pa)**

**Alternative candidate (retained for human choice):** counter-pole "disenchantment — seeing through a
binding fixation"; operation "dispels the enchantment that binds one to a fixation." Same family, terser;
kept as a documented option, not discarded.

**Contrastivity note:** "de-fascination / spell-breaking" is distinct from **Bha** (*snap a hypnotic
spell* — Mūrcchā, an externally-induced entrancement) because Na's object is an *internally-generated
compulsive attraction* (infatuation), whereas Bha's is a *loss of common sense under a ripu's spell*. The
boundary fields must name each other (Na "not Bha's induced spell"; Bha "not Na's self-generated
fascination").

---

## Decision 2 — Ra (source-complex / protected special case)

**Decision:** **protect the source-attested Ra material; no normal interpretive rewrite.** Ra is
**dual-attested in the classical source** — *Prāṇaśakti / Agnitattva* (vitality / creative fire, positive)
**and** *Sarvanāśa* (defeatist annihilation-thought, negative). Both poles are classical; **neither is a
derived interpretive counter-pole**, so the standard "rewrite the counter-pole" rule does **not** apply.

**Handling:** flag Ra as **`SOURCE_COMPLEX / DUAL_SOURCE`** in the JSON draft — both poles labeled
source-attested, no synthetic counter-pole generated. **Any Ra counter-pole rewrite requires separate,
explicit human approval** and is out of scope for the first JSON draft.

- source-attested pole (positive): Prāṇaśakti / Agnitattva — vitality / creative fire
- source-attested pole (negative): Sarvanāśa — defeatist annihilation-thought
- status: **dual-source; no interpretive rewrite; human-review-gated**

---

## Decision 3 — Śa (source-attested neutral dynamic principle)

**Decision:** **protect the source-attested neutral principle; do not force it into a simple positive/negative
virtue pair.** Śa is the acoustic root of *rajoguṇa* (the mutative principle) + *artha* (psychic longing) —
a **neutral dynamic principle**, not a moral pole.

**Handling:** represent Śa as a **`SOURCE_NEUTRAL_PRINCIPLE`**. Any directional label (e.g. "directed
accomplishment" vs "restless acquisition") is **interpretive and provisional**, explicitly marked as such.
**Do not** collapse Śa into a virtue/vice pair. **Separate human review required before JSON freeze.**

- source-attested principle: rajoguṇa (mutative) + artha (psychic longing) — neutral dynamic drive
- provisional interpretive ends (NOT source truth): "directed accomplishment" ↔ "restless acquisition"
- status: **neutral principle; ends interpretive/provisional; human-review before freeze**

---

## Decision 4 — Blocked / source-pole conditioning ablation

**Decision:** **include as EXPLORATORY in the B1.1 design — not co-primary** (promote to co-primary only if
sample size / power supports it at prereg). Rationale: the source-attested poles are *more distinct* than the
interpretive counter-poles, so this tests whether the distinct source poles separate from R better than the
rewritten counter-poles do — directly probing whether contrastivity of the *source* side is the operative
variable.

**Exploratory arms (defined; to be finalized at `B1_1_PREREG`):**
| arm | conditioning content |
|---|---|
| `A_dual_pole` | normal revised conditioning (source-attested + counter-pole together) — the default A |
| `A_source_only` | source-attested pole only |
| `A_counter_only` | experimental counter-pole only |
| `A_source_weighted` | source pole dominant, counter-pole secondary |

**Purpose:** test whether the more distinct **source-attested** poles beat R more than the interpretive
**counter-poles** do. **Status: exploratory**; reported, non-gating, unless prereg power analysis justifies
co-primary. Each still measured against the same R controls (R_same, R_deranged, R_domain).

---

## Decision 5 — Vowels

**Decision:** **out of scope for the first B1.1.** B1.1 is **consonants-only** unless a **separate vowel
audit + pre-registration** is run. **Do not include vowels in the first B1.1 lexicon JSON draft.**

---

## Consequences for the JSON draft (next gate, not yet approved)

The future `B1_1_EXPERIMENTAL_LEXICON_JSON_DRAFT` must encode:
- **Na** → the adopted de-fascination rendering (alternative retained in a comment/field for human choice).
- **Ra** → `SOURCE_COMPLEX / DUAL_SOURCE`, no synthetic counter-pole, human-review-gated.
- **Śa** → `SOURCE_NEUTRAL_PRINCIPLE`, directional ends flagged interpretive/provisional, human-review before freeze.
- **Ablation arms** → carried into `B1_1_PREREG` as exploratory (not into the lexicon JSON itself, which just
  supplies the poles; the arms are a *design* artifact).
- **Vowels** → excluded.
- Every rewritten counter-pole → field-tagged `experimental_interpretive_rendering: true`.

None of this is executed here; the JSON draft is a separate, separately-approved gate.

## Final status

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             OPEN-ITEM RESOLUTION ONLY
JSON modified:         NO
Model run:             NO
Generation run:        NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
**Structure, not validated meaning.** Resolution only; the B1 verdict stands and Track B remains BLOCKED.
