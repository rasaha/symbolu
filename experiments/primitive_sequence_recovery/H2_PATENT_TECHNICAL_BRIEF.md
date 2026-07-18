# Patent-Facing Technical Brief — Symbolic-Resonance Generation-Conditioning Stack

*Docs-only technical brief for patent counsel / collaborators. No code change, no model call, no generation, no scoring, no result change.*

---

## 1. Title

**A Computer-Implemented Deterministic Symbolic-Conditioning Pipeline for Constructing Format-Matched, Controllable Generation Prompts from Phoneme-Derived Structural Units**

## 2. One-paragraph summary

The system is a **computer-implemented, deterministic pipeline** that converts an input word into an ordered sequence of phoneme-derived structural units via grapheme-to-phoneme (G2P) mapping, assigns each unit a **positional role**, looks up frozen descriptor fields for each unit from a fixed data table, condenses these into a controlled process paraphrase using fixed templates and a frozen bridge vocabulary, and finally assembles a set of **format-matched conditioning prompts** — one "real" arm plus several control arms (random, scrambled, surface-only, neutral, dictionary-only) that share an identical wrapper and differ only in a single conditioning slot. Every stage is deterministic, auditable, and runs **without any machine-learning model call**; interpretive inspection layers relate the intermediate output to a frozen dictionary anchor and to a frozen synonym-attribute inventory. The pipeline is an **engineering/inspection apparatus**; it makes **no claim** that the symbolic units carry meaning, that the conditioning improves generation, or that any linguistic ontology is validated.

## 3. Problem addressed

Prompt-conditioning today is typically ad hoc: a single hand-written instruction is prepended to a task, with no principled way to (a) derive the conditioning **deterministically** from properties of a target word, (b) hold prompt **format constant** while varying only the conditioning content, or (c) supply matched **control conditions** that isolate whether any observed effect is attributable to the specific conditioning content versus mere text injection, surface phonetics, or a dictionary gloss. The apparatus addresses these by making conditioning **derivation deterministic and reproducible**, by enforcing a **single-slot-varying** prompt construction across a fixed control set, and by providing **frozen, blind-authored** intermediate tables so the pipeline is fully auditable and testable.

## 4. Technical mechanism

1. **G2P unitization.** The input word is converted to a phoneme sequence (e.g., ARPAbet via a pronunciation dictionary); each phoneme is mapped (approximately, and flagged as such) to a symbolic unit key in a **frozen data table**. True-G2P-only: absence triggers a loud abort with no spelling/roman fallback.
2. **Positional role assignment.** Deterministic rules assign each unit a role from its position (first consonant = onset/seed; final consonant = transformer; interior consonants = unresolved; vowels = field). An **opt-in experimental variant** additionally lets a word-initial vowel take a seed role; the default behavior is unchanged.
3. **Frozen descriptor selection.** For each role, the apparatus selects a descriptor field (e.g., a "binding" or "liberating" pole string/object) **read directly from the frozen table** — never invented; missing entries are marked.
4. **Templated synthesis.** A fixed template plus a **frozen bridge vocabulary** (one paraphrase per descriptor) produces a single deterministic process sentence; unmapped descriptors render an explicit unresolved token and are never filled.
5. **Interpretive inspection (non-scoring).** Two independent inspection modules relate the synthesis to (a) a frozen dictionary anchor → a relation label, and (b) a frozen synonym-attribute inventory → per-attribute support labels with explicit evidence paths. Neither emits a score.
6. **Format-matched prompt assembly.** A wrapper with a single conditioning slot is instantiated across a fixed **arm set** (real / random / scrambled / surface-only / neutral / dictionary-only); only the slot content differs. Output is a set of prompts — never a generated completion.

## 5. Layer stack summary

| Layer | Function | Output |
|---|---|---|
| **L1** | G2P unitization + positional role + frozen descriptor emission | ordered units, roles, descriptors, approximate/missing flags |
| **L2** | Templated synthesis over a frozen bridge vocabulary | one deterministic process paraphrase; explicit unresolved tokens |
| **L3** | Interpretive dictionary-anchor relation (inspection-only) | relation label (aligns / partially / diverges / unresolved) + matched terms |
| **L4** | Synonym-attribute attribution (inspection-only) | per-attribute support labels + explicit evidence paths (no aggregate) |
| **L5** | Format-matched prompt construction | six single-slot-varying conditioning prompts (no model call) |

