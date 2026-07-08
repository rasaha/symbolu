# B1.6 — KCPR Theory Accommodation Audit

**Status:** Theory-accommodation audit (docs only). Locates the governing pole/polarity theory sources and audits
the B1.6 KCPR pole-selection rulebook (`1937b9f`) against them **before** any pilot scaffold is frozen. **No
code, no generation run, no pilot-scaffold instantiation, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Decision: `KCPR_THEORY_AMENDMENT_REQUIRED`. Readiness: `B1_6_KCPR_THEORY_AMENDED_READY`** (via
`B1_6_KCPR_THEORY_AMENDMENT.md`).

Audits: `B1_6_KCPR_POLE_SELECTION_RULEBOOK.md` (`1937b9f`), `frozen/b1_6_kcpr_pole_selection_manifest.json`.

---

## 1. KCPR theory-document search

Searched the repo for `KCPR`, `Kosha`, `pole`, `polarity`, `correct pole`, `binding`, `liberating`, `worldly`,
`counter`, `context`, and any document defining KCPR **theory** (vs experiment rules).

**Finding — no document defines "KCPR" as a theory.** The literal acronym **`KCPR` occurs only under
`experiments/primitive_sequence_recovery/`** and is **never expanded** except in this session's own B1.6
rulebook. There is **no repo-wide "KCPR theory document."**

**But governing pole/polarity *theory* sources exist** and materially constrain the rulebook. These are audited
here (full sha256):

| Doc | Path | sha256 (16) | Relevance |
|---|---|---|---|
| Primitive-vṛtti ontology (frozen note) | `varna_lens/PRIMITIVE_VRTTI_WITHOUT_POLARITY.md` | `43ab478894bb184e` | **prohibits polarity as a per-varṇa input** |
| CRS pole-selection prereg | `varna_lens/PREREG_CRS_POLE_SELECTION.md` | `06e38428b719e88d` | **governs how poles may be selected** |
| Varṇa State-Operator theory | `VARNA_STATE_OPERATOR_THEORY.md` | `16d9eeda9b6644b3` | binding/liberating = theoretical internal coordinate; circular if used as measured |
| Symbol-U theory v1 freeze | `SYMBOL_U_THEORY_V1_FREEZE.md` | `7862c2837244e8d9` | readings track sound not meaning |
| B1.1 binding/liberating pole language | `B1_1_BINDING_LIBERATING_POLE_LANGUAGE_ADDENDUM.md` | `8a9fa0d75ee6880e` | pole-language convention |
| KCPR experiment rules | `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` | `acfff4043db5b2f1` | decoder-side pole rule; kosha experimentally assigned |

This is **not** `B1_6_KCPR_THEORY_BLOCKED_SOURCE_NOT_FOUND`: relevant governing theory **was** found (just not a
KCPR-named one). The audit proceeds against these sources, and **does not silently override** them.

## 2. Expansion audit

**No theory document expands `KCPR`.** → **`KCPR_EXPANSION_NOT_FOUND`** stands (no inference). The B1.6
operational expansion **"Kosha-Context Pole Resolution"** remains an operational-only label (unchanged), not a
historical/theory expansion.

## 3. Theory content audit

- **Pole selection (`PREREG_CRS_POLE_SELECTION.md`):**
  - "Whole-word semantic labels must **not** choose varṇa poles" — doing so is **circular** (the reading merely
    echoes the label).
  - **Design A — strict structure-first pole decoding (a deterministic vowel-attachment rule) — is the PERMANENT
    baseline.** Semantic/contextual signal `S` may *rank/weight* readings but **never flips a pole**
    ("*S before R, or S after R — never inside R*").
  - **CRS-guided pole selection is NOT implemented now** (gated future; admissible only for genuine structural
    ambiguity, never to override an unambiguous pole).
- **Polarity as input (`PRIMITIVE_VRTTI_WITHOUT_POLARITY.md`, frozen for that note):**
  - Each varṇa → one **irreducible** vṛtti with **no internal polarity/intensity/valence coordinates**.
  - **Strict prohibition:** "no polarity/intensity/binding-liberating **input** coordinate; **no lexicon
    polarity/counter-pole grounding**; no gloss embeddings; no fitting."
  - **Polarity is EMERGENT after composition, never an input** — "admit it only as one possible emergent Φ" on
    the **composed** state, "undefined on single primitives."
- **Binding/liberating status (`VARNA_STATE_OPERATOR_THEORY.md`):** `φ_binding`, `φ_liberating` are
  **theoretical internal coordinates**; "using the internal binding/liberating coordinate **as if it were a
  measured quantity** is the circularity to avoid... falsifiable only once bridged."
