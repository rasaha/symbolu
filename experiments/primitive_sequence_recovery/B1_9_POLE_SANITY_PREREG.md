# B1.9 — Pole-Logic Sanity Test — PREREGISTRATION

**Status:** preregistration + implemented, mock-tested driver. **No generation. No readings. No Mistral/Qwen. No
`GENUTILITY_*`. No `ONTOLOGICAL_SIGNAL`.** Real run is **gated on operator sign-off of the WordNet
synonym/opposite table.**

**Readiness label: `B1_9_POLE_SANITY_DRIVER_READY_MOCK_TESTED`.**

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** No ontology, no Sanskrit privilege, no semantic-truth claim.

---

## 0. Purpose & scope

A **coherence check on the pole labels only.** For each target word `W`, take `W`'s OWN varṇa facet packets at the
referent-**correct** pole and at the **flipped** pole (the RAW facet text from the frozen v2 table), and have blind
judges rate 1–7 how **directly** each packet describes `W` + synonyms (same pole) and opposite/contrast words
(opposite pole). This tests only whether the two pole labels behave as **coherent, directional descriptors**.

**Explicitly NOT tested:** ontology, Sanskrit privilege, semantic truth, generation utility, or word-specific
varṇa mapping. Because there is **no generation** (judges rate raw table text, no LLM rewrites), the
contrastive-framing confound that made the pole-DiD inconclusive (`B1_9_POLE_DID_RESULTS.md`) cannot enter through
a generation layer; residual contrastive reading is handled by an explicit anti-contrastive instruction **and** an
audit.

## 1. Design (no generation — direct rating only)

For each `W`: two packets (`correct`, `flipped`) × candidate words in two role-groups:

