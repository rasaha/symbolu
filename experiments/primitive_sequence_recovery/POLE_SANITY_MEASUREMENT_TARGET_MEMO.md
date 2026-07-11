# Pole-Sanity — Measurement-Target Clarification (design memo, docs-only)

**Docs-only. No generation, no run, no approval-flag change, no re-derive, no frozen artifact touched.**
`word_groups_approved` stays `false`; the pole-sanity run stays **paused** (per the manual approval review,
`c6010ad`: 0 word groups approve as-is, 14 reject/rebuild, and all 24 packets fail a *literal dictionary* match).
Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth /
ontology / Sanskrit-privilege claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked.
**Structure, not validated meaning.**

---

## 1. The question this memo answers

> Are v3 packets intended to **directly describe the English word's dictionary meaning**, or to describe the
> **sub-semantic experiential weather / source-condition / resonance behind the word-in-context**?

**Answer: the latter.** A v3 packet is *not* a definition of the word. It is the pole-reading of each constituent
varṇa — a description of the **inner condition or "weather" a word can carry**, split into a binding (other-
conditioned, downward) reading and a liberating (self-grounded, upward) reading. The manual review measured the
packets against the *wrong* yardstick (dictionary fit) and correctly found 0/24 — because that was never what the
packet encodes. This does **not** upgrade the packet to "true"; it only fixes which question it should be rated
against. Structure, not validated meaning.

## 2. Why "does this packet describe this word?" is too literal

The old judge question —

> *"How directly does this packet describe this word?"*

— presumes the packet is a **gloss**. But the packet is a bag of varṇa **pole-readings**, and the same word can sit
at either pole depending on its source-condition. A dictionary asks *what the word denotes*; the pole framing asks
*from what inner condition the word arises here*. Rating denotation is a category error against a construct that
was built to rate condition. Concretely, three failure modes of the literal question:

- **It has no room for the two poles.** A single word (e.g. *happy*) has one dictionary meaning but **two**
  packets (binding vs liberating). "How directly does this describe *happy*?" can't distinguish them — both are
  "about happiness" — so the judge is forced to score denotation overlap, which is near-constant across the pole
  and tells you nothing about pole logic.
- **It rewards lexical echo, not resonance.** Under the literal question a packet scores well only if its words
  *look like* the target's dictionary gloss. The review showed lexical echo is 0/24 **by construction** — so the
  literal question guarantees a null that is an artifact of the yardstick, not a finding about the mapping.
- **It collapses context.** The whole point of the pole design is that *the same word in two contexts* lands at
  two different poles. A denotation question is context-blind (a dictionary entry doesn't change with the
  sentence), so it discards exactly the signal the test exists to measure.

### The `happy` example (why the literal question fails)

| | source-condition | which pole |
|---|---|---|
| **binding happy** | happiness *conditioned by others* — praise, comparison, rivalry, winning over someone, envy/hatred of a rival's loss; joy that needs an external scoreboard | worldly_binding |
| **liberating happy** | inward, self-grounded joy — self-love, contentment that does not depend on others' approval or defeat | spiritual_liberating |

Both are "happy" in the dictionary. A literal *"does this packet describe happy?"* cannot separate them. But
*"which inner condition is this happiness arising from?"* separates them cleanly — and **that** is the axis the
varṇa poles were built to express. The construct is a **source-condition classifier**, not a synonym detector.

## 3. Proposed revised rating target (no-generation)

Replace the literal question with a **source-condition** question:

> **"How well does this packet describe the inner experiential weather / source-condition underlying this word in
> this context?"**

Properties that make this the right no-generation target:

- **Two-pole discriminating.** The binding and liberating packets now have *different* correct answers for the
  *same* word, because the context fixes which source-condition is in play. The judge rates fit-to-condition, not
  fit-to-dictionary.
- **Context-load-bearing.** The context sentence is now a required input (it selects the pole), so the test
  actually exercises the pole logic instead of averaging it away.
- **Still no generation.** It remains a **direct rating** of an existing packet against a word-in-context — no
  text is generated, so it stays inside the no-generation regime and does not reopen Track B.
- **Falsifiable in the honest direction.** If varṇa poles carry *no* source-condition signal, a judge will rate
  the correct-pole and flipped-pole packets **equally** well against the context — a null. The revised question
  can *fail*; it is not rigged to pass. (And a pass would still be **resonance legibility**, never meaning-truth.)