- **How context / Kosha determines the pole:** the pole-selection theory (CRS prereg) selects poles
  **structurally** (vowel-attachment), not by Kosha; **no theory source supplies a mechanical Kosha→pole rule.**
- **Polarity axes structure:** the tradition-facing docs frame poles as **binding vs liberating** (B1.1
  addendum); the operative track_g axes are **directional pole pairs** (expansion/contraction, …) — a candidate
  representation, not a validated binding/liberating ontology.
- **Target-specific interpretation:** **forbidden** where a whole-word/semantic label would author the pole
  (CRS prereg §1).

## 4. Compatibility with the current B1.6 KCPR rulebook

| B1.6 rulebook property | vs theory | verdict |
|---|---|---|
| **No per-target pole selection** (`DUAL_POLE_RENDERING`) | CRS prereg forbids semantic pole selection; dual-pole selects nothing | **compatible** (strictly safer than the CRS baseline) |
| **Never flips a pole** (both shown) | "S never flips a pole" | **compatible** |
| **Both poles rendered as a tension-field, not a truth claim** | candidates allowed; labels must not author poles | **compatible** |
| **Kosha deferred** | no theory Kosha→pole rule exists; not required for rendering | **compatible** |
| **CSR/STL deferred** | CRS is firewalled + gated ("not implemented now") | **compatible** (safer) |
| **Low-leak axis-pole names only; high-leak vṛtti notes withheld** | avoids label/gloss authoring the pole | **compatible** |
| **Uses per-varṇa polarity table (track_g) as scaffold *input* content** | `PRIMITIVE_VRTTI` prohibits polarity as a per-varṇa **input** coordinate / counter-pole grounding; polarity should be **emergent after composition** | **conflict** |
| **Treats binding/liberating lean as given** | `VSO`: internal coordinate is circular if used **as if measured** | **compatible with caveat** (B1.6 disclaims validity, but must say so explicitly) |
| **No structure-first (vowel-attachment) pole-decoding baseline in the scaffold** | CRS prereg makes Design A the permanent baseline (for *decoding*) | **compatible with caveat** (B1.6 is generative-utility, not pole-decoding; note it) |

**Net:** the *pole-selection* theory (the operative CRS prereg) is **satisfied** — B1.6 selects/flips **no**
pole, which is the mildest, safest position. The single **conflict** is narrower and ontological: B1.6 feeds a
**per-varṇa polarity table as scaffold input**, which the frozen `PRIMITIVE_VRTTI` note prohibits (polarity must
be emergent/output, not a per-primitive input), and which `VSO` flags as circular if treated as measured.

## 5. Decision

**B. `KCPR_THEORY_AMENDMENT_REQUIRED`.** Not `A (COMPATIBLE)` — there is a real conflict on the
polarity-as-input axis that must not be papered over. Not `C (BLOCKS_PILOT)` — the conflict is about the
**ontological status** of the polarity scaffold, which B1.6 **already disclaims** (it tests *generative utility
of a candidate scaffold*, not theory-truth), and the operative *pole-selection* rules are satisfied (no
selection, no flip). Not `D (SOURCE_NOT_FOUND)` — governing theory was found. The proportionate fix is a
**docs-only amendment** that makes the epistemic status explicit and adds guards, **without changing the
mechanism**. See `B1_6_KCPR_THEORY_AMENDMENT.md`.

## 6. Amendment summary (see `B1_6_KCPR_THEORY_AMENDMENT.md`)

The amendment (docs/manifest only) cites the theory docs + hashes and adds, **without altering the
`DUAL_POLE_RENDERING` mechanism or `policy_sha256`:**

- a **`THEORY_NONCANONICAL_INPUT_POLARITY` guard** — the per-varṇa polarity dual-pole frame is an **admittedly
  theory-noncanonical candidate readout scaffold** for a *utility* test; it is **not** a claim that polarity is a
  real per-varṇa input coordinate, **not** the emergent-from-composite readout the frozen note prefers, and **not**
  validated;
- an explicit statement that **the coordinate-free operator layer L (Stage A′) stays polarity-free** — polarity
  enters **only** the downstream generative *readout scaffold*, never operator composition, so the
  "keep polarity out of L/primitives" prohibition is **honored**;
