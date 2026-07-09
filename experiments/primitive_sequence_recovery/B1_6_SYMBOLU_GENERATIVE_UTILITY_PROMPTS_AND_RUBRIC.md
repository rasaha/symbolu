# B1.6 — Symbol-U Generative Utility — Prompts & Judge-Rubric Specification

**Status:** Operationalization spec (docs-only). Freezes prompts, arms, rubric, blind packaging, and controls so
B1.6 becomes runnable later. **No code, no generation run, no judging, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

Subordinate to: `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` (`c1f5028`).
Related: `B1_5_THREE_CLUE_WORD_RECOVERY_PREREG.md` (`cde0a9c`),
`B1_4B_PRIME_SCREENING_OPERATOR_COMMANDS_EXECUTED.md` (`880ad1a`, NULL),
`SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.

---

## 1. Purpose

This document **operationalizes B1.6** by freezing the exact generation prompt templates, the generation arms,
the judge rubric, the blind-packaging format, and the leakage/overclaim controls — so the experiment *can* be
run later under a proper freeze. **It does not run the experiment**, does not generate any text, does not judge
any output, and does not declare an evidence freeze. It is preparation only.

## 2. Relationship to the prereg

This spec is **subordinate to** `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md`. It **does not change** the prereg's
terminal labels, thresholds, hypotheses, or claims — it only fills in the concrete prompt/rubric machinery the
prereg calls for. Where this document and the prereg could appear to differ, **the prereg governs**. The prereg's
terminal labels (`GENUTILITY_SYMBOLU_BEATS_BASELINES`, `..._BEATS_PLAIN_ONLY`, `..._COLLAPSES_TO_GENERIC_STRUCTURE`,
`..._RANDOMIZED_SYMBOLU_MATCHES`, `..._LLM_BASELINE_WINS`, `..._NO_PREFERENCE`,
`..._HALLUCINATION_OR_OVERCLAIM_FAIL`, `..._INCONCLUSIVE`, `..._INVALID_LEAKAGE`) remain the only outcome
vocabulary; this spec adds none.

## 3. Target item format

Each evaluation item is a frozen record:

- **`item_id`** — stable unique id.
- **`target_text`** — the object to interpret (one word/phrase/name/term).
- **`target_type`** — one of: `common_word` / `abstract_concept` / `name` / `symbolic_term` /
  `brand_product_term`.
- **`neutral_context`** *(optional)* — a short, arm-neutral framing sentence, identical across all arms if
  present (e.g. "This is a personal name."); must not hint at any interpretation.
- **`forbidden_hints`** — explicit list of things no arm may be given for this item (e.g. the "intended"
  reading, an etymology gloss when etymology is disallowed, any evaluative adjective).
- **`category` / `stratum`** — stratification key (abstract vs concrete; task family) for balanced sampling and
  per-stratum reporting.

Items are **frozen before generation**; no post-hoc edits (prereg §6, §16).

## 4. Generation arms (frozen)

- **A. `SYMBOLU_SCAFFOLD`** — candidate; frozen Symbol-U scaffold prompt (§10).
- **B. `PLAIN_PROMPT_BASELINE`** — plain interpretation, no framework (§7). The floor.
- **C. `GENERIC_STRUCTURED_PROMPT_BASELINE`** — matched generic interpretive structure, **no varṇa content**
  (§8). The decisive control.
- **D. `RANDOMIZED_SYMBOLU_CONTROL`** — the scaffold with shuffled/relabelled varṇa profiles (§11).
- **E. `SEMANTIC_LLM_BASELINE`** — ordinary semantic/conceptual analysis (§9). The benchmark.
- **F. `SYMBOLIC_SYSTEM_BASELINE`** *(optional; disabled by default)* — an alternate symbolic system (§12);
  enabled only by explicit later approval; **never** Symbol-U evidence.

## 5. Shared generation constraints (all arms)

Every arm MUST use:

- the **same generator model**;
- the **same temperature**;
- the **same max tokens** (identical output budget — no arm, especially A, gets more room);
- the **same target item** and any `neutral_context`;
- the **same output format** (§6);
- **no arm labels** anywhere in the generated output;
- **no claim of truth, ontology, Sanskrit authority, or special revelation** in the output;
- **no mention of "Symbol-U", "varṇa", or the scaffold's name** in the final output — such terms may appear
  **only** inside the scaffold arm's *prompt instructions* (arms A and D), never in the produced text.

Any violation is a leakage event (§18) → item voided or `GENUTILITY_INVALID_LEAKAGE` per the prereg.

## 6. Output format (every generation, every arm)

Exactly, in this order:

- **Title:** one short phrase.
- **Interpretation:** **120–180 words**.
- **Practical reflection:** exactly **2 bullet points**.
- **Caution:** **1 sentence** stating limits/uncertainty.

The identical format across arms enforces length parity and removes format as a giveaway. Outputs violating the
word/bullet bounds are regenerated (before any judging) or flagged and excluded — never silently kept.

## 7. Prompt template — `PLAIN_PROMPT_BASELINE`

```
You are a thoughtful interpreter. Give a thoughtful, grounded interpretation of the following item.
Do not use any special framework, system, or lens — just your own careful reading.

