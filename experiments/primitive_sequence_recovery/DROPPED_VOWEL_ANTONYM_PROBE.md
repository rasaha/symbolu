# Dropped-Vowel / Antonym-Pair Theory Probe (mechanical + docs only)

**Mechanical-only analysis over the existing frozen artifacts.** No embeddings, no scoring, no
external assets, no LLM, no new experiment — only canonical-sequence (consonant-skeleton)
collision analysis over `frozen/`. No Stage A change, no `manifest_v2`, no READY. `manifest.json`
remains NOT_READY; the runner remains NOT_RUN.

Basis: `REVIEW_ONTOLOGY_ARTIFACTS.md` (where these collisions were first found), the frozen
`assignment.json` / `word_list.json` / `meaning_reference.json`, and the corrected ontology
(`CANONICAL_PRIMITIVE_REPRESENTATION.md`).

---

## Mechanical findings (computed from frozen artifacts)

Grouping **all** corpus words by their canonical opaque sequence (varṇa → atom via τ) yields
exactly **3 collision groups**, every one an antonym or gender pair:

| canonical skeleton | words (meaning) | what distinguishes them | dropped by consonant-only |
|---|---|---|---|
| `na·ra` | nara (man) / **nārī** (woman) | gender: a-stem masc. vs ī/ā fem. | vowel length + final gender vowel |
| `va·da·ya` | vidyā (knowledge) / **avidyā** (ignorance) | **a-privative** negation | initial vowel `a` |
| `ha·ma·sa` | himsā (violence) / **ahimsā** (nonviolence) | **a-privative** negation | initial vowel `a` |

(**bold** = the member excluded via `exclude_flag=true`.) Among the **107 active** words the
collision count is **zero** — the exclusions did their job. The a-privative is the productive
pattern: both `X`/`aX` pairs present in the corpus (`vidyā`/`avidyā`, `himsā`/`ahimsā`) are
exact meaning-flips created solely by the prefixed vowel `a`.

---

## 1. What exactly collapses under consonant-only canonical representation?

The frozen `assignment.json` maps only the **34 consonant varṇas** to opaque atoms; vowels,
vowel length, the a-privative prefix, anusvāra, and visarga are **not varṇas in this table** and
are therefore **dropped** during decomposition. For the three pairs above, the *entire*
meaning-distinguishing signal lives in exactly those dropped elements, so the two words map to
the **identical opaque sequence** and become indistinguishable in principle.

## 2. Why are these cases theoretically important?

They are a clean **natural experiment**: same consonant skeleton, opposite (or gender-flipped)
meanings. They let us localize *where the contrastive meaning lives* without any model or
embedding — purely from the ontology. The answer is unambiguous: **in the vowels/prefix**, not
in the shared consonants.

## 3. Do they show dropped vowels/prefixes carry meaning-flipping information?

**Yes — decisively, by construction.** vidyā↔avidyā and himsā↔ahimsā differ *only* by the vowel
`a`; nara↔nārī differ *only* by vowel length/gender vowel. The consonants are identical in each
pair, the meanings are opposite/contrastive. So the meaning-flipping information is carried
**entirely** by material the consonant-only representation discards. This is an existence proof,
not a statistical claim.

## 4. What does this imply for the primitive-sequence recovery design?

- The current design tests a **proper subset** of Symbol-U: the *consonant-only* claim. It is
  **structurally blind** to any contrast borne by vowels/prefixes.
- Excluding the colliding members was **correct and necessary** — including them would inject
  guaranteed-unrankable items (identical query, different target) and depress any recovery
  metric for reasons unrelated to whether varṇas carry meaning.
- Therefore any recovery result (positive or null) from this corpus speaks only to the
  consonant subset, with the vowel-borne contrasts removed by design.

## 5. Does this weaken consonant-only Symbol-U testing?

**It bounds it — cuts both ways, honestly:**
- *Against a strong consonant claim:* for these words the consonant primitives carry **zero**
  meaning-distinguishing content. This is a direct **counterexample to any "consonants
  dominate / first consonant is the driver" reading** — nara/nārī share every consonant yet
  differ in meaning; vidyā/avidyā differ by a single vowel.
- *In defense of the theory:* Symbol-U (per the project's own "varṇa = written form" stance)
  includes **vowels** as varṇas. A consonant-only null is thus **not** a falsification of the
  full theory; it may simply reflect a lossy operationalization. A fair test must include the
  vowel varṇas.

Net: consonant-only testing is **incomplete**, and its scope must be stated explicitly whenever
results are reported.

## 6. Does it argue for a future vowel-aware / prefix-aware model?

**Yes.** The principled next ontology would treat **vowels (a, ā, i, ī, u, ū, …), the
a-privative, vowel length, anusvāra, and visarga as first-class varṇas** with their own opaque
atoms. Then:
- antonym pairs like vidyā/avidyā get **distinct** canonical sequences (avidyā = ⟨a⟩ + vidyā),
- the corpus need not exclude them,
- and the full written-form claim (not just the consonant subset) is actually tested.
This is a **design extension**, obtainable with no new assets — it only requires extending
`assignment.json` and re-decomposing `word_list.json`. (It does **not** rescue the *semantic*
blockers: Sanskrit vectors and a non-circular concept resolver remain unavailable; Track B stays
blocked regardless.)

## 7. Does it affect the interpretation of Track C?

**Yes — it narrows the scope of the Track C negative.** Track C (`en_gloss`) ran on the
consonant-only sequences with the three pairs excluded, and found **no robust semantic signal**.
That negative therefore applies to the **consonant-only** hypothesis on this corpus — it does
**not** falsify vowel-inclusive Symbol-U, because the model literally could not see the
vowel-borne contrasts these pairs demonstrate exist. The honest Track C statement must read:
"no robust signal *for the consonant-only rendering*," not "no signal for Symbol-U."

## 8. Fatal flaw or bounded limitation?

**Bounded limitation, not fatal.**
- *Corpus-level:* small — only 3 of 110 words collide, and they are excluded; the active corpus
  is collision-free.
- *Theory-level:* significant but bounded — it proves the consonant-only operationalization is
  lossy and cannot represent an entire class of real Sanskrit semantic contrasts (a-privatives,
  gender). It caps what consonant-only results can claim, and it points to a concrete, asset-free
  fix (a vowel-aware ontology).
It is **not** fatal to Symbol-U (the vowels it drops are themselves varṇas the full theory
covers), and it is **not** a defect in the pipeline (the freeze/audit correctly caught and
excluded the collisions).

---

## Conclusion

The three excluded collisions (`vidyā`/`avidyā`, `himsā`/`ahimsā`, `nara`/`nārī`) are a
mechanical, model-free demonstration that **meaning-flipping information in Sanskrit can live
entirely in vowels/prefixes** that the current **consonant-only** ontology discards. Two honest
consequences follow simultaneously: (a) it is a **counterexample to consonant-dominance** for
those words, and (b) it shows the consonant-only test is a **lossy proper subset** of the theory,
so the Track C negative must be scoped to "consonant-only rendering," not to Symbol-U as a whole.
The remedy is a **vowel-aware ontology** (asset-free, a future design extension), which would let
antonym pairs be represented distinctly — though it changes nothing about the still-blocked
*semantic* channels (Sanskrit vectors, non-circular concept resolver) or Track B.

> structure, not validated meaning.
