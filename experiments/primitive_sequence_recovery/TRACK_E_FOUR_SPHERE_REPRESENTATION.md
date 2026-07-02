# Track E — Four-Sphere Varṇa Representation (candidate artifact note)

**Data-artifact note. Nothing run, scored, or validated.** No experiment, no LLM/scorer call, no
network, no model download. `frozen/manifest.json` remains **NOT_READY** (and is not edited by
this file); the psr runner remains **NOT_RUN**; Stage A is untouched; **Track B remains BLOCKED**;
no `ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege. Nothing here
reinterprets the Track C or D0 negatives.

## What this is

`track_e_varna_sphere_lexicon.json` is a **standalone candidate input representation** for Track E
(the varṇa boundary-constraint test). It stores, for each of the 34 consonant varṇas, a
**four-sphere boundary vector**:

1. **physical** — body / action / material expression,
2. **mental** — emotion / feeling / impulse,
3. **intellectual** — cognition / discernment / meaning-formation,
4. **spiritual** — deeper direction (bondage, liberation, ascent, fall, dharma, mokṣa).

It is **separate from and does not replace** the existing flat varṇa gloss
(`frozen/realization_en_gloss.json`). It is a *new, additional* representation to be tested against
the flat gloss — not an upgrade assumed to be better.

## Provenance (read this first)

The classical source (the P.R. Sarkar acoustic-root varṇa/vṛtti table) supplies a **single
acoustic-root meaning** per consonant (e.g. `na` → moha, `pha` → bhaya, `ka` → hope). It **does
not** supply a four-sphere table. The four sphere fields are therefore a **researcher interpretive
expansion** of those roots. The JSON marks this explicitly and non-negotiably:

```json
"source_supplies_four_spheres": false,
"representation_status": "researcher_interpretive_extraction",
"validation_status": "unvalidated_candidate_representation"
```

This matters because researcher-authored content is the highest-degrees-of-freedom, highest-
contamination channel in the project (failure mode **F5**, researcher-authored, from the
concept-resolver circularity audit). The representation buys *faithfulness to the claim* (the
theory does assert layered content); it does **not** buy independence, and it **raises** the
evidentiary bar rather than lowering it.

## Leak rule (built into the data)

The classical **`root` column itself names likely target candidates** — moha, bhaya, kāma, tṛṣṇā,
lobha/greed, fear, desire, attachment, envy, hatred, ego. Sending those roots (or the varṇa names,
or the surface word) into a blinded scoring packet would leak the answer. Therefore every entry
carries:

- `packetize_root: false` — the root is **never** placed in a scorer packet;
- `leak_risk: low | medium | high` — `high` wherever the root directly names a plausible candidate.

In the current draft: 23 `high`, 10 `medium`, 1 `low`. A real run's pre-send leak scan must strip
surface words, varṇa names, and root-names in addition to honoring `packetize_root`.

## Key convention

Keys match `frozen/assignment.json` (the 34 consonant varṇas: `ka … ksha`, including `nga`, `nya`,
`ssa` for the retroflex/sibilant forms). Transliteration variants are recorded per entry in an
`aliases` field (e.g. `ssa` → `["śa","ṣa"]`, `nga` → `["una","ṅa"]`) rather than introducing a
conflicting key.

## Status: candidate draft, not frozen

As shipped this file is an **unfrozen candidate draft**. Before any real Track E run it must be:

1. **authored/reviewed blind to the target word list** (the sphere text must not be tuned to the
   words it will later be scored against), with **inter-annotator agreement recorded**;
2. **hash-pinned and frozen** as a Track E input artifact (a `track_e_*` bundle separate from
   `frozen/manifest.json`, which is never edited for this);
3. **gated by the four-sphere-specific controls** — at minimum a **flat-gloss baseline (G)** that
   the four-sphere arm must beat (else the spheres add nothing: `FOUR_SPHERE_ADDS_NOTHING`), a
   **four-sphere scrambled baseline**, **sphere-ablation baselines** (to detect a single sphere —
   especially the Barnum-prone *spiritual* sphere — carrying all the apparent effect), and a
   **Barnum four-sphere baseline (I4)**. See `TRACK_E_IMPLEMENTATION_PILOT_PLAN.md` §5–§8 (to be
   updated) and `PREREG_TRACK_E_VARNA_BOUNDARY_CONSTRAINT.md`.

None of that is done or authorized here. This note and the JSON are a representation artifact only.

## What this does NOT do

- Not a Track E result and not validation. No word, context, candidate, or boundary has been
  scored.
- Not a rescue or reinterpretation of Track C (dictionary-referent recovery: no robust signal) or
  D0 (experiential-weather recovery: `LLM_PILOT_NO_SIGNAL`). The four-sphere idea is at most a
  *lead* for why flat glosses underperformed; using it requires a fresh pre-registered test and
  cannot retroactively convert those negatives.
- Not a step toward unblocking Track B. Researcher-authored spheres, English mediation, and
  shared-source dependence keep the non-circularity problem unsolved (if anything harder).

---

Four-sphere varṇa JSON created as an unvalidated Track E candidate representation. No experiment has been run. Track B remains blocked. Structure, not validated meaning.
