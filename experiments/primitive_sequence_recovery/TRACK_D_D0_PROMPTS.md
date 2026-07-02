# Track D — D0 LLM Prompt Templates (docs only; not executed)

**Templates for a future D0 run. No LLM was called; no scoring occurred.** These are drafts to be
reviewed before any approved run. `manifest.json` NOT_READY; runner NOT_RUN; Stage A untouched;
Track B BLOCKED. Placeholders in `{{ }}`. All calls must return **strict JSON only**.

Cross-model rule: the **Stage-1 generator** and **Stage-2 scorer** should be **different models**
(reduce self-consistency inflation). Prefer offline/pinned models; log ids/versions.

---

## Prompt 1 — Stage 1: profile generation (word-identity-blind)

**Input the model sees:** dictionary meaning + POS only. **NOT** the Sanskrit spelling, varṇa
sequence, or vṛtti glosses.

```
SYSTEM: You produce an "experiential profile" for an English word-meaning: the emotional
atmosphere / psychological field a person associates with it. Use ONLY descriptors from the
provided controlled vocabulary. Choose 8–20 descriptors. Do NOT use vague universal terms
(energy, inner movement, blockage, resonance, life force, vibration, flow) — pick specific,
discriminating descriptors. You are given ONLY an English meaning; do not guess any source
language or word. Output STRICT JSON only, no prose.

USER:
meaning: "{{dictionary_meaning}}"
part_of_speech: "{{pos}}"
controlled_vocabulary: {{controlled_vocab_list}}

Return: {"descriptors": ["...", "..."]}   // 8–20, all from controlled_vocabulary
```

## Prompt 2 — Stage 1: profile quality check

Rule-based checks run first (count 8–20; all in controlled vocab; no banned universals; no dupes).
This LLM check is a secondary gate.

```
SYSTEM: You audit an experiential profile for quality. Flag it if: it has fewer than 8 or more
than 20 descriptors; any descriptor is outside the controlled vocabulary; any descriptor is a
vague universal (energy, inner movement, blockage, resonance, life force, vibration, flow) not
operationalized; or it is so generic it would fit almost any word. Output STRICT JSON only.

USER:
descriptors: {{descriptors}}
controlled_vocabulary: {{controlled_vocab_list}}

Return: {"ok": true|false, "problems": ["..."]}
```

## Prompt 3 — Stage 2: anonymous composition-vs-profile scoring (fully blinded)

**Input the model sees:** anonymized compositions (`comp_*`) and anonymized profiles (`prof_*`)
only. **NO** Sanskrit word, **NO** dictionary meaning, **NO** arm/profile names, **NO** hidden key.

```
SYSTEM: You are given several short token-strings ("compositions") and several descriptor lists
("profiles"). For each composition and each profile, output a match score in [0,1] = how well the
composition's overall feel matches that profile. Do NOT identify, name, translate, or guess the
language or origin of any composition. Do NOT add commentary. Output STRICT JSON only.

USER:
compositions: {{[{"comp_id","text"}...]}}
profiles: {{[{"profile_id","descriptors"}...]}}

Return: {"scores": {"comp_1": {"prof_1": 0.0, "prof_2": 0.0, ...}, ...}}
```

## Prompt 4 — contamination self-check (separate call; blinding probe)

Run separately on the same anonymized compositions. If the model can identify the word/language
or supplies cultural/spiritual meaning, blinding is broken → `LLM_PILOT_CONTAMINATED`.

```
SYSTEM: You will see anonymized token-strings. Do you recognize what any of them is (a specific
word, language, or concept)? Answer honestly. Output STRICT JSON only.

USER:
compositions: {{[{"comp_id","text"}...]}}

Return: {"identified": true|false,
         "details": [{"comp_id":"...","guess":"...","basis":"..."}]}
```
Contamination fires if `identified` is true for target items above chance, or if `details`
reference Sanskrit / a specific word / cultural / spiritual / etymological knowledge.

## Prompt 5 — malformed-response repair (one attempt only)

If Prompt 3's output is not valid JSON per the schema, re-prompt **once** to reformat. It must add
**no new information** — only restructure. If still invalid → drop the item (pervasive → the run
is `LLM_PILOT_INCONCLUSIVE`).

```
SYSTEM: Your previous output was not valid JSON in the required schema. Reformat it into valid
JSON. Do NOT add, remove, or change any scores — only fix the JSON structure. Output STRICT JSON
only.

USER:
required_schema: {"scores": {"comp_id": {"profile_id": <number 0..1>, ...}, ...}}
previous_output: {{raw_text}}

Return: the corrected JSON only.
```

---

Real D0 pilot package prepared only. No real scoring has occurred. Track B remains blocked.
Structure, not validated meaning.