**What this is not.** It is not a claim that the source-condition reading is *correct*, *ancient*, or *real*. It is
a claim about **which question a rater should be asked** so the answer is informative rather than a yardstick
artifact. B1.4b′ stays `NULL_RETURN_BOTTOM`; a favorable pole-sanity result would be a *legibility* measurement,
not a validation of meaning.

## 4. Why this reframes the paused run (not why to un-pause it)

The pole-sanity run stays paused. But the review's three "not ready" findings now read differently:

- **"0 word groups approve as-is / 14 reject."** Those were computed for a **synonym/opposite** design (§5 argues
  that design is the weaker test anyway). Under the source-condition target, the item unit is a **word + two
  contrasting contexts**, not a word + curated synonym/opposite lists — so the WordNet-curation blockers
  (missing opposites, proper-noun noise like *Oliver Lodge*, wrong-POS verbs) largely **dissolve**, because they
  were artifacts of harvesting antonyms, not of the pole logic.
- **"All 24 packets fail a literal dictionary match."** Expected and irrelevant under the revised target — the
  packet was never a dictionary entry.

This is a **reframing to consider**, not an instruction to build. No new items, no run, no flag change here.

## 5. Proposed same-word two-context examples (design only)

Five words, each with a **binding / other-conditioned** context and a **liberating / self-grounded** context,
the expected pole, and why the paired-context design tests pole logic better than synonym/opposite sets. **These
are illustrative candidates only — not authored items, not frozen, not approved, not to be run.**

### 5.1 happy
- **Binding context:** *"He was happy only because he had beaten his rival and could watch the man's face fall."*
- **Liberating context:** *"She was happy sitting alone at dawn, wanting nothing and comparing herself to no one."*
- **Expected pole:** binding → `worldly_binding`; liberating → `spiritual_liberating`.

### 5.2 love
- **Binding context:** *"His love demanded she prove it daily, and curdled into jealousy whenever she looked away."*
- **Liberating context:** *"Her love asked for nothing back; it simply wished the other well and let him go."*
- **Expected pole:** binding → `worldly_binding`; liberating → `spiritual_liberating`.

### 5.3 peace
- **Binding context:** *"He felt peace only once his opponents were silenced and no one could challenge him."*
- **Liberating context:** *"Peace settled in her on its own, needing no victory and no one's permission."*
- **Expected pole:** binding → `worldly_binding`; liberating → `spiritual_liberating`.

### 5.4 longing
- **Binding context:** *"His longing fixed on possessing her, restless and grasping until she was his."*
- **Liberating context:** *"Her longing turned inward and upward, a pull toward the Great that asked for no object."*
- **Expected pole:** binding → `worldly_binding`; liberating → `spiritual_liberating`.

### 5.5 devotion
- **Binding context:** *"His devotion was performed for the congregation's eyes, hungry for their approval."*
- **Liberating context:** *"Her devotion was quiet and unwitnessed, offered for its own sake and no one's applause."*
- **Expected pole:** binding → `worldly_binding`; liberating → `spiritual_liberating`.

### 5.6 Why paired-context beats synonym/opposite sets

- **It isolates the pole variable.** The **word is held constant**; only the source-condition changes. Any
  difference in packet-fit is therefore attributable to the **pole**, not to lexical differences between a word
  and its synonyms/antonyms. Synonym/opposite sets confound "different pole" with "different word."
- **It removes the WordNet-curation failure surface.** No antonym harvest → no missing-opposite items (the 14
  rejects), no proper-noun noise (*Oliver Lodge*), no wrong-POS verbs. The blocker set that paused the run is a
  property of antonym harvesting, not of pole logic.
- **It makes context load-bearing and the test falsifiable in the honest direction.** The pole is fixed by the
  sentence, so a null (judge rates both packets equally against the context) is a **real** null about the mapping,
  not an artifact of thin synonym lists. A synonym/opposite design can fail for a boring reason (no clean
  opposites); a paired-context design fails only if the pole signal is genuinely absent.
- **It is a cleaner minimal contrast.** Two cells (same word × two contexts × correct-vs-flipped packet) is a
  tighter within-word contrast than a word-vs-many-neighbors comparison, and needs no external lexicon at all.

**Caveat (honest).** Even a clean pass under §3–§5 would show only that varṇa poles are **legible as
source-condition descriptors to a rater** — resonance legibility. It would **not** show that varṇas carry meaning,
that the source-condition reading is true, or that any Sanskrit privilege obtains. Structure, not validated meaning.

## 6. Guardrails
Docs-only — no generation, no run, no approval-flag change, no re-derive, no frozen artifact modified. Resonance /
phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology /
Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
