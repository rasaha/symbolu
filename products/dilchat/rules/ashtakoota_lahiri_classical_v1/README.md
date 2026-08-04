# Rule Pack: `ashtakoota_lahiri_classical_v1`

> **STATUS: DRAFT — `draft: true`. NOT for user-facing use.**
> Per **DEC-009** (see `docs/DILCHAT_DECISION_LOG.md`) this pack encodes the
> classical eight-Koota Ashtakoota (Guna Milan) tables using widely-documented
> standard values, but it has **not** been verified against a single named
> textual authority and **requires Vedic-astrology domain-expert sign-off and
> founder approval** before it can back any user-facing compatibility report.
> Cross-reference `docs/DILCHAT_ASTROLOGY_ENGINE_SPEC.md` for how the engine
> consumes this pack.

This directory is a **versioned, self-contained data pack** — pure JSON tables
plus this schema description. It contains **no code**. The `guna_milan` module
loads these files and applies the encoded rules deterministically (DEC-019:
Classical Compatibility is fixed by natal data + rule pack; AI may explain it,
never alter it).

## Provenance tuple

| Field | Value |
|-------|-------|
| `rule_pack_id` | `ashtakoota_lahiri_classical_v1` |
| `version` | `1.0.0-draft` |
| `ayanamsa` | `lahiri` (DEC-008, `SE_SIDM_LAHIRI`) |
| `zodiac` | `sidereal` |
| `tradition` | `north_indian_ashtakoota` (assumed default — flag for founder/domain confirmation) |

## Index conventions (authoritative — used as JSON keys across all files)

- **Nakshatra indices `0..26`** = Ashwini(0), Bharani(1), … Revati(26). The
  canonical list lives in `manifest.json → nakshatras`.
- **Rashi indices `0..11`** = Aries/Mesha(0), Taurus(1), … Pisces/Meena(11).
  Canonical list in `manifest.json → rashis`.
- Every table that is `keyed_by: "nakshatra"` or `keyed_by: "rashi"` uses these
  exact integer indices (as JSON string keys). They must stay consistent with
  the manifest lists.

## Files

| File | Koota | Max | Keyed by | Contents |
|------|-------|-----|----------|----------|
| `manifest.json` | — | — | — | Pack identity, ayanamsa/zodiac, `draft`/`review_required`, per-component directional flags, seeker/partner→bride/groom role mapping, component list with maxima (total 36), canonical nakshatra & rashi lists. |
| `varna.json` | Varna | 1 | rashi | Moon-rashi → varna (Brahmin/Kshatriya/Vaishya/Shudra) + groom-varna ≥ bride-varna → 1 else 0. |
| `vashya.json` | Vashya | 2 | rashi | Rashi → vashya group (Chatushpada/Manava/Jalachara/Vanachara/Keeta) + group-pair score matrix (2/1/0.5/0). |
| `tara.json` | Tara | 3 | nakshatra | 9-tara sequence + auspicious flags + counting rule + bidirectional combine (3/1.5/0). |
| `yoni_matrix.json` | Yoni | 4 | nakshatra | 14 yonis, nakshatra → yoni, 14×14 compatibility matrix (4 same … 0 mortal enemy). |
| `graha_maitri_matrix.json` | Graha Maitri | 5 | rashi | Rashi → lord, Naisargika planet-friendship table, compound score (5/4/3/1/0.5/0). |
| `gana_matrix.json` | Gana | 6 | nakshatra | Nakshatra → gana (Deva/Manushya/Rakshasa) + directional 3×3 matrix (6…0). |
| `bhakoot.json` | Bhakoot | 7 | rashi | Rashi-to-rashi counting rule; 2/12, 5/9, 6/8 → 0 else 7. |
| `nadi.json` | Nadi | 8 | nakshatra | Nakshatra → nadi (Aadi/Madhya/Antya); same nadi → 0 (dosha) else 8. **Constitutional only (DEC-021).** |
| `exceptions.json` | (parihara) | — | — | Optional dosha-cancellation rules, **all `enabled: false` by default**, each with id, conditions, effect, citation slot. |
| `sources.json` | — | — | — | Per-component citation slots, all `verified: false`, plus DRAFT status note. |
| `README.md` | — | — | — | This document. |

