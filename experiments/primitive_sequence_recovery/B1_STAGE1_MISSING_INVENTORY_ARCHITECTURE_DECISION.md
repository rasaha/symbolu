# B1 — Stage-1 Missing-Inventory Architecture Decision (docs/data-only)

**Architecture verdict: `RECOMMEND_TYPED_MIXED_INVENTORY`. Readiness: `READY_FOR_MISSING_INVENTORY_PROVENANCE_STUDY`.**
This decides the **functional type (role)** of every currently-missing Stage-1 unit *before* any meaning is authored
or inferred. It authors **no meaning, no pole, no polarity**; edits no table; runs no experiment. **Structure, not
validated meaning.** No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`. The role matrix contains **no** binding/liberating
words. Machine-readable: `missing_inventory_architecture/`.

Authoritative base: parser freeze `a1988394` (schema 1.1); integration audit `f83d8dc8`; D1–D4 reconciliation
`26d680c9`; metadata v3.1 re-freeze `1856c56f` (active table `frozen/varna_polarity_table_v3_1_metadata_refreeze.json`).

---

## A. Source-grounded architecture audit (`source_claim_ledger.json`)

Three source strata bear on the missing units, and they **do not fully agree** on the vowel role:

| id | claim | location | provenance | what it implies |
|---|---|---|---|---|
| **S1** | Native varṇa theory (Sarkar) assigns **acoustic roots to the vowels and to aṃ/aḥ** | staging plan A.1 | `SECONDARY_ATTESTED` (theory asserted; per-unit **content MISSING**) | vowels/marks are **root-bearing**, not mere carriers |
| **S2** | Patent apparatus: **vowels = FIELD** positional role; opt-in word-initial-vowel seed | patent brief L22 | `AUTHORED_PROVISIONAL` (deprecated **English** pipeline) | vowels as **positional operators**, not per-vowel meaning |
| **S3** | Dev lexicon holds authored per-vowel polar-state fields; disclaimed, English-`EY`-keyed | vowel memo | `AUTHORED_PROVISIONAL` | authored poles exist but **unattested** |
| **S4** | Privative-`a` and vowel length **flip meaning**: vidyā↔avidyā, himsā↔ahimsā, nara↔nārī | dropped-vowel probe | `PRIMARY_ATTESTED` (structural natural experiment) | vowels/prefix/length are **load-bearing** → refutes consonant-only as *complete* |
| **S5** | v3.1 table has 34 consonant entries and **no** vowel/mark entries | v3.1 table | `MISSING` | content for every missing category is absent |
| **S6** | Open in-repo: "does anusvāra carry a nasal root?" | staging plan B.3 | `UNRESOLVED` | anusvāra role explicitly open |
| **S7** | Parser preserves vowels/marks structurally, no meaning; they are **45% of tokens** | freeze record / coverage | `PRIMARY_ATTESTED` | preservation done; missing categories dominate frequency |

**The pivotal tension:** S1 (native theory → root-bearing **primitives**) vs S2 (patent English apparatus →
positional **field/operator**). S4 settles that vowels are *load-bearing* (so **not** droppable), but is a structural
existence proof — it does **not** assign per-vowel poles. No source establishes that the S1 "acoustic roots" are
**polar** (binding/liberating) rather than operator/transition roles.

## B. Category-by-category decision (`role_matrix.json`, no meanings)

- **14 vowels** (अ आ इ ई उ ऊ ऋ ॠ ऌ ॡ ए ऐ ओ औ): category role **`UNRESOLVED_ROLE`**; primary candidate
  `POLARITY_BEARING_PRIMITIVE` (S1), secondary `CONTEXTUAL_REALIZATION_OPERATOR` (S2). **May not** receive an
  independent meaning yet (`independent_semantic_entry_allowed=false`); **polarity `UNRESOLVED`**. Independent and
  dependent orthographic forms **share one identity** (parser already unifies). Length: `S4` shows it is
  *contrastive* (nara↔nārī) — so length is at least structurally load-bearing; whether it changes **role** or only
  **magnitude** is unresolved. Vocalic **ṛ/ḷ** flagged for possible separate (syllabic-sonorant) treatment. No
  individual vowel meaning is authored.
- **Anusvāra `ṃ`**: `UNRESOLVED_ROLE`; primary `MODIFIER` (nasalization), secondary `POLARITY_BEARING_PRIMITIVE`
  (S1/S6). Canonical `ṃ` kept **distinct** from any homorganic-nasal resolution. Polarity `UNRESOLVED`.
- **Visarga `ḥ`**: `UNRESOLVED_ROLE`; primary `MODIFIER` (release/exhalation), secondary
  `COMPOSITION_BOUNDARY_OPERATOR`. **Not** collapsed into `h`. Polarity `UNRESOLVED`.
- **Candrabindu**: `PHONOLOGICAL_MARKER_ONLY`; **distinct** from anusvāra; role provenance `MISSING` (no source root);
  largely Vedic/vernacular → likely outside classical-core scope. Polarity `NO`.
- **Retroflex lateral `ḷ`/ळ**: `OUT_OF_SCOPE` (extended Vedic/regional; not in the classical 34-key inventory). Do
  **not** create a table mapping without a scope justification. Polarity `NO`.

## C. Candidate-model comparison (`model_comparison.json`)

| model | keeps vowels? | source support | back-fit risk | falsifiability | explains 45% w/o inventing? |
|---|---|---|---|---|---|
| **A** full primitive symmetry | yes | PARTIAL — over-assumes vowel roots are polar | **HIGH** | LOW | no |
| **B** consonant-sem + vowel transitions | yes | PARTIAL — fits S2, conflicts S1 | MEDIUM | MEDIUM | yes |
| **C** hierarchical akṣara | yes | PARTIAL — no akṣara meanings sourced | HIGH | LOW | no |
| **D** mixed typed inventory | yes | **STRONGEST structural fit** (S1+S4+guardrail) | LOW–MED | **HIGH** | yes |
| **E** consonant-only core | no (inert) | **REFUTED as complete** by S4 | none | HIGH (already contradicted) | only by declaring 45% out of scope |

**Model D wins on source-fidelity + falsifiability + back-fit resistance** among models that retain vowels, because
it (a) keeps vowels (refuting E), (b) does not clone the consonant pole model onto them (guardrail; refuting A),
(c) treats classes as distinct types (S1 gives vowels their *own* roots; S4 shows they behave heterogeneously). The
one genuinely conflicted sub-question — is the vowel role a polar primitive (S1) or a positional operator (S2)? —
is held **`UNRESOLVED`** inside the typed inventory, to be settled by evidence, not by preference.

## D. Decision criteria (ranking in `model_comparison.json#criterion_ranking`)

