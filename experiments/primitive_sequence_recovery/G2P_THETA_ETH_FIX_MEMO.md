# /θ,ð/ Fidelity Fix — SCOPED DESIGN MEMO (candidate, not applied)

**Status: CANDIDATE / bridge-candidate only. Nothing applied. No re-derive, no re-freeze, no fresh prereg.**
Resonance / phonetic-fidelity refinement only — no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth /
ontology / Sanskrit-privilege claim. **Track B remains blocked. B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure,
not validated meaning.

Files: `varna_bridge_thfix.py` (candidate), `test_varna_bridge_thfix.py` (8 tests, passing). The frozen v1 bridge,
the retroflex bridge v2, and the v3 table are all UNCHANGED (asserted by the tests).

---

## 1. Current behavior and the exact bug

- **Where /θ,ð/ map now.** The G2P (`stage_a_prime_coverage`, `A_PRIME_EN`) emits a **single `th` phoneme for BOTH**
  the voiceless dental fricative `/θ/` (*thin, thought, path, faith*) **and** the voiced `/ð/` (*this, that, other,
  mother*). It **never emits `dh`**. The frozen bridge then maps `th → tha` (थ) — and `dh → dha` (dead, since `dh`
  is never emitted).
- **Why mapping to `tha` is wrong.** `tha` (थ) is the **aspirated dental STOP** (viṣāda / melancholy in the v3
  table). `/θ,ð/` are **fricatives**, and Sanskrit has **no dental fricative at all**. So the mapping is wrong on
  **manner** (fricative → aspirated stop) and lands on the wrong meaning-root. It also **over-triggers massively**:
  `the, this, that` are the three most frequent words in English, and *every* English `th` word (think, three,
  path, both, month, mother, father, breath, faith…) injects a spurious `tha` = **melancholy**.
- **Examples (current vs. correct place).** `the → tha`, `this → tha,sa`, `mother → ma,tha,ra`, `path → pa,tha`,
  `faith → tha`, `think → tha,na,ka`. Every one carries a wrong "melancholy" root.
- **Item-vocabulary note.** *None* of the 24 pole-DiD words, 12 B1.9 targets, or pole-sanity items/synonyms/
  opposites contain `th` (audit §3), so the bug never touched the frozen item packets — it is a **general-vocabulary
  over-trigger**, not a frozen-item corruption.

## 2. Proposed corrected mapping

- **Principle.** `/θ,ð/` are **dental fricatives**; Sanskrit lacks fricatives at that place, so the least-wrong
  target is the **dental UNASPIRATED stop** — `ta` (voiceless) / `da` (voiced) — matching **place** (dental), not
  the aspirate `tha`. **This explicitly moves OFF the aspirate series, so it does not create an aspiration rule.**
- **Bridge-only fix (no G2P change).** Because the G2P collapses `/θ/` and `/ð/` into one `th` phoneme, a
  bridge-only fix **cannot distinguish voicing**; it maps merged **`th → ta`** (voiceless dental stop — exact for
  `/θ/`, a voicing-only approximation for `/ð/`). `the → ta`, `this → ta,sa`, `path → pa,ta`.
- **Distinguishing `/θ/` vs `/ð/` (the fuller fix).** The faithful version — `/θ/ → ta` (voiceless), `/ð/ → da`
  (voiced) — requires the **G2P to emit a separate `dh` phoneme for `/ð/`** (ARPAbet-style TH vs DH), which this
  G2P does not do. The candidate **pre-wires `dh → da`** so that the moment a G2P upgrade emits `dh`, voiced `/ð/`
  routes correctly to `da` with no further change. Until then only `th → ta` fires.
- **Voicing caveat (honest).** With the merged phoneme, `ta` is exact for `/θ/` but mismatches voicing for `/ð/`
  (the/this → `ta` rather than `da`). By **token** frequency `/ð/` (function words) dominates, so a `da` default is
  defensible too; the recommendation is `ta` (the voiceless dental, the conservative "θ default") **plus** the
  pre-wired `dh → da` for the real distinction once the G2P supports it.
- **No accidental aspiration.** The override targets are strictly the **unaspirated** `ta`/`da`; tests assert no
  `tha/kha/pha/…` is ever introduced.
- **Composability.** The fix keys on the `th`/`dh` phonemes; the retroflex bridge v2 keys on `t`/`d` before `r` —
  **disjoint phonemes**, so they compose cleanly. `three` (`/θr/`) → `ta,ra` (NOT the retroflex `tta`, correctly,
  since `θr ≠ tr`); `drum` still → `ḍa,ra,ma`.

## 3. Impact audit (measured)

- **Frozen item sets: ZERO words change.** 0/24 pole-DiD, 0/12 B1.9 targets, 0 pole-sanity items and 0
  synonyms/opposites contain `th`. So applying this fix would require **no re-derivation of any frozen item**.
- **Which words change:** only general/future vocabulary containing `th` — pervasive there (the/this/that/think/
  three/path/both/mother/…), each moving `tha` → `ta`.
- **Prior reported results:** **unaffected.** No prior result (B1.4b′, B1.9 embedding, B1.8/B1.9 generation,
  pole-DiD) used any `th` word, and nothing is applied. This changes only **future** re-derivations, and only if
  promoted.
- **Interaction with the retroflex candidate:** none — disjoint phonemes (verified).

## 4. Tests (`test_varna_bridge_thfix.py`, 8, passing)

- **/θ/**: `thin→ta,na`, `thought→ta,ga,ta`, `path→pa,ta`, `faith→ta`.
- **/ð/**: `this→ta,sa`, `that→ta,ta`, `other→ta,ra`, `mother→ma,ta,ra`, `the→ta`.
- **No accidental aspiration**: no `tha/kha/pha/…` introduced; override is `{th:ta, dh:da}`.
- **Composes with retroflex v2**: `drum→ḍa,ra,ma`, `train→ṭa,ra,na`, `three→ta,ra` (θr not retroflex).
- **Zero frozen impact**: th-fix output == v1 for every frozen pole-DiD / target / pole-sanity word.
- **Regression — nothing applied**: frozen v1 bridge still `th→tha`, `dh→dha`; **bridge v2 unchanged** (still maps
  a bare `th` word to `tha` — the fix lives only in the candidate); **v3 table unchanged** (`tha` still = viṣāda —
  the phoneme fix does not touch the polarity table).

## 5. Status

- **Resonance / phonetic-fidelity refinement only** — it corrects *which sound maps where*; it makes **no**
  semantic-truth / ontology / Sanskrit-privilege claim and does not touch the content-level nulls.
- **Candidate / bridge-candidate only. NOT APPLIED.** v1 bridge, bridge v2, and v3 table all unchanged.
- **No re-derive, no re-freeze, no fresh prereg** in this memo.
- To go live (only on operator approval): pick `ta`-only (bridge-only) vs the G2P-distinguishing `/θ/→ta,/ð/→da`
  version → new bridge version + hashes → re-derive (0 frozen items) → re-freeze → fresh prereg before any test.

## 6. Guardrails

No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege claim. **Track B
remains blocked. B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure, not validated meaning.
