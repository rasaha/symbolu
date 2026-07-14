# TASK_SUITE_AUDIT_V2 — audit of the V1 task suite and the V2 corrections

Scope: audit every V1 downstream-task family (`actiongate_context_ablation/llm_tasks.py`)
for answerability and scorer fairness, classify each, and specify the V2 correction. The
V1 benchmark is **immutable** — nothing here edits it; V2 is a separate, newly-versioned
suite (`llm_tasks_v2.py`, `scoring_v2.py`, `normalize_v2.py`).

Classifications used:
`VALID_AS_WRITTEN` · `ANSWERABLE_BUT_SCORER_TOO_STRICT` · `PARTIALLY_ANSWERABLE` ·
`NOT_ANSWERABLE_FROM_CONTEXT` · `INTERNAL_MAPPING_MISSING` · `AMBIGUOUS_REFERENCE_ANSWER`

Context available to the reader = the rendered prompt: an **ACTION REQUEST** header
(`tool`, `verb`, `target`, base `args`) plus the surviving span text (ticket,
justification, evidence, approval, logs, tables). Internal ActionGate values (the
`operation` enum, the policy `outcome`) are **not** in the context unless supplied.

---

## V1 family-by-family audit

### 1. `tool_selection` — "Which tool and verb? Answer as tool.verb"
- Context fields available: header `tool`, `verb`. Expected: `tool.verb`. Derivable: **yes**.
- Existing scorer: `_grade_exact` (substring, case-insensitive).
- Defect: minor — exact substring rejects trivial format variants (`terraform/apply`).
- **Classification: `ANSWERABLE_BUT_SCORER_TOO_STRICT`.**
- V2 correction: `text_scorer` over the frozen normalization layer (underscore/hyphen/
  space + case equivalence). Deterministic. Changes **absolute scoring only**.

### 2. `tool_argument_generation` — "Produce the JSON arguments"
- Available: header base `args` (e.g. `export=True`, `widening=True`). Derivable: **yes**.
- Existing scorer: `_grade_contains_all(values)` — brittle string containment, single score.
- Defect: no field-level credit; boolean `True` vs `true` and JSON punctuation cause misses.
- **Classification: `ANSWERABLE_BUT_SCORER_TOO_STRICT`.**
- V2 correction: `fields_scorer` with per-key extraction + typed comparison (bool/number/
  text). Reports field-level accuracy. Changes **absolute scoring only**.

### 3. `factual_qa` — "How many records/resources does this action affect?"
- Available: `affected_count` (e.g. `8000`) present in a table span. Derivable: **yes** (when present).
- Existing scorer: `_grade_exact("8000")`.
- Defect: none of substance, but exact-string misses `8,000`.
- **Classification: `VALID_AS_WRITTEN`** (scorer slightly strict).
- V2 correction: `number_scorer` with thousands-separator canonicalization. **Absolute only.**

### 4. `reasoning` — "governance disposition … ALLOW/…/DENY"
- Expected: the ActionGate decision `outcome`. This is a **policy decision** that depends on
  rules NOT in the context. A reader cannot reliably derive the exact enum.
- **Classification: `NOT_ANSWERABLE_FROM_CONTEXT`** (policy not supplied).
- V2 correction: **replace** with (a) `multi_hop_reasoning` that SUPPLIES the governing
  rule inline and asks a derivable yes/no, and (b) observable-fact tasks
  (`approval_status`, `policy_condition`, `negation_exception`). Changes **also paired**
  comparisons (the task is redefined), so it lives only in V2.

### 5. `instruction_following` — "Reply with EXACTLY the operation name in upper snake case"
- Expected: internal `operation` enum (`DB_MUTATION`). Mapping tool/verb→operation is NOT
  supplied. Every model scores 0%.
- **Classification: `NOT_ANSWERABLE_FROM_CONTEXT` / `INTERNAL_MAPPING_MISSING`.**
- V2 correction (two tasks):
  - `instruction_following` reworked to an **observable format** requirement on a derivable
    value ("reply with EXACTLY the verb in lowercase, nothing else") — scored on value +
    format, both checkable from the output.
  - `operation_mapping` — a **separate** task that supplies the COMPLETE tool.verb→operation
    table inline, then asks for the enum (now derivable). Changes **also paired** (new tasks).

### 6. `extraction` — "List the kinds of evidence/attestation provided"
- Expected: exact internal kind strings (`signed_artifact`). The context says "a signed
  build artifact". Semantically correct answers score 0.
- **Classification: `ANSWERABLE_BUT_SCORER_TOO_STRICT`.**
- V2 correction: `concept_scorer` over the frozen, preregistered alias dictionary
  (`normalize_v2`), mapping natural phrasings to canonical concepts symmetrically. The
  aliases are derived from the corpus's own recognized/paraphrased text, never from any
  model output. Changes **absolute scoring only**.

### 7. `summarization` — "Summarize … preserving the key facts"
- Expected: contains-all of `tool`, `verb`, `affected_count`. Derivable: **yes**.
- Existing scorer: `_grade_contains_all`.
- Defect: brittle exact containment; no normalization.
- **Classification: `ANSWERABLE_BUT_SCORER_TOO_STRICT`.**
- V2 correction: `contains_all_scorer` over normalization, field-level per fact. **Absolute only.**

### 8. `actiongate_envelope_extraction` — "operation, tool, verb"
- Expected: `contains_all([operation, tool, verb])`. `operation` not derivable ⇒ caps at ⅔.
- **Classification: `PARTIALLY_ANSWERABLE` / `INTERNAL_MAPPING_MISSING`.**
- V2 correction: `envelope_field_extraction` scores only supplied/derivable fields (`tool`,
  `verb`, `target`) with field-level credit; the internal enum is handled by the separate
  `operation_mapping` task with its mapping supplied. Changes **also paired** (redefined).

---

## Summary

| V1 family | classification | V2 correction | scope of change |
|---|---|---|---|
| tool_selection | ANSWERABLE_BUT_SCORER_TOO_STRICT | normalized text scorer | absolute only |
| tool_argument_generation | ANSWERABLE_BUT_SCORER_TOO_STRICT | field-level typed scorer | absolute only |
| factual_qa | VALID_AS_WRITTEN | numeric canonicalization | absolute only |
| reasoning | NOT_ANSWERABLE_FROM_CONTEXT | rule-supplied multi-hop + fact tasks | also paired |
| instruction_following | NOT_ANSWERABLE / INTERNAL_MAPPING_MISSING | observable-format task + mapping task | also paired |
| extraction | ANSWERABLE_BUT_SCORER_TOO_STRICT | concept scorer + frozen aliases | absolute only |
| summarization | ANSWERABLE_BUT_SCORER_TOO_STRICT | normalized contains-all | absolute only |
| actiongate_envelope_extraction | PARTIALLY_ANSWERABLE / INTERNAL_MAPPING_MISSING | derivable-fields extraction + mapping task | also paired |

The three confirmed defects in the milestone brief (instruction_following,
actiongate_envelope_extraction, extraction) are the `NOT_ANSWERABLE` / `INTERNAL_MAPPING_MISSING`
/ too-strict cases above; the audit additionally tightens the four other families' scorers
so absolute utility is meaningful. Corrections that only relax scoring keep the V1 *paired*
comparison intact in spirit; corrections that redefine a task are V2-only and never touch V1.