**Component maxima sum to 36:** 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 = 36.

## Directional (bride/groom) scoring convention

Some kootas are **asymmetric** in the two partners' classical roles. The product
captures partner roles **neutrally** — `role: "seeker" | "partner"` — and maps
them to the classical `bride` / `groom` roles via
`manifest.json → role_mapping` (default `seeker→bride`, `partner→groom`,
`confirmed: false`). This is the DEC-009a recommendation and **requires domain +
founder confirmation (OQ-2)**.

`manifest.json → directional` flags each component:

- **Directional (order matters):** `varna` (groom ≥ bride), `tara` (counted both
  ways then combined), `gana` (asymmetric 3×3 matrix, written groom-row /
  bride-column).
- **Symmetric (order irrelevant):** `vashya`, `yoni`, `graha_maitri`, `bhakoot`,
  `nadi`.

If the confirmed role mapping is the reverse of the default, the directional
tables (notably `gana_matrix.json`) must be interpreted/transposed accordingly —
see the note inside each directional file.

## Immutability & versioning

- A frozen pack is **never edited in place.** Any change to any table, score,
  mapping, or rule — including completing a citation that alters a value —
  requires a **new versioned directory** (e.g.
  `rules/ashtakoota_lahiri_classical_v2/`).
- The directory name **is** the `rule_pack_id`. Charts and reports stamp the
  exact `rule_pack_id` they were computed under (DEC-019); recomputing under a
  new pack is an explicit versioned recalculation, never a silent mutation.
- While a pack is `draft: true` it may still be revised in place *before first
  freeze*, but once it has produced any stored report it is immutable.

## Draft status & the domain-review gate

This pack is `draft: true` / `review_required: true`. Before it can serve a
user-facing report, ALL of the following must be true:

1. A named classical authority is fixed and every `sources.json` citation is
   completed with `verified: true` (OQ-1).
2. A Vedic-astrology domain expert has reviewed each table — especially the
   flagged high-variance ones — and signed off.
3. The founder has confirmed the tradition (`north_indian_ashtakoota`) and the
   seeker/partner → bride/groom `role_mapping` (OQ-2).
4. `draft` is set `false` in a **new frozen version** (not by editing this one
   post-freeze).

### High-variance tables to scrutinise during review

- **Yoni matrix** — diagonal `4` (same) and the seven mortal-enemy pairs (`0`)
  are the reliable values; all other cells are a documented `2` (neutral)
  placeholder. Friendly(3)/unfriendly(1) gradations must be transcribed from the
  cited source.
- **Vashya group matrix** — off-diagonal values vary by source; the canonical
  form is a 12×12 rashi-pair table. Half-signs (Sagittarius, Capricorn) assigned
  by dominant half.
- **Gana matrix** — confirm groom/bride orientation and Deva×Rakshasa = 1 vs 0.
- **Graha Maitri** — confirm the neutral-neutral = 3 band is used.

## Safety constraints (DEC-021)

- **Nadi** is *traditional constitutional compatibility* only. It must **never**
  be surfaced or worded as medical, genetic, fertility, pregnancy, progeny, or
  health information. See `nadi.json → safety_constraint`.
- **Yoni** interpretations apply only in a consensual adult romantic context and
  are never sexualized outside it.
- **Dosha cancellations** never fire unless explicitly enabled in
  `exceptions.json`, and every applied exception id is written into the report's
  calculation trace — no silent cancellation.
- Ashtakoota output is never usable as evidence for medical, psychiatric,
  employment, credit, insurance, or legal decisions.

## Related references

- `docs/DILCHAT_DECISION_LOG.md` — DEC-008 (Lahiri), DEC-009 / DEC-009a
  (rule-pack source & directionality), DEC-019 (score-family separation),
  DEC-021 (Nadi/Yoni/medical safety), OQ-1/OQ-2.
- `docs/DILCHAT_ASTROLOGY_ENGINE_SPEC.md` — engine that consumes this pack
  (nakshatra/rashi/pada boundary computation, ambiguous-time handling,
  calculation trace format).