Item: {TARGET_TEXT}
{NEUTRAL_CONTEXT}

Respond in EXACTLY this format:
Title: <one short phrase>
Interpretation: <120–180 words>
Practical reflection:
- <bullet 1>
- <bullet 2>
Caution: <one sentence stating the limits/uncertainty of this interpretation>

Do not claim your reading is objectively true, ancient, or authoritative. Do not name any system.
```

## 8. Prompt template — `GENERIC_STRUCTURED_PROMPT_BASELINE`

```
You are a thoughtful interpreter. Interpret the following item using this general interpretive structure.
This is an ordinary organizing structure, not a special or esoteric system.

Item: {TARGET_TEXT}
{NEUTRAL_CONTEXT}

Work through these lenses internally, then synthesize:
- surface meaning of the item;
- emotional tone it evokes;
- metaphorical associations;
- a practical reflection;
- a note of caution.

Respond in EXACTLY this format:
Title: <one short phrase>
Interpretation: <120–180 words>
Practical reflection:
- <bullet 1>
- <bullet 2>
Caution: <one sentence stating the limits/uncertainty of this interpretation>

Do not claim your reading is objectively true, ancient, or authoritative. Do not name any system.
```

*(Matched to the Symbol-U arm in structure and length pressure; contains no varṇa/Symbol-U content.)*

## 9. Prompt template — `SEMANTIC_LLM_BASELINE`

```
You are a knowledgeable interpreter. Give a strong, conventional interpretation of the following item,
drawing on ordinary semantic and conceptual analysis, common cultural associations, and — only if allowed
for this item and if you actually know it — etymology. Do NOT invent etymology or facts.

Item: {TARGET_TEXT}
{NEUTRAL_CONTEXT}
Etymology permitted for this item: {ETYMOLOGY_ALLOWED}

Respond in EXACTLY this format:
Title: <one short phrase>
Interpretation: <120–180 words>
Practical reflection:
- <bullet 1>
- <bullet 2>
Caution: <one sentence stating the limits/uncertainty of this interpretation>

Do not use any esoteric framework. Do not claim your reading is objectively true, ancient, or authoritative.
Do not name any system. If you are unsure of a fact or etymology, say so rather than inventing it.
```

## 10. Prompt template — `SYMBOLU_SCAFFOLD`

```
You are an interpreter using a structural lens as a heuristic scaffold — NOT as truth.
Use the following pre-computed structural profile of the item to shape an interpretation. Treat the scaffold as
one possible interpretive lens, a way to generate a reading — never as proof that sound carries meaning.

Item: {TARGET_TEXT}
{NEUTRAL_CONTEXT}