Across the 10 criteria (source fidelity, parameter minimality, phonological preservation, determinism, ordered-parser
compatibility, back-fit resistance, falsifiability, composition-preregisterability, native-before-English, structure/
meaning separation), **D ranks first on 8 of 10**; E leads only parameter-minimality and ties back-fit resistance.
The verdict is chosen on **source fidelity and falsifiability, not completeness/coverage.**

## E. Provenance policy for future inventory completion (`provenance_policy.json`)

- The **confirmatory** Stage-1 mechanism admits only `PRIMARY_ATTESTED` / `SECONDARY_ATTESTED` roles.
- `INFERRED` roles require a **separately stated derivation**.
- **`AUTHORED_PROVISIONAL` meanings are development-only and are NOT permitted in the confirmatory mechanism.**
- `MISSING` units must **not** be silently ignored; **absence of a semantic role may itself be an explicit
  architectural decision.**
- Before a unit may receive a **pole**, there must be sourced evidence that its root is **polar** — S1 (roots exist)
  does **not** establish this. Before an **independent gloss**, a `PRIMARY/SECONDARY` source root for that specific
  unit. A **modifier** role needs a sourced phonological role (structural, still no meaning). A **context rule** must
  be deterministic, pre-registered, and kept distinct from canonical output.

## F. No-meaning role-matrix prototype

`missing_inventory_architecture/role_matrix.json` — 18 units, fields `devanagari / canonical_unit / category /
stage1_scope / candidate_roles / recommended_role / role_provenance / independent_semantic_entry_allowed /
polarity_allowed / modifies_previous / modifies_next / composition_effect / unresolved_questions /
required_evidence_before_activation`. **Verified free of binding/liberating words**; no unit is granted an
independent semantic entry; polarity is `UNRESOLVED`/`NO` everywhere.

## Answers to the required report questions

- **Recommended architecture:** `RECOMMEND_TYPED_MIXED_INVENTORY` (Model D), vowel role cell held `UNRESOLVED`.
- **Category-level roles:** vowels → `UNRESOLVED_ROLE` (primary `POLARITY_BEARING_PRIMITIVE`); anusvāra → `UNRESOLVED_ROLE`
  (primary `MODIFIER`); visarga → `UNRESOLVED_ROLE` (primary `MODIFIER`); candrabindu → `PHONOLOGICAL_MARKER_ONLY`;
  `ḷ` → `OUT_OF_SCOPE`.
- **May individual vowels receive meanings?** **No** — not until a provenance study sources per-vowel Sarkar acoustic
  roots from primary text; authored-provisional vowel meanings remain development-only.
- **Does polarity apply to vowels/markers?** **Unresolved.** The source claims *roots*, not that those roots are
  polar; polarity is not permitted for any vowel/marker until it is *sourced as polar*.
- **Unresolved source ambiguities:** the vowel role (S1 primitive vs S2 field); whether vowel roots are polar;
  length as role vs magnitude; vocalic ṛ/ḷ treatment; anusvāra nasal-root (S6); visarga modifier-vs-boundary;
  candrabindu/`ḷ` scope.
- **Readiness:** `READY_FOR_MISSING_INVENTORY_PROVENANCE_STUDY` (not composition prereg, not semantic testing).

## Single recommended next action

Run the **missing-inventory provenance study**: source the Sarkar acoustic roots for the 14 vowels and aṃ/aḥ from
primary text (the same discipline that produced the consonant backbone via the b1_2 lexicon), and for each sourced
root record its provenance class **and** whether it is polar or an operator/transition role. That study resolves the
`UNRESOLVED` vowel/anusvāra/visarga role cells and unblocks the typed-mixed inventory — before any composition
pre-registration or semantic word testing.