## 6. What is implemented

- **L1/L2** deterministic extraction and synthesis.
- **L2 bridge coverage** (full descriptor inventory covered by frozen paraphrases).
- **L3** dictionary-bridge **inspection** (relation labels, frozen local anchors, no runtime lookup).
- **L4** synonym-attribute **attribution inspection** (per-attribute labels + evidence paths, no aggregate score).
- **L5** **no-model** prompt construction across the six-arm control set (identical wrapper, single-slot variation).
- **Experimental vowel positional polarity** as an **opt-in, non-default** variant (default behavior byte-identical).
- All implemented inspection layers are deterministic and unit-tested; no model call or network lookup is required for the implemented inspection path.

## 7. What is not yet evaluated

- **No model generation, no human judging, no scoring** has been performed.
- A future generation-evaluation **pre-registration exists as a document only** and is **not approved for execution**.
- No integration of the inspection layers (L3/L4) or the experimental vowel variant into any scored path.
- Consequently there is **no measured claim** of generation quality, steerability, or preference improvement.

## 8. Why this may be patent-relevant

Potentially useful technical elements for counsel to evaluate, independent of any semantic theory:
- A **deterministic derivation of prompt-conditioning content from G2P-derived positional structure** of an arbitrary input word, using a frozen descriptor table and fixed templates.
- A **single-slot-varying, format-matched multi-arm prompt-construction method** with built-in matched controls (random / scrambled / surface-only / neutral / dictionary-only) enabling apples-to-apples comparison.
- **Frozen, blind-authored intermediate tables** (bridge vocabulary, dictionary anchors, attribute inventories) that make the pipeline reproducible and auditable, with explicit unresolved/missing handling rather than fabrication.
- **Non-scoring interpretive attribution with explicit evidence paths** (support-term ← emitted-phrase ← positional-role), providing traceability without an aggregate metric.
- An **opt-in positional-polarity mode** toggling per-unit role assignment while guaranteeing default-output invariance.

## 9. Claim-theme handles (for counsel to shape; not legal claims)

- **Method:** deriving a conditioning string from an input token by G2P unitization → positional role assignment → frozen-table descriptor selection → templated synthesis.
- **Method:** constructing N prompts sharing an identical wrapper and differing only in one conditioning slot, where the slot is populated from {structure-derived, randomized, permuted, surface-only, neutral, lexicon-derived} sources to form matched controls.
- **System/apparatus:** modules L1–L5 with frozen data tables and deterministic, model-free operation.
- **Data-structure:** frozen bridge/anchor/attribute tables with explicit unresolved/missing markers and blind-authoring provenance metadata.
- **Feature:** configurable, default-invariant positional-role mode (vowel field-only vs. positional-polarity).
- **Feature:** traceable attribution output with per-item evidence paths and no aggregate score.

## 10. Cautions for counsel

- The apparatus is described **purely as engineering**. It asserts **no** semantic-truth, ontology, linguistic-universal, or "Sanskrit-privilege" claim; drafting should avoid any such language.
- **No efficacy/utility has been measured** — do **not** state or imply that the conditioning improves generation, steerability, or quality. Internal informed-negative prior stands (prior correctness-degradation result; prior null/negative controls remain valid).
- Certain intermediate mappings are **approximate** (G2P→unit) and are flagged as such; a natural-language "a-" prefix maps via the pronunciation dictionary to a diphthong (e.g., ARPAbet `EY`), not a Sanskrit short vowel — avoid claims tying spelling to meaning.
- Some illustrative examples are **fixture-based** (not from a natural pronunciation dictionary) and must not be presented as empirical results.
- Prior-art considerations: G2P, template NLG, and prompt-wrapping are individually known; novelty should be framed around the **specific deterministic derivation + matched-control single-slot construction + frozen-auditable-table** combination.
- Freeze/versioning: any evaluation is gated behind a documented readiness process; nothing herein should be represented as validated or evaluation-ready.

---

**Guardrails.** No ontology validation. No Sanskrit privilege. No semantic-truth claim. No generation-utility claim. No model-result claim. No Track G rescue. No Track B unblock. Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`). Track B remains **BLOCKED**. Prior PSE negatives remain valid. Track F prior remains `CORRECTNESS_DEGRADED`. Frozen manifest remains `NOT_READY`.

**Structure, not validated meaning.**
