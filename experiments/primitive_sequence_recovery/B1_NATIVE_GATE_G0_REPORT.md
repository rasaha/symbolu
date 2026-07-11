# B1 — Native Gate-G0 Recomputation (Sanskrit word-specificity arm, docs/data-only)

**Gate verdict: `NATIVE_GATE_G0_PASS`.** The native Sanskrit **confirmatory consonant backbone** now supports a
clean word-specificity experiment that was previously **blocked** at the old 11-varṇa prose-packet gate. **Not a
polarity test.** No judges, no semantic scoring, no prose authoring, no preregistration, no experiment. Packets use
**only** confirmatory consonant rows (`source consonant_v3_1`, scope `CONFIRMATORY_BACKBONE`); authored-provisional
vowels/anusvāra/visarga are excluded. Selection uses **only structural distinctness**, never semantic fit.
**Structure, not validated meaning.** B1.10's pole-legibility negative (−2.78) and the qualitative guarded prior are
preserved. Data: `native_gate_g0/`.

## 1. The old Gate G0 (reconstructed)

- **Criteria:** K=6; every selected word must have ≥1 unique discriminating facet; max facet-Jaccard ≤ **0.34**,
  mean ≤ **0.20**; no best-effort set; caps never relaxed; exhaustive enumeration of the valid pool.
- **Why it failed:** the facet render map covered **only 11 varṇas** (`ba da ga ka la ma na pa ra ta tta`), so
  **21 of 37** candidate words were invalid, and — with `ra` alone in 9 of 16 valid words — **no** size-6 subset
  had a per-word unique facet. Status: `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`.
- **Preserved for the native gate:** K=6, the Jaccard caps, per-word-uniqueness, no-cap-relaxation, exhaustive
  pool enumeration, and the facet↔varṇa bijection (Jaccard on consonant sets == facet-Jaccard).
- **Revised (substrate changed):** packets are built from the **native Devanāgarī consonant backbone (33
  confirmatory units, not 11 rendered)**; and three controls are **strengthened** — C5/C6 length-non-identifying,
  C8 same-valence inclusion, C10 rare-only-uniqueness flag. **The gate was strengthened, not weakened.**

## 2. The representational blocker is removed

| | old (English prose packets) | native (confirmatory backbone) |
|---|---|---|
| renderable pole-bearing units | **11** | **33** |
| eligible candidate words | 16 valid | **107** |
| size-6 sets satisfying the gate | **0** | **17,009** |

## 3. Candidate eligibility & packets

Eligible = deterministic round-trip parse; 2–4 distinct confirmatory consonants; complete consonant packet (no
non-backbone unit); no contradictory mapping (none exist post-refreeze); no English-G2P path; dictionary meaning
exists; **not** selected for semantic plausibility. Words with missing vocalic ṛ remain eligible **only** because
the packet is explicitly consonant-only and ṛ (a vowel) never enters it — recorded per word. **107 eligible
candidates.**

## 4. Selection (systematic, non-semantic)

Procedure: enumerate eligibles → consonant-set features → pairwise Jaccard → rank a **distinctness-core pool** of 20
by lowest mean overlap (structural, deterministic) → **exhaustively enumerate all C(20,6)** → keep sets meeting all
criteria → deterministic rank (length-non-identifying, then same-valence, then max/mean Jaccard, then rare-only,
then alphabetical). **The search does not begin from any proposed set.**

**Selected set (only because it is structurally optimal):**

| word | Devanāgarī | consonant packet | valence (balance label) |
|---|---|---|---|
| aśva | अश्व | ś, v | neutral |
| bala | बल | b, l | positive |
| bhaya | भय | bh, y | negative |
| duḥkha | दुःख | d, kh | negative |
| gaja | गज | g, j | (unlabeled) |
| megha | मेघ | gh, m | (unlabeled) |

**Max pairwise Jaccard = 0.0, mean = 0.0** — the 12 consonants are **completely disjoint**; every word's entire
packet is unique. Uniform length (all 2 consonants) → **length/consonant-count cannot identify any word**. Contains
a same-valence pair (bhaya/duḥkha). **No** word is identifiable by a single rare consonant. (Deduplicated packets;
no identical or trivially-equivalent packets.)

## 5. Distinctiveness statistics

- Set-level: per-word unique feature ✔; no identical packets ✔; max Jaccard 0.0 ≤ 0.34 ✔; mean 0.0 ≤ 0.20 ✔;
  length-non-identifying ✔; same-valence pair ✔; rare-only cues none ✔.
- Pairwise matrix over the 20-word core pool: `native_gate_g0/pairwise_distinctiveness_matrix.json`.
- 17,009 eligible sets → the gate is comfortably satisfiable, not a knife-edge pass.

## 6. Control feasibility (all constructible)

| control arm | feasible | how |
|---|---|---|
| true packet | ✔ | the frozen consonant-backbone packets |
| cross-word mismatch | ✔ | pair each word with another member's packet |
| scrambled packet | ✔ | reassign packets across words / permute feature order |
| random varṇa-assignment | ✔ | structure-preserving permutation of the 33 consonant→pole map |
| packet-length matched | ✔ | uniform length in the selected set (trivially matched) |
| same-valence comparisons | ✔ | bhaya/duḥkha (both negative) |
| consonant-frequency matched | ✔ | corpus consonant frequencies computable + matchable |
| no per-word polarity selection | ✔ | both poles fixed per word by construction |
| blind word-identity matching | ✔ | forced-choice: match packet → word within the set |
| no open-ended plausibility endpoint | ✔ | endpoint is forced-choice accuracy, not "sounds plausible?" |

## 7. Validation

`test_b1_native_gate_g0.py` (9): only confirmatory consonant rows used; no vowel/marker pole in any packet; no
English-G2P import; merged lexicon + parser unchanged; deterministic; **eligibility independent of valence** (valence
is a balance label only); every selected word satisfies the gate; prior G0 constants preserved. All pass.

## 8. What this does and does not establish

- **Establishes:** the word-specificity arm that B1.10 left **blocked at Gate G0** is now **representationally
  testable** on the clean consonant backbone — the substrate change (native Devanāgarī, 33 vs 11 units) removed the
  exact obstacle. This is **distinct** from the resolved pole-legibility question (−2.78) and is **not** a polarity
  test.
- **Does not establish:** any word-specific signal. The gate is a **feasibility** result; the development-grade
  qualitative review's guarded prior (valence-dominated, generic) stands, and only a preregistered blind
  matching test with the §6 controls could decide it.

## Gate verdict & next action

**`NATIVE_GATE_G0_PASS`.** Next action: **draft a native Sanskrit word-specificity preregistration using only the
frozen consonant backbone** — a blind forced-choice packet→word matching design over the selected distinct set (and
sibling distinct sets for replication), with the true / cross-word-mismatch / scrambled / random-varṇa-assignment /
length- and consonant-frequency-matched / same-valence controls, no per-word polarity selection, and a forced-choice
accuracy endpoint (no plausibility judgement). Vowels stay out of the confirmatory arm until their provenance is
raised above `AUTHORED_PROVISIONAL`.
