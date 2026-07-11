# Pole-Context Sanity Micro-Test — PREREGISTRATION / DESIGN (docs-only, DRAFT)

**Status: DESIGN / prereg DRAFT. No code, no scaffold, no run, no approval-flag change.** Nothing here is built or
frozen; this is the pre-specification to read **before** deciding whether to implement. `word_groups_approved` /
`classification_approved` remain `false`.

Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth /
ontology / Sanskrit-privilege claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked.
**Structure, not validated meaning.**

---

## 1. Purpose (one sentence)

Test whether the `fidelity_bundle_v1` binding/liberating **packets** are legible to LLM judges as descriptions of
the **inner experiential weather / source-condition** underlying a word held in two contrasting contexts — a direct
no-generation rating, **not** a definition check and **not** a synonym/opposite comparison.

## 2. Scope and exclusions

- **Words (3):** `happy`, `peace`, `love` — the clean/usable subset (approval table `3632c92`).
- **Excluded for now:** `longing` (asymmetric discriminating power), `devotion` (too many off-axis facets). Not in
  this micro-test.
- **No generation. No synonyms/opposites. No dictionary-fit question.** The only judge task is fit-rating an
  existing packet to a word-in-context.

## 3. Fixed materials (packets are context-invariant)

Each word's two packets are **fixed by its varṇa sequence** and do **not** change with context; only the context
changes, and the context sets which pole *should* fit. Packets below are read-only from the frozen v3 table
(`frozen/varna_polarity_table_v3.json`) via `varna_bridge_active` — quoted, not authored. **These will be verified
against the frozen table at implementation time (hash-pinned); they are not re-derived here.**

### happy — `ha, pa, pa, ya`
- **Binding context (Cb):** *"He was happy only because he had beaten his rival and could watch the man's face fall."*
- **Liberating context (Cl):** *"She was happy sitting alone at dawn, wanting nothing and comparing herself to no one."*
- **Binding packet (Pb):** `[ha]` outward/visible vision — fixation on the outward world · `[pa]` ghṛṇā — the fetter
  of hatred/revulsion · `[ya]` aviśvāsa — self-doubt that cannot commit.
- **Liberating packet (Pl):** `[ha]` intuitional vision — inner, subtle seeing · `[pa]` the upward turn — goodwill
  dissolving revulsion; anurakti → devotion · `[ya]` self-efficacy — steady trust in self and path.

### peace — `pa, ka`
- **Binding context (Cb):** *"He felt peace only once his opponents were silenced and no one could challenge him."*
- **Liberating context (Cl):** *"Peace settled in her on its own, needing no victory and no one's permission."*
- **Binding packet (Pb):** `[pa]` ghṛṇā — hatred/revulsion; downward pull · `[ka]` āśā as grasping/clinging hope —
  goaded toward an outcome.
- **Liberating packet (Pl):** `[pa]` the upward turn — goodwill dissolving revulsion · `[ka]` aspiring hope WITHOUT
  attachment — releasing the grip on the result.

### love — `la, va`
- **Binding context (Cb):** *"His love demanded she prove it daily, and curdled into jealousy whenever she looked away."*
- **Liberating context (Cl):** *"Her love asked for nothing back; it simply wished the other well and let him go."*
- **Binding packet (Pb):** `[la]` kruratā — cruelty; crude, cruel thought/behaviour · `[va]` ensconcement gone rigid
  — over-holding, clinging.
- **Liberating packet (Pl):** `[la]` compassion (karuṇā) that protects the vulnerable · `[va]` dharma — the
  sustaining principle; movement toward subtlety.

## 4. Design (2 × 2 within each word)

For each word there are **4 rating cells** — each of the 2 packets rated in each of the 2 contexts:

| cell | context | packet | notation |
|---|---|---|---|
| 1 | binding (Cb) | binding packet (Pb) | `fit(Pb|Cb)` |
| 2 | binding (Cb) | liberating packet (Pl) | `fit(Pl|Cb)` |
| 3 | liberating (Cl) | liberating packet (Pl) | `fit(Pl|Cl)` |
| 4 | liberating (Cl) | binding packet (Pb) | `fit(Pb|Cl)` |

3 words × 4 cells = **12 rating cells** per judge.

### Judge question (verbatim, the only question asked)
> **"How well does this packet describe the inner experiential weather or source-condition underlying this word in
> this context?"**
Rating scale: integer **0–6** (0 = not at all, 6 = extremely well). One number per cell. No other question is
asked — **no** "does this define the word", **no** synonym/opposite judgement.

### Judge protocol (anti-leak)
- **Blind to pole labels.** Packets are shown as plain facet text; the strings "binding", "liberating",
  "worldly", "spiritual", "correct/flipped pole", varṇa tags, and any system name are **stripped** from what the
  judge sees. Cells are presented in randomized order. (Blinding is a design requirement; the exact render is
  fixed at implementation, not here.)
