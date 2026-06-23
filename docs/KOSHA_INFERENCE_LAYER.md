# Kosha — Optional Inference-Time Depth/Readiness Prompt-Control Layer

> **C×R×S controls semantic-frame alignment. Kosha controls inference-time answer depth/readiness. Kosha is
> currently a deterministic prompt-control layer, not a trained cognitive-state estimator.**
>
> **Kosha inference is not yet validated for quality improvement. It is implemented as an optional
> experimental layer requiring evaluation.**

## What Kosha does
Given a user query (and, optionally, the C×R×S frame + hints), Kosha deterministically selects one of five
**depth/readiness levels** and emits a short **prompt modifier** that is inserted into the framed prompt to
steer *how deep* the answer should go — without changing *which semantic frame* it stays in.

## What Kosha does NOT do
- It does **not** replace or modify C×R×S frame selection.
- It does **not** train anything, read hidden states, or change model weights.
- It does **not** add Guna / Vritti / Bhava signals.
- It is **not** wired into agent runtime.
- It is **disabled by default**; when disabled, the framed prompt is **byte-for-byte unchanged**.
- It must **not** weaken C×R×S frame correctness or rejected-domain avoidance (it only appends a depth
  instruction that explicitly says "preserve the primary semantic frame").

## C×R×S vs Kosha
| | C×R×S | Kosha |
|---|---|---|
| Question answered | *Which semantic frame should the answer stay in?* | *At what depth/readiness should it be generated?* |
| Output | primary / secondary / rejected domains | one of five depth levels + prompt modifier |
| Status | **validated** inference-time mechanism | **experimental**, not yet validated for quality |
| Mechanism | deterministic MATCH = C×R×S | deterministic rule-based selector |

## Five Kosha levels
| level | inference meaning | prompt behavior |
|---|---|---|
| `ANNAMAYA` | surface / data | short, concrete, factual, simple |
| `PRANAMAYA` | action / practical | steps, next actions, operational guidance |
| `MANOMAYA` | context / intent | user concern, ambiguity, contextual framing |
| `VIJNANAMAYA` | reasoning / discernment | compare alternatives, assumptions, tradeoffs |
| `ANANDAMAYA` | synthesis / integration | high-level synthesis, unifying principle |

## Selection (deterministic)
`select_kosha_depth(query, *, primary_domain, secondary_domains, rejected_domains, user_level_hint,
task_type_hint)` → `KoshaSelection{level, confidence, reason, prompt_modifier, features}`.

- **Precedence:** explicit `user_level_hint` > `task_type_hint` > query cues.
- **Cue conflicts:** `VIJNANAMAYA > PRANAMAYA > MANOMAYA > ANANDAMAYA > ANNAMAYA`.
- **Simplicity override:** an explicit "simple / 5th grade / brief / ELI5" request **forces `ANNAMAYA`**
  *unless* the query is high-stakes.
- **Default:** no strong cue → `ANNAMAYA` (surface), low confidence (0.4).
- **Safety boundary:** if medical / legal / financial / high-stakes terms are detected, the prompt modifier
  appends *"Be cautious, state limits, avoid unsupported certainty, and preserve factual grounding,"* and
  the simplicity-override is suppressed (do not force a shallow answer on a high-stakes query). This is a
  light cautious modifier only — **no** deep medical/legal/financial policy logic.

## Inference pipeline
```
User query
  → C×R×S frame selection
  → [Kosha depth selection]          (optional; enable_kosha)
  → prompt construction              (modifier inserted AFTER frame instructions, BEFORE the question)
  → LLM answer
  → answer audit
```

## Config flag
Kosha is **off by default**. It is engaged only when a `KoshaSelection` is passed to
`build_framed_prompt(..., kosha=<selection>)` (callers gate this on an `enable_kosha: bool = False` flag).
With `kosha=None` the framed prompt is identical to the pre-Kosha output (asserted by tests).

## Example prompt (Kosha enabled)
```
CSR/C×R×S semantic-frame analysis:

Primary domains:
  technology
Secondary domains:
  (none)
Rejected domains:
  (none)

Instructions:
1. Use primary domains as the main answer frame.
2. Mention secondary domains only if useful.
3. Do not introduce rejected domains unless the user explicitly asks.
4. Do not claim phonemes alone prove meaning.
5. Preserve factual correctness.

Depth/readiness instruction:
Answer at a reasoning/discernment level: compare alternatives, state assumptions, explain tradeoffs, and preserve the primary semantic frame.

User question:
Compare microservices vs a monolith.
```

## Example trace
```json
{ "kosha": { "enabled": true, "level": "vijnanamaya", "confidence": 0.8,
             "reason": "Query cue(s) ['compare', 'tradeoff'] → vijnanamaya.",
             "features": { "matched_cues": {"vijnanamaya": ["compare", "tradeoff"]},
                           "high_stakes": false, "source": "query_cue" } } }
```
Disabled: `{ "kosha": { "enabled": false } }`.

## Validation status
- **Implemented · optional · disabled by default.**
- The deterministic **selector** scores 0.9 on a 10-item labelled set
  (`scripts/conscious_generation/eval_kosha_inference.py`) — but **selector accuracy ≠ answer-quality
  improvement.**
- **Kosha is NOT yet validated as a quality-improving signal.** Whether the depth modifier actually
  improves answers (clarity/usefulness/appropriateness) **without** regressing C×R×S frame correctness,
  rejected-domain avoidance, or factuality requires a separate generation eval (four-arm style, same
  validated rubric) under its own pre-registration before any default-on or runtime claim.

## Files
- `scripts/cg_wrapper_ablation/csr_match_filter/kosha.py` — enum, `KoshaSelection`, `select_kosha_depth`,
  `depth_block`, `kosha_trace`.
- `scripts/cg_wrapper_ablation/csr_match_filter/prompts.py` — `build_framed_prompt(..., kosha=None)`.
- `scripts/conscious_generation/eval_kosha_inference.py` — deterministic selector eval.
- `tests/test_kosha_inference.py` — unit tests.
