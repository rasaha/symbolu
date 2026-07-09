# B1.6 — Named-Vṛtti Dual-Pole Candidate (v2 Representation)

**Status:** Representation-design note (docs only) for the B1.6-v2 named-vṛtti table
(`track_g_varna_polarity_table_v2_named_vritti.json`). **Candidate, unvalidated. No generation. No evidence
freeze. No `GENUTILITY_*`. Not ontology / Sanskrit privilege / semantic truth. B1.4b′ remains
`NULL_RETURN_BOTTOM`. Structure, not validated meaning.**

---

## 1. What changed vs v1

- **v1 (superseded):** each varṇa → signed contributions on 10 **generic directional axes**
  (expansion/contraction, binding/release, …). Abstract; the "meaning" was axis geometry.
- **v2 (this candidate):** each varṇa → its **named vṛtti/root** with an explicit **worldly-binding distortion**
  and **spiritual-liberating reading**, extracted from the frozen sources. The scaffold carries named content
  (dharma, mokṣa, sattva, …), not axis coordinates.

## 2. Per-varṇa fields (extracted, not invented)

For each reachable varṇa: `named_attribute` + `spiritual_liberating_reading` from `track_e` (root / spiritual
sphere); `worldly_binding_distortion` from the `realization_en_gloss` binding-sense gloss; plus `atom_id`,
`source_binding_gloss_verbatim`, `spheres`, `source_path`, `source_hash`, `leak_risk`, `notes`. A varṇa without
source coverage would be `SOURCE_INSUFFICIENT` (none were, for the 25 reachable keys).

## 3. Worked examples

- **`va`** — named: *dharma; holding (dhṛ = "to hold"); jala-tattva; Varuṇa; sustaining flow*. Binding: *rigid
  holding; stuck ensconcement; over-holding; clinging to holding*. Liberating: *dharma; sustaining flow;
  alignment with sustaining principle; movement toward subtlety*. Interpretive (tagged): *order/right order*
  (gloss of dharma). *possession* removed.
- **`sa`** — named: *mokṣa; sattva-guṇa; clarity; peace; release; liberation-oriented thought*. Binding:
  *escapism; premature static withdrawal; inert/static withdrawal*. Liberating: *sattva; clarity; peace;
  release; mokṣa; unqualified liberation*. Interpretive (tagged): *goodness/purity* (gloss of sattva).

## 4. KCPR named dual-pole rule

Both poles are shown per varṇa (`worldly_binding_pole`, `spiritual_liberating_pole`); the generator is not told
which is "correct"; no per-target selection; no post-output editing. The named root is not "bad" — same root,
two koshic readings.

## 5. Leakage note (v2-specific)

v2 scaffolds deliberately carry **named-meaning glosses** to the Symbol-U arm (that is the point of a named
interpretive scaffold). This does **not** breach blinding: the scaffold is **not** in the judge-visible package,
and the driver's `assert_blind` forbids **system-identifying** tokens (`Symbol-U`, `varṇa`, `KCPR`, `scaffold`,
`polarity`, …) in any generated output — content words like *dharma*/*mokṣa* are legitimate interpretation and
are not arm-identifying. A future judging pass should still watch for a model over-naming a source gloss in a way
that a judge could pattern-match; the pre-registered non-genericity / overclaim penalties cover that.

## 6. Guardrails

Candidate representation only; unvalidated; not ontology / Sanskrit privilege / semantic truth. No generation, no
evidence freeze, no `GENUTILITY_*`. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked. Track B
blocked. **Structure, not validated meaning.**

---

> B1.6 named-vṛtti dual-pole candidate documented (v2 representation). No generation run. B1.4b′ remains
> NULL_RETURN_BOTTOM. Structure, not validated meaning.
