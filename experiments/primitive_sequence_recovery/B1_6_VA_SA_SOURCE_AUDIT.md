# B1.6 — `va` / `sa` Source Audit (Pre-v2 Checkpoint)

**Status:** Source-audit checkpoint (docs only). Records exactly what the **frozen** source supports for `va` and
`sa`, what is interpretive, and what to remove/soften **before** a B1.6-v2 named-vṛtti candidate is drafted.
**No frozen table modified. No B1.6-v2 created. No generation run. No evidence freeze. No judging. No
`GENUTILITY_*` label.**
**This is not semantic validation, not ontology, not Sanskrit privilege. B1.4b′ remains `NULL_RETURN_BOTTOM`.
Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_VA_SA_SOURCE_AUDIT_DOCUMENTED`.**

Sources audited: `frozen/realization_en_gloss.json` (via `frozen/assignment.json` varṇa→atom `tau`),
`track_e_varna_sphere_lexicon.json`, `track_g_varna_polarity_table.json`.

---

## 1. Purpose

A **checkpoint before the B1.6-v2 named-vṛtti refreeze**. It fixes, on record, which `va`/`sa` wording is
**directly source-supported**, which is **interpretive**, and which is **unsupported** and must be removed or
softened — so that a later B1.6-v2 candidate table can be authored from grounded material, blind and frozen
before any run. **It edits no frozen table and creates no v2.**

## 2. Verbatim source evidence

**`va` → `atom_28`**

- **Primary gloss** (`realization_en_gloss.atom_content[atom_28]`): *"holding / ensconcement in original stance
  (BINDS — dhṛ = to hold; non-moral)"*
- **Root** (`track_e`): *"dharma; jala-tattva / liquid factor; Varuna"*
- **Spheres** (`track_e`): physical *"water / liquid, sustaining flow"*; mental *"natural movement toward
  happiness and rightness"*; intellectual *"alignment with sustaining principle"*; spiritual *"dharma; movement
  toward subtlety; ensconcement in original stance"*
- **`track_g` axes:** `integration_fragmentation: +1`, `binding_release: +1`

**`sa` → `atom_31`**

- **Primary gloss** (`realization_en_gloss.atom_content[atom_31]`): *"escapism / premature static withdrawal"*
- **Root** (`track_e`): *"moksha; sattva-guna"*
- **Spheres** (`track_e`): physical *"lightness, release from binding action"*; mental *"clarity, peace,
  release"*; intellectual *"sentient discrimination, liberation-oriented thought"*; spiritual *"moksha,
  salvation, unqualified liberation, sattva"*
- **`track_g` axes:** `expansion_contraction: -1`, `activity_inertia: -1`

*(All entries self-declare as `researcher_authored_candidate_representation` / `unvalidated` /
`not_ontological_evidence`; `track_e` four-sphere fields are a researcher expansion of the classical
P.R. Sarkar acoustic-root, not present in the source.)*

## 3. Source-supported B1.6-v2 wording

**`va`**

- **Root / named attribute:** dharma; holding; *dhṛ = "to hold"*; jala-tattva (liquid factor); Varuṇa; sustaining
  flow / "alignment with sustaining principle"; "movement toward subtlety". *(all direct from §2)*
- **Binding / worldly distortion:** rigid holding; stuck ensconcement ("in original stance"); over-holding;
  clinging to holding. *(from "holding / ensconcement … BINDS")*
- **Liberating / spiritual reading:** dharma; sustaining flow; alignment with sustaining principle; movement
  toward subtlety. *(from spiritual + physical + intellectual spheres + jala)*

**`sa`**

- **Root / named attribute:** mokṣa; sattva-guṇa; clarity; peace; release; "liberation-oriented thought". *(all
  direct from §2)*
- **Binding / worldly distortion:** escapism; premature static withdrawal; inert / static withdrawal. *(from
  "escapism / premature static withdrawal" + `track_g` inertia)*
- **Liberating / spiritual reading:** sattva; clarity; peace; release; mokṣa; unqualified liberation. *(from
  mental + physical + spiritual spheres)*

## 4. Interpretive-gloss policy

- **`va` = "order" / "right order":** usable **only as an interpretive gloss** of *dharma* / *"rightness"* /
  *"sustaining principle"* — **not** as direct source text ("order" does not appear in the source).
- **`sa` = "goodness" / "purity":** usable **only as an interpretive gloss** of *sattva-guṇa* — **not** as direct
  source text ("goodness"/"purity" do not appear in the source).
- **`va` = "possession":** **remove.** The source is *"holding / ensconcement," explicitly non-moral*;
  "possession" adds an acquisitive/moral connotation not present. (If ever kept, it must be explicitly labeled a
  loose non-source interpretation — but the preferred action is **remove**.)
- Any interpretive gloss carried into B1.6-v2 must be **visibly tagged as interpretive**, never presented as
  frozen-source wording.

## 5. KCPR principle (recorded)

- **The named root itself is not "bad."** `va`'s gloss is explicitly *"non-moral"*; `sa`'s root is *mokṣa /
  sattva* (liberation-oriented).
- **The same root can bind** when distorted at the **worldly / grosser** layer (`va`: rigid/stuck holding;
  `sa`: escapism / premature static withdrawal).
- **The same root can liberate** when expressed at the **subtler / spiritual** layer (`va`: dharma / movement
  toward subtlety; `sa`: sattva / mokṣa / unqualified liberation).
- **Both poles should be shown** (the B1.6 `DUAL_POLE_RENDERING` stance) unless a **future frozen mechanical
  context rule** selects one — no per-item pole selection is made here.

## 6. Status

- This audit **supports carrying the corrected `va` and `sa` wording into B1.6-v2** — as a new, versioned
  candidate authored blind and frozen before any run.
- **This is not semantic validation.** **Not ontology.** **Not Sanskrit privilege.** It records source-grounding
  for a candidate *utility-test* representation only.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

## 7. Guardrails

- **No frozen table edited** (`track_g` / `track_e` / `realization_en_gloss` untouched).
- **No B1.6-v2 created yet.**
- **No generation run. No evidence freeze. No judging. No `GENUTILITY_*` label.**
- No semantic-truth / ontology / Sanskrit-privilege claim. Original B1.4b remains blocked. Track B remains
  blocked. **Structure, not validated meaning.**

## 8. Readiness label

**`B1_6_VA_SA_SOURCE_AUDIT_DOCUMENTED`.**

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_6_VA_SA_SOURCE_AUDIT.md`. No other file
  modified.
- **Commit hash:** (recorded on commit below).
- **Readiness label:** `B1_6_VA_SA_SOURCE_AUDIT_DOCUMENTED`.
- **No table/scaffold changed** — `track_g_varna_polarity_table.json`, `track_e_varna_sphere_lexicon.json`,
  `frozen/realization_en_gloss.json`, and the frozen B1.6 scaffolds are all untouched.
- **No generation / evidence freeze / judging occurred.** No `GENUTILITY_*` label.
- **`va` correction:** ~grounded (dharma / holding / dhṛ / jala / Varuṇa / ensconcement / sustaining / subtlety);
  remove **"possession"**; "order/right order" → interpretive gloss of dharma only.
- **`sa` correction:** ~grounded (mokṣa / sattva / clarity / peace / release / liberation / escapism / premature
  static withdrawal); "goodness/purity" → interpretive gloss of sattva only.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 va/sa source audit documented only. No table or scaffold changed. No generation run. No evidence freeze.
> No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains
> blocked. Structure, not validated meaning.