Structural scaffold (pre-computed; use as a lens only):
- Phoneme / varṇa sequence: {VARNA_SEQUENCE}
- Varṇa profile / polarity table: {VARNA_PROFILE_TABLE}
- Interpretive dimensions (CSR / STL frame): {CSR_STL_FRAME}
- Transformation rules: read the sequence in order; let each element's profile color the reading; let the
  ordered transformation (earlier elements conditioning later ones) shape a coherent arc; synthesize into a
  single interpretation tailored to THIS item.

Instructions:
- Use the scaffold as an interpretive lens to produce a specific, grounded reading of the item.
- Build the reading from the scaffold's structural profile, not from the dictionary definition of the item.
- Do NOT claim this proves meaning, is objectively true, ancient, or authoritative.
- Do NOT mention "Symbol-U", "varṇa", scaffolds, or any system name in your output.

Respond in EXACTLY this format:
Title: <one short phrase>
Interpretation: <120–180 words>
Practical reflection:
- <bullet 1>
- <bullet 2>
Caution: <one sentence stating the limits/uncertainty of this interpretation>
```

Placeholders `{TARGET_TEXT}`, `{VARNA_SEQUENCE}`, `{VARNA_PROFILE_TABLE}`, `{CSR_STL_FRAME}` (and
`{NEUTRAL_CONTEXT}`) are filled from the **frozen** Stage A / Stage A′ decomposition and the **frozen** profile
table; **no per-item tuning**. The scaffold text, profile table, and template are hash-frozen before generation.

## 11. Prompt template — `RANDOMIZED_SYMBOLU_CONTROL`

Identical to §10 **except** the `{VARNA_PROFILE_TABLE}` (and, per the frozen randomization seed, the
sequence→profile assignment) is **shuffled/relabelled** so the specific varṇa content is destroyed while the
template, length pressure, and register are preserved.

```
[Identical to SYMBOLU_SCAFFOLD (§10), but {VARNA_PROFILE_TABLE} is replaced by a shuffled/relabelled profile
table drawn under the frozen randomization seed. The model is given no indication that the scaffold is
randomized — it is presented exactly as an interpretive scaffold.]
```

- The model is presented this scaffold **as if it were a genuine interpretive scaffold** (no hint of
  randomization in the prompt).
- The **judge remains blind** — the randomized-control output is packaged and rated exactly like any other arm.
- The output must **not** reveal that the scaffold was randomized, and (like arm A) must not name any system.

## 12. Optional prompt — `SYMBOLIC_SYSTEM_BASELINE` (placeholder only; disabled)

A future, explicitly-enabled alternate-symbolic-system baseline (e.g. astrology / tarot / I Ching / numerology
style) of **matched form and length**. **Disabled by default.** Placeholder only:

```
[DISABLED BY DEFAULT — requires explicit later approval and its own freeze.]
Interpret {TARGET_TEXT} using {ALT_SYMBOLIC_SYSTEM} as an interpretive lens (not truth), producing the same
fixed output format (§6). Not Symbol-U evidence; cannot emit any Symbol-U positive label.
```

If ever enabled, it contextualizes a Symbol-U effect against a *different* symbolic scaffold and can never stand
in for a Symbol-U win.

## 13. Blind packaging format

Each generation is packaged for judging as:

- **`item_id`**
- **`arm_blinded_id`** — an opaque per-run code (e.g. `G3`), carrying **no arm name** and no systematic mapping
  the judge can infer; the arm↔code map is held out of the judge package.
- **`generation_text`** — the output, with any residual system-name/register giveaways scrubbed (§18).
- **No arm name** anywhere in the package.
- **Randomized output order** within each item (fixed by the frozen seed), so position leaks nothing.

**Target visibility:** the **target IS shown to the judge**, with justification: the rubric requires judging
**specificity to the target** and **non-genericity** (§15), which is impossible without seeing the target.
Showing the target is the same for all arms and leaks no arm identity, so it does not compromise blinding.

## 14. Judge instructions (blind)

```
You are a blind evaluator. You will see an item (the target) and several interpretations of it, each with an
opaque code. You do NOT know which method produced which interpretation, and you must not guess or reward any
apparent "system".