| rate packet ↓ against → | **target + synonyms** (W's pole) | **opposite / contrast** (opposite pole) |
|---|---|---|
| **correct-pole packet** | cell ① expect HIGH | cell ④ expect LOW |
| **flipped-pole packet** | cell ② expect LOW | cell ③ expect HIGH |

## 2. Rating protocol

- **Judge prompt:** *"How directly does this facet packet describe this word (with its meaning)? Rate 1–7."*
- **Anti-contrastive instruction (enforced in the prompt):** *"Only DIRECT description counts. Do NOT give a high
  rating if the packet describes what the word overcomes, resists, is free from, opposes, or contrasts with — that
  is not a direct description and must be rated low."* The judge also labels each rating **direct** or
  **contrastive** (compliance audit; diagnostic).
- **Blinding:** a judge sees ONLY `{rating_id, packet, word, word_meaning}` — never the pole (correct/flipped), the
  role (target/synonym/opposite), or the item. Tasks are shuffled. Every candidate carries a WordNet sense gloss so
  ratings are sense-clear and **uniform** (no target-vs-distractor tell); `W`'s narrative context is used only to
  choose senses and is **not** shown.
- **Panel:** 3 judges, disjoint families (Llama-3.1-8B, Meta-Llama-3-8B, Gemma-2-9b), temperature 0.

## 3. TWO primary diagnostics (fixed in advance)

- `D_target   = mean(correct fit to W/synonyms) − mean(flipped fit to W/synonyms)`  — expect **> 0**
- `D_opposite = mean(correct fit to opposites)  − mean(flipped fit to opposites)`   — expect **< 0**
- **Diagnostic 1 — `INT = D_target − D_opposite`** — expect **> 0** (robust) if the pole labels are coherent.
- **Diagnostic 2 — `Cell ①` = correct-pole packet fit to target/synonyms** — the word-level fit number, reported
  with its own CI, its distance from the neutral midpoint 4, and its margin over `Cell ②` (flipped→target).

Report the four cell means (① ② ③ ④), `D_target`, `D_opposite`, `INT` and `Cell ①` with bootstrap CI95 + per-item
sign test, plus the anti-contrastive audit rate per cell.

## 4. Interpretation (fixed in advance — the INT-vs-Cell① rule)

- **`INT > 0` ALONE shows only pole-label / VALENCE coherence** (the two table columns carry opposite valence and
  judges rate matching-valence text as fitting). Necessary, **not** sufficient for word-level fit.
- **A HIGH `Cell ①` is REQUIRED** to claim the correct packet **directly fits the word-family** (well above the
  neutral midpoint 4 AND above `Cell ②`).
- **`INT > 0` but `Cell ① ` low ⇒ the test does NOT support word-level packet coherence** — the crossover is
  generic valence, not the packet describing its own word.
- **`INT ≈ 0` (CI straddles 0):** the pole labels do no directional work — informative negative.
- **`INT < 0`:** anti-coherent (the "flipped" pole fits better than the "correct" one).
- Even the strongest joint outcome (`INT>0` **and** `Cell①` high) is a **sanity/coherence pass only** — **no**
  ontology, semantic truth, Sanskrit privilege, `GENUTILITY_*`, or word-specific varṇa-mapping claim.
- **Audit caveat:** if the anti-contrastive audit shows high contrastive rates despite the instruction, a nonzero
  `INT` is discounted (contrastive credit, not direct fit). No terminal verdict under any outcome.

## 5. Item set & word groups

- **All 24 approved pole-DiD words** (`frozen/b1_9_pole_did_items.json`); packets reuse the approved canonical
  **consonant-only** varṇas at the two poles — **no new derivation**.
- **Synonyms (target 4/word):** **PRIMARY WordNet noun synset ONLY** — tight, same-sense. Cross-synset fill is
  **deliberately not done** (that is what produced `lock→curl` / `terror→brat`, which came from *other* synsets).
  Words with fewer primary-synset synonyms are **flagged `NEEDS_MANUAL_REPLACEMENT`**, not padded with wrong senses.
- **Opposites (target 4/word):** **TRUE WordNet antonyms of `W` and its synonyms ONLY** — direct contrast. The
  **opposite-pole item-word pool is NO LONGER used** (it made `INT` measure generic binding/liberating valence
  rather than word-level contrast). Verb-only antonyms (e.g. `agitate`) are flagged for replacement with a noun.
- **Operator curation via overrides (anti-circularity):** the operator curates same-sense synonyms + true antonyms
  in **`frozen/b1_9_pole_sanity_overrides.json`** (`word → {synonyms:[…], opposites:[…]}`), which the builder
  **merges and treats as authoritative, surviving rebuilds**. Every short / verb-antonym / wrong-sense slot is
  flagged `NEEDS_MANUAL_REPLACEMENT` and must be resolved. Then set `word_groups_approved: true`. The gate refuses
  to run until approval; do not revise after seeing any rating.

### 5b. Vowel-omission limitation (inherited)

Consonant-only. Vowels `VOWEL_NO_PROFILE` and dropped; adding vowels needs a sourced table + new representation +
separate prereg — not here.

## 6. Counts

24 items × 2 packets × (1 target + up to 4 synonyms + up to 4 opposites) rating tasks × 3 judges. Exact counts
depend on the approved group sizes (printed by `prepare` and in the run manifest).

## 7. Guardrails

No generation/readings; only direct fit-rating. No `run_out/` committed. No `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`,
no ontology/semantic-truth/Sanskrit-privilege claim, no word-specific mapping claim. **B1.4b′ remains
`NULL_RETURN_BOTTOM`.** Structure, not validated meaning.

---

## Final report

- **Files:** `B1_9_POLE_SANITY_PREREG.md`, `run_b1_9_pole_sanity.py`, `test_run_b1_9_pole_sanity.py`,
  `build_b1_9_pole_sanity_scaffold.py`, `frozen/b1_9_pole_sanity_items.json` (DRAFT — needs sign-off),
  `frozen/b1_9_pole_sanity_scaffold.json`, `B1_9_POLE_SANITY_RUNPOD_COMMANDS.md`.
- **Readiness:** `B1_9_POLE_SANITY_DRIVER_READY_MOCK_TESTED`.
- **Primary statistic:** `INT = D_target − D_opposite`.
- **Real run gated on `word_groups_approved: true`** (currently false — DRAFT).
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.9 pole-logic sanity test preregistered and driver mock-tested. No generation; direct packet rating only;
synonym/opposite table requires operator curation + sign-off before any run. No GENUTILITY terminal label. No
B1.10. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
