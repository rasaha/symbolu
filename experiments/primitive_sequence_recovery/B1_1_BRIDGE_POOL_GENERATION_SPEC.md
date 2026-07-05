# B1.1 Bridge-Pool Generation — SPECIFICATION (spec only, do not implement)

## 1. Scope and non-claims

**Spec only.** Defines how a future B1.1 bridge pool would be generated from the resolved binding/liberating
lexicon and how the arms (A, R_same, R_deranged, R_domain, S, D, C, X) draw from it. **Implements nothing:**
no bridge pool generated, no model, no generation, no scoring, no LLM judge. Does **not** modify B1, change
the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology / Sanskrit
privilege / semantic-truth claim. **Structure, not validated meaning.**

## 2. Inputs

- `experiments/primitive_sequence_recovery/b1_1_experimental_contrastive_lexicon_draft.json` — 34 resolved
  consonants, each with `binding_expression`, `liberating_expression`, `functional_operation`,
  `contrast_boundary`, `source_attested_pole`, `source_note`. Validator 18/18.
- The G2P→varṇa decomposition used in B1 (word → varṇa sequence).
- The frozen seeds discipline (generation, output-randomization, packet, bootstrap) as in B0/B1.

## 3. Why the old bridge pool failed

B1's 64-phrase pool was **non-contrastive**: 34×2=68 candidate glosses collapsed to **64** because 4
liberated Sanskrit poles were exact duplicates, and most positive entries fell into a few affect basins. A
random draw (R) therefore landed in the same affective neighborhood as the "correct" draw, so the blind
judge could not separate **A from R** → `RANDOM_OR_SCRAMBLED_MATCHES`. The resolved lexicon removes exact
duplicates (validator) and reframes poles as binding/liberating expressions. **But contrastivity is
necessary, not sufficient** — a contrastive pool with an arbitrary word→mapping link still yields A ≈ R.
That is what **`R_deranged`** tests; the bridge design must make that test fair and hard.

## 4. One-to-one bridge generation rule

- The bridge pool is **generated from the JSON**, never hand-written.
- **Each (varṇa, expression) source maps to exactly one bridge phrase.** No two sources may collapse to the
  same or a near-duplicate phrase.
- Target: **68 distinct phrases** (34 binding + 34 liberating), or the subset an arm actually surfaces — with
  **no collapsed duplicates** (the exact defect that reduced 68→64 in B1).
- Every bridge phrase **preserves** the `functional_operation` and at least the primary `contrast_boundary`,
  so a wrong draw is a *distinguishably wrong operation*, not a generic mood.

## 5. Binding/liberating language constraints

- Use **binding/liberating expression** language only (from `binding_expression` / `liberating_expression`).
- **No** good/bad, positive/negative, vice/virtue framing.
- **Do not** hand-write generic virtue phrases (e.g. bare "compassion", "clarity", "humility").
- Bridge phrases must remain **experimentally testable**, **not** spiritual-truth claims.
- Preserve `functional_operation` and `contrast_boundary` in each phrase's derivation.

## 6. A-arm bridge construction

- For a target word: **G2P → varṇa sequence** (the word's own varṇas).
- Select each varṇa's **resonance expression** (its `liberating_expression` + `functional_operation`;
  binding/liberating conditioning as pre-registered) and **compose in order** into a conditioning phrase.
- A is the **real, word-specific** mapping: it is derived *from this word's varṇas*, preserving each varṇa's
  operation and boundary. Composition order matters (sequence-sensitive).
- A carries the `contrast_boundary` so the conditioning is a specific operation set, not generic evocation.

## 7. R_same construction

- **Random draw from the same revised pool**, matched to A in count, length, and style, but **not** the
  word's own varṇas.
- Same fluency and register as A (fluent, same-style) — **wrong only in that it is not word-derived.**
- Pin the random seed. Tests whether *any* draw from the contrastive pool is as good as the word-specific one.

## 8. R_deranged construction