For each interpretation, rate it on the rubric (§15), 1–7 per dimension. Reward interpretations that are:
- coherent and well-formed;
- specific to THIS target (not a reading that would fit any word);
- interpretively rich and genuinely useful;
- appropriately humble about their own limits.

Penalize interpretations that are:
- generic fluff that could apply to anything;
- overclaiming or asserting mystical/ancient certainty;
- factually hallucinated (invented etymology, false claims);
- verbose without added substance.

Do not reward mystical or esoteric register for its own sake. Do not try to identify the method. Rate only what
is on the page, against the target.
```

## 15. Rubric dimensions (1–7 each)

Positive dimensions:

- **coherence**
- **specificity to target**
- **interpretive richness**
- **practical usefulness**
- **non-genericity**
- **creativity / aesthetic quality**
- **internal consistency**
- **caution / epistemic humility**

Penalty dimensions (higher = worse; modeled as penalties, see §16):

- **overclaim penalty** — asserting truth/authority/ancient certainty.
- **hallucination penalty** — fabricated etymology / false factual claims.

## 16. Composite score

- **Positive composite** = mean of the eight positive dimensions (§15), on the 1–7 scale (pre-declared equal
  weighting unless the prereg's frozen weighting says otherwise).
- **Penalties** = the two penalty dimensions, **subtracted** (or separately modeled) to yield a
  **penalty-adjusted composite**.
- **Both are reported:** the **raw positive composite** AND the **penalty-adjusted composite**. If the Symbol-U
  advantage exists only in the raw composite and vanishes once penalties are applied → this is the prereg's
  `GENUTILITY_HALLUCINATION_OR_OVERCLAIM_FAIL` condition, not a win.

## 17. Pairwise preference

Blind forced-choice (win / tie / loss) on these contrasts:

- **Symbol-U vs plain**
- **Symbol-U vs generic-structured**
- **Symbol-U vs randomized-Symbol-U**
- **Symbol-U vs semantic-LLM**
- **semantic-LLM vs generic-structured** *(sanity contrast: locates the baselines relative to each other)*

Each comparison yields a win/tie/loss; win rates and their CIs feed the prereg's terminal-label logic (a
Symbol-U win requires beating plain **and** generic-structured **and** randomized **and** semantic-LLM).

## 18. Leakage controls (breach → `GENUTILITY_INVALID_LEAKAGE`)

Explicitly forbidden:

- **arm names shown to judges** (only opaque `arm_blinded_id`);
- **generated output saying "Symbol-U"** (or "varṇa" / scaffold/system names) — scrubbed; residual → void item;
- **generated output claiming ancient authority, truth, or special revelation**;
- **post-hoc editing** of items, prompts, outputs, or rubric after any score is seen;
- **changing prompts after scores** are collected;
- **using different models or temperatures across arms**;
- **allowing the Symbol-U arm a longer output budget** than the others (max tokens and the 120–180-word bound
  are identical for all arms).

## 19. Pilot settings

- **20–30 target items.**
- **5 arms** (A–E; F disabled).
- **1 generation per item per arm** for a plumbing pilot, or **2–3** for stability.
- **LLM-as-judge allowed for the pilot only** (a different model from the generator).
- **No terminal label / no claim** may be emitted from the pilot; it validates plumbing, blinding, leakage
  scrubbing, rubric discrimination, and a synthetic positive control (a deliberately better vs worse pair).

## 20. Full-run settings

- **50–200 target items** (frozen, stratified per §3).
- **Human blind judges preferred** for any terminal claim.
- **≥3 independent ratings per output** where feasible; IRR reported.
- **Pre-frozen** targets, prompts (all arms, incl. scaffold + template), randomization seed, blind packaging,
  and judge rubric.
- **Evidence freeze declared before any generation** — the same gated discipline used for B1.4b′. No generation
  before the freeze; report the terminal label as-is.

## 21. Readiness labels (for this spec)

- **`B1_6_PROMPTS_RUBRIC_READY`** — prompts, arms, rubric, packaging, and controls all specified and internally
  consistent; scaffold placeholders defined; judge spec complete. (This document's state — subject to a real
  scaffold freeze at run time, §23.)
- **`B1_6_PROMPTS_RUBRIC_BLOCKED_UNFROZEN_SCAFFOLD`** — the concrete frozen `{VARNA_SEQUENCE}` /
  `{VARNA_PROFILE_TABLE}` / `{CSR_STL_FRAME}` content is not yet hash-frozen for the target set.
- **`B1_6_PROMPTS_RUBRIC_BLOCKED_JUDGE_SPEC`** — judge protocol / IRR plan / rating logistics not settled.
- **`B1_6_PROMPTS_RUBRIC_INVALID_LEAKAGE`** — a spec-level leakage hole is found (e.g. an arm-identifying
  giveaway baked into a template).

**Assigned label for this document: `B1_6_PROMPTS_RUBRIC_READY`** — the templates, arms, rubric, blind
packaging, and controls are fully specified and mutually consistent. The *instantiation* of the frozen scaffold
content for a specific target set (and the final judge logistics) is a separate run-time freeze step; until that
is done for a run, that run is `..._BLOCKED_UNFROZEN_SCAFFOLD`.

## 22. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning claim. No claim that sound objectively encodes meaning. No rescue of B1.4b′. No reuse-as-
positive of any prior null. A generative-utility win is **scaffold usefulness on this task only**. Original
B1.4b remains blocked. Track B remains blocked. **Structure, not validated meaning.**

## 23. Validation checklist

- [x] **Prompts frozen** — exact templates for A–E given verbatim (§7–§11); F placeholder-only, disabled (§12).
- [x] **Arm parity** — same model / temperature / max tokens / target / output format across all arms (§5).
- [x] **Output length parity** — identical 120–180-word + 2-bullet + 1-sentence format for every arm (§6); no
  extra budget for the Symbol-U arm (§18).
- [x] **Judge blindness** — opaque `arm_blinded_id`, no arm names, randomized order (§13, §14, §18).
- [x] **Randomized control present** — `RANDOMIZED_SYMBOLU_CONTROL` specified, presented as a genuine scaffold,
  judge blind (§11).
- [x] **Generic structured baseline present** — `GENERIC_STRUCTURED_PROMPT_BASELINE`, matched, no varṇa content
  (§8).
- [x] **No generation run** — this document generates no text.
- [x] **No evidence freeze** — no freeze declared; run-time freeze is a separate gated step (§20).

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md`
- **Commit hash:** (recorded on commit below)
- **Readiness label:** `B1_6_PROMPTS_RUBRIC_READY` (run-time scaffold instantiation is a separate freeze step).
- **Prompt/rubric spec summary:** five frozen generation arms (A `SYMBOLU_SCAFFOLD`, B `PLAIN_PROMPT_BASELINE`,
  C `GENERIC_STRUCTURED_PROMPT_BASELINE`, D `RANDOMIZED_SYMBOLU_CONTROL`, E `SEMANTIC_LLM_BASELINE`; F
  `SYMBOLIC_SYSTEM_BASELINE` disabled), all under matched model/temperature/length and a fixed output format
  (Title / 120–180-word Interpretation / 2 bullets / 1-sentence Caution); a 1–7 rubric over eight positive
  dimensions plus overclaim and hallucination penalties, reported as both raw and penalty-adjusted composites;
  blind packaging with opaque arm codes, randomized order, and target visible to judges (needed for specificity/
  non-genericity); strict leakage/overclaim controls; and pairwise preference on the five decisive contrasts.
- **No generation run was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is not a semantic-decoding or ontology claim** — it operationalizes a *generative-utility-of-a-scaffold*
  test only; no validated meaning, no Sanskrit privilege, no `ONTOLOGICAL_SIGNAL`.

> B1.6 prompt/rubric spec drafted docs-only. No generation run. B1.4b′ remains NULL_RETURN_BOTTOM. Original
> B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