- **Independent cells.** Each cell rated on its own; the judge is not told two packets are "opposites" or that a
  contrast is expected.
- **Multiple judges / replicates.** ≥2 independent judge models (or ≥2 seeds) so a per-cell mean is used, not a
  single draw. Exact N fixed at implementation.
- **Compliance capture.** Each rating must return a bare score; a per-cell free-text one-liner is captured only to
  audit compliance (see §7), not scored.

## 5. Primary statistic

**Per-word context–pole margin:**
```
context_pole_margin(word) =
    [ fit(Pb|Cb) - fit(Pl|Cb) ]      # in the binding context, binding packet should win
  + [ fit(Pl|Cl) - fit(Pb|Cl) ]      # in the liberating context, liberating packet should win
```
Range −12…+12 (two differences of 0–6 scores). A within-word, within-context contrast: because the **word is held
constant**, any margin is attributable to the **pole × context** interaction, not to lexical differences.

- **Per-word margin:** the value above for each of happy / peace / love.
- **Aggregate:** mean margin across the 3 words (and, secondarily, a sign test / mean of per-judge margins).
- **Individual cell means:** report all four `fit(·|·)` cell means per word (the raw 2×2), not only the margin.

## 6. Hypothesis and decision rule (pre-specified)

- **H1 (legibility):** `context_pole_margin > 0` — the correct-pole packet is rated a better source-condition fit
  in its matching context, in both directions.
- **H0 (null):** margin ≈ 0 — judges rate the two packets about equally regardless of context; the pole-context
  distinction is **not legible** under this packet-rating design.
- **Pre-specified read (direction, not a significance ritual on n=3):**
  - **Legible-positive** if aggregate mean margin is clearly > 0 **and** all 3 per-word margins > 0 **and** the
    effect survives with pole labels blinded.
  - **Null / not-legible** if aggregate margin ≈ 0 or the sign is inconsistent across words.
  - **Mixed** otherwise (e.g. 2/3 positive) → report as inconclusive; do not over-claim.
  - With only 3 words this is a **descriptive pilot**, not a powered inferential test; the decision rule is about
    direction and consistency, and any positive is a cue to scale the item count, not a conclusion.

## 7. Judge-compliance notes to capture (audit, not scored)

- **Leakage check:** the compliance one-liner must not name the system, the poles, "binding/liberating", or claim
  the packet "defines/means" the word; flag any cell where the judge answered a definition question instead of a
  source-condition question.
- **Refusal / hedge / out-of-range** scores flagged and handled per a pre-set rule (drop + re-draw, fixed at
  implementation).
- **Scale abuse:** all-6 or all-0 judges flagged (no discrimination).

## 8. Ambiguity notes (pre-registered, per the approval table)

- **happy, peace:** low ambiguity; sharp discriminators (`pa` revulsion↔upward-turn; `ka` grasp↔non-grasp).
- **love:** binding `la` = **cruelty** is a coarse fit for jealous love (source-condition is possessive control,
  not literal cruelty); the clinging `va` facet is expected to carry most of the binding signal. If love's margin
  is the weakest / only non-positive one, that is the **pre-registered expected** soft spot — not a post-hoc excuse.
- **General:** a positive margin driven mainly by the **liberating** direction (judges agreeing self-grounded
  contexts fit liberating packets) with a weak **binding** direction is a partial result; report both directional
  halves separately, not only their sum.

## 9. Interpretation constraints (binding)

- **A positive result means only source-condition / resonance-legibility to judges** — that these packets are
  *readable* as inner-weather descriptors matching a context. It does **not** prove ontology, semantic truth,
  Sanskrit privilege, generation utility, or any **word-specific** varṇa mapping (the packet is a bag of
  constituent-varṇa pole readings; the test cannot attribute the signal to any individual varṇa).
- **A null means** the pole-context distinction is **not legible** to judges under this packet-rating design —
  nothing more and nothing less.
- **Independent of the content nulls.** Whatever the outcome, **B1.4b′ remains `NULL_RETURN_BOTTOM`**, original
  B1.4b stays blocked, and Track B stays blocked. This micro-test does not reopen them; it measures rater
  legibility of a source-condition, not whether varṇas carry meaning. **Structure, not validated meaning.**

## 10. What implementation would add (only on approval — not done here)

A hash-pinned item file (3 words × 2 contexts × 2 packets, verified byte-equal to the frozen v3 facets), a blinded
render, a judge runner with the fixed question, a fresh `EVIDENCE_FREEZE_DECLARED` + this prereg frozen, and the
mapping labels (`mapping_era: fidelity_bundle_v1`). **None of that is built until you approve this design.**

## 11. Guardrails
Docs-only design/prereg — no code, no scaffold, no run, no approval-flag change. Resonance / phonetic-fidelity
refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege
claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated
meaning.**