- Apply a **fixed derangement π** over the word list (π(w) ≠ w); word *w* receives the **real A mapping of
  π(w)** (another word's word-derived bridge).
- **Mapping quality held maximal**; only the word→mapping **fit** is broken.
- Pin the derangement seed. **This is the crux control**: if A cannot beat R_deranged, word-specific fit
  carries no signal (the H2 claim fails), regardless of contrastivity.

## 9. R_domain construction

- Fluent symbolic mapping sampled from a **domain deliberately mismatched** to the target word; same
  length/grammar/style/wrapper as A.
- **Pre-register** per-word forbidden domains (semantically native to the word) and allowed R domains
  (deliberately distant). Guards against researcher degrees-of-freedom in "distant."
- Tests whether **semantic fit** matters while fluency is held constant.

## 10. S scrambled construction

- **Scramble the intra-word varṇa order** before deriving the bridge — same varṇa *set*, broken *sequence*.
- Tests whether internal order/structure matters. (In B1, A **beat** S — order mattered; R was the failure.)

## 11. D / C / X interaction

- **D (dictionary):** the word's plain dictionary meaning — independent of the bridge pool.
- **C (surface):** surface facts / length-style control — independent of the bridge pool.
- **X (neutral):** no conditioning — the floor.
- These three are **not** drawn from the bridge pool; they bound the pool-based arms from below and against
  plain meaning.

## 12. Required bridge validator

Before any generation, a bridge validator must assert:
- **one-to-one**: no two (varṇa, expression) sources collapse to the same/near-duplicate bridge phrase; count
  == expected; no exact duplicates.
- **language**: binding/liberating vocabulary only; **no** good/bad/positive/negative/vice/virtue tokens;
  `functional_operation` + `contrast_boundary` preserved.
- **R fluency parity**: R_same / R_deranged / R_domain match A in length/style/register — **strong and
  fluent, not ugly or nonsense** (an ugly R is an unfair control).
- **blinding**: no arm/word/model/seed label leaks into judge-visible text (structural check, as in B1).
- **no source-lexicon or B1 artifact modified.**

## 13. Persistence requirements

Closing the B1 gap (raw outputs were RunPod-only, hash-bound but unrecoverable):
- commit a **small, leak-scanned, blinded sample** (30–50 packets), deliberately including **R-beats-A** and
  **A-beats-R** cases;
- store the **full** raw outputs + packets in durable storage (not an ephemeral pod), **hash-bound** in the
  repo;
- the packet builder must **refuse to finish** unless the committed sample + its hash exist.

## 14. Relationship to the blocked embedding gate

- The **real embedding gate remains `BLOCKED_DEPENDENCY_UNAVAILABLE`** (huggingface.co egress-denied) and is
  **still owed**.
- The **local lexical audit passed surface-level screening only** (`PASS_LOCAL_SURFACE_ONLY`, 2 soft flags
  accepted-with-rationale) — this is **not** a contrastivity pass.
- **Before final B1.1 freeze, one of:** (A) the real embedding gate runs and passes, or (B) the prereg
  **explicitly documents** that the embedding gate was unavailable and the weaker local fallback was used,
  with the **elevated R-risk** (deep synonymy undetected) recorded.

## 15. Go / no-go decision before bridge generation

Bridge generation **must NOT start** until **all** hold:
- JSON validator passes — **met** (18/18);
- local lexical audit adjudicated — **met** (`PASS_LOCAL_SURFACE_ONLY`);
- **contrastivity assurance** — **NOT met**: either embedding-gate PASS (currently BLOCKED) **or** an explicit
  prereg decision to accept the weaker local fallback with documented elevated risk;
- R-control construction rules (§7–§9) + bridge validator (§12) + persistence (§13) specified and approved.

**Current status: NO-GO by default** — the contrastivity-assurance condition is unmet. Owner decision
required (run embedding gate when access is available, or accept the weaker fallback in prereg).

## 16. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             SPEC ONLY
Bridge pool generated: NO
Embedding run:         NO (still BLOCKED)
Model/generation/scoring/judging: NO
Source lexicon:        NOT modified
Go/no-go:              NO-GO by default (contrastivity assurance unmet)
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity /
non-synonymy repair remains **necessary but not sufficient**; **`R_deranged` remains the crux**.

**Structure, not validated meaning.** Spec only; the B1 verdict stands and Track B remains BLOCKED.