- a **no-selection / no-flip** restatement (satisfying the CRS prereg's anti-circularity rule);
- preservation of **no-target-tuning**, **no ontology/semantic-truth claim**, and **B1.4b′ `NULL_RETURN_BOTTOM`**;
- a manifest readiness bump to **`B1_6_KCPR_THEORY_AMENDED_READY`**.

## 7. Correct-pole-selection check (task §7)

The theory does **not** require correct-pole selection — the CRS prereg **forbids** semantic pole selection and
mandates no pole-flipping; `DUAL_POLE_RENDERING` performs **no** selection. There is **no** frozen mechanical
context rule that selects a "correct" pole, and none is invented. Therefore **not**
`B1_6_KCPR_BLOCKED_TARGET_SPECIFIC_SELECTION_UNFROZEN` (we do not attempt target-specific selection at all).

## 8. Kosha check (task §8)

No mechanical Kosha→pole assignment rule exists in any theory source; the pole-selection theory (CRS prereg)
selects poles **structurally**, not by Kosha. B1.6 **does not require** Kosha (dual-pole rendering needs none),
so the missing Kosha rule does **not** block it → **not** `B1_6_KCPR_BLOCKED_KOSHA_REQUIRED_BUT_UNFROZEN`. Kosha
remains **deferred**; **no Kosha layer is invented.**

## 9. Readiness label

**`B1_6_KCPR_THEORY_AMENDED_READY`** (emitted via the amendment). A polarity source exists; the pole-selection
theory is satisfied; the one ontological conflict is resolved by an explicit epistemic guard, not by overriding
the theory. Not `..._COMPATIBLE` (a conflict existed and required an amendment). Not any block label (§5, §7,
§8). Not `..._INVALID_LEAKAGE` (no generation/judge exposure; only low-leak pole names).

## 10. Downstream instruction

Because the readiness label is **amended-ready**, the next step is the **B1.6 pilot target/scaffold instantiation
package** — carrying the theory caveats (the `THEORY_NONCANONICAL_INPUT_POLARITY` guard, L-stays-polarity-free,
no-selection/no-flip, CSR/STL deferred, Kosha deferred). *(Instantiation itself is a separate gated step — not
performed here — and still requires target freeze, randomized-control freeze, and an operator evidence-freeze
before any generation.)*

## 11. Guardrails

- **No generation.** **No evidence freeze.** **No semantic-truth claim.** **No `ONTOLOGICAL_SIGNAL`.** **No
  Sanskrit privilege.** **No target-specific pole choice** (no mechanical frozen rule exists; none invented).
  **No high-leak theory/vṛtti content sent to the generator.** **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original
  B1.4b remains blocked. Track B remains blocked. **The theory documents are neither overridden nor invented** —
  the conflict is surfaced and bounded, not hidden. **Structure, not validated meaning.**

---

## Final report

- **Files created/modified:** created `B1_6_KCPR_THEORY_ACCOMMODATION_AUDIT.md` and
  `B1_6_KCPR_THEORY_AMENDMENT.md`; updated `frozen/b1_6_kcpr_pole_selection_manifest.json` (readiness label +
  theory-accommodation block; `DUAL_POLE_RENDERING` mechanism and `policy_sha256` unchanged). No non-KCPR prior
  artifact modified.
- **Commit hash:** (recorded on commit below).
- **KCPR theory source path/hash:** **no KCPR-named theory doc exists** (`KCPR` acronym confined to the
  experiment track). Governing pole/polarity theory sources audited: `varna_lens/PRIMITIVE_VRTTI_WITHOUT_POLARITY.md`
  (`43ab478894bb184e`), `varna_lens/PREREG_CRS_POLE_SELECTION.md` (`06e38428b719e88d`),
  `VARNA_STATE_OPERATOR_THEORY.md` (`16d9eeda9b6644b3`), `SYMBOL_U_THEORY_V1_FREEZE.md` (`7862c2837244e8d9`).
- **KCPR expansion if explicitly found:** **none** — `KCPR_EXPANSION_NOT_FOUND` (operational expansion retained).
- **Compatibility decision:** **`KCPR_THEORY_AMENDMENT_REQUIRED`** — pole-selection theory satisfied; one
  ontological conflict (per-varṇa polarity as input) resolved by explicit epistemic guard.
- **Readiness label:** **`B1_6_KCPR_THEORY_AMENDED_READY`**.
- **Does `DUAL_POLE_RENDERING` stand / amended / blocked?** **Stands, amended** — mechanism unchanged; epistemic
  guards (`THEORY_NONCANONICAL_INPUT_POLARITY`, L-stays-polarity-free, no-selection/no-flip) added.
- **Kosha:** **remains deferred** (not required; none invented).
- **May pilot scaffold instantiation proceed?** **Yes** — next step is the pilot target/scaffold instantiation
  package, carrying the theory caveats; instantiation remains a separate gated step (not done here).
- **No generation run was performed.**
- **No evidence freeze was declared.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 KCPR theory accommodation audit completed docs-only. No generation run. No evidence freeze. B1.4b′ remains
> NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
