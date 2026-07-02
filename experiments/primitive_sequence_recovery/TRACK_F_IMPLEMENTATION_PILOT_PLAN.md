# Track F — Implementation & Pilot Plan (docs only)

**Planning only. Nothing implemented, run, or scored.** No experiment, no LLM/scorer call, no
network, no artifact mutation, no manifest marked READY. `frozen/manifest.json` remains NOT_READY;
psr runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`,
no Sanskrit privilege. This turns `PREREG_TRACK_F_VARNA_INFERENCE_STEERING.md` into a build spec; it
authorizes **no run**.

**Not a rescue of Track C / D0 / Track E.** Those tested dictionary recovery (no signal),
experiential-weather (`LLM_PILOT_NO_SIGNAL`), and candidate-boundary selection
(`CONTEXT_ONLY_EXPLAINS`, closed). Track F tests a *different* thing — inference behavior change —
and cannot reinterpret or soften those negatives.

**Skeptical note.** The dominant prior is `PROMPT_PRIMING_ONLY`: any injected boundary text changes
LLM output. The build must therefore make **specificity** (A ≠ B, A ≠ I) and **correctness
preservation** first-class, length/register-match all boundary texts, and penalize poetic-but-wrong
answers. Default expectation: `PROMPT_PRIMING_ONLY` / `NO_EFFECT`.

## 1. Purpose

Specify what must be built and frozen before a Track F run: prompt-arm construction, task/packet
schemas, boundary-injection format, output and judge schemas, metrics, decision logic, and a
synthetic-first harness — all under an explicit approval gate. **No run is approved here.**

## 2. Testing object

Track F tests **inference-output steering**: whether injecting a varṇa/vṛtti boundary as a *soft*
prompt constraint changes a real LLM's answer/interpretation/reasoning **specifically** (vs
scrambled/Barnum/dictionary boundaries) and **usefully** (without degrading correctness). It is
**not**:
- semantic validation (whether varṇa meanings are true),
- candidate-selection accuracy (that was Track E),
- dictionary/experiential recovery (Track C / D0),
- Track B confirmatory validation.

Even a positive is an **engineering/prompting** effect on *this* model in *this* setup, never
ontological truth.

## 3. Prompt arms (implementation requirements)

Same base model, task text, decoding, and injection position for all arms; only the boundary text
differs, and all boundary texts are **length/register-matched**:

- **X — normal prompt:** task only, no boundary block.
- **A — real varṇa boundary:** the true varṇa/vṛtti composition of the target word, phrased as a
  soft "internal lens/constraint."
- **B — scrambled varṇa boundary:** same glosses under a frozen scrambled mapping (seed recorded).
- **F — dictionary/etymology-only:** dictionary gloss and/or root prior, no varṇa.
- **I — generic Barnum boundary:** a generic "could-apply-to-anything" symbolic lens (the D0/E
  Barnum family, adapted; arm-I scored as `max` over the family if multi-member).
- **R — random unrelated boundary (optional):** an off-topic constraint of matched length/register,
  to bound the pure "any added text" effect.

Requirement: boundary text is a **soft prior**, explicitly *not* an instruction to override context
or ground truth. Arm identity is never in a scorer/judge-facing field.

## 4. Prompt-packet schemas (docs; NOT frozen artifacts; separate from frozen/manifest.json)

**`track_f_tasks.jsonl`**
```
{"task_id":"f000","task_type":"ambiguous_word|context_sensitive|moral_emotional|metaphor|
   candidate_ranking|short_answer|reasoning_path","base_prompt":"<task text>",
 "target_word":"<word or phrase or null>","context":"<context or null>",
 "candidates":["..."]|null,               // only for candidate_ranking
 "expected_task_behavior":"<what a correct answer does>","correctness_criteria":"<checkable ref>",
 "contamination_risk":"low|med|high","exploratory_only":false}
```

**`track_f_prompt_arms.jsonl`** (per task × arm; the assembled prompt is dev/hidden until run)
```
{"task_id":"f000","arm":"X|A|B|F|I|R","boundary_text":"<injected block or null for X>",
 "boundary_kind":"none|real|scrambled|etymology|dictionary|barnum|random",
 "length_tokens":<int>,"dev_only":true}     // arm label is hidden from judges
```

**`track_f_boundary_packets.jsonl`** (scorer/model-facing, anonymized: no arm label, no varṇa/root)
```
{"packet_id":"pkt_<opaque>","task_id":"f000","prompt":"<assembled model prompt>",
 "response_format":"json","instructions":"<JSON-only output contract>"}
```

**`track_f_judge_packets.jsonl`** (judge-facing, anonymized model outputs to compare)
```
{"judge_packet_id":"jpkt_<opaque>","task_id":"f000","outputs":[{"anon_id":"resp_1","text":"..."}...],
 "reference":"<correctness ref>","rubric_version":"1.0"}     // arm identities in a hidden key only
```

**`track_f_manifest.json`** (separate from frozen/manifest.json; never edit that)
```
{"schema_version":"1.0","bundle_type":"track_f_input_bundle","status":"NOT_READY",
 "run_enabled":false,"approval_status":"NOT_APPROVED","representation":"prompt_boundary_injection",
 "four_sphere_integrated":false,"arms":["X","A","B","F","I","R?"],"hashes":{...},"seeds":{...},
 "note":"Track F inference-steering input bundle; behavior test, not validation"}
```

## 5. Task types

Cover, with 3–5 chosen for the smoke (§12):
- **ambiguous word interpretation** (which sense),
- **context-sensitive meaning** (sense shifts with context),
- **moral / emotional interpretation** (affective/ethical read),
- **metaphor interpretation** (unpack figurative language),
- **candidate ranking** (order supplied interpretations),
- **short answer generation** (free-form answer),
- **reasoning-path / explanation-style analysis** (how the model justifies its answer).

Each task carries a **checkable correctness reference** (for correctness preservation) plus genuine
interpretive room (for the steering signal).

## 6. Boundary-injection format

- **Same position** in every prompt (e.g. a labelled "Internal lens:" block immediately before the
  task question), identical across arms; X omits the block (or uses an empty placeholder of matched
  position).
- **Length/register-matched** across A/B/F/I/R so the comparison is content, not verbosity.
- **Neutral wording** ("Consider this internal lens as a soft prior; it does not override the
  context or known facts") — the boundary is a **soft prior**, never an override.
- **No varṇa/root names in the model-/judge-facing prompt** where they would leak (strip surface
  word, varṇa keys, and root-name tokens; keep them in a hidden dev field), per the Track E leak
  scanner, extended to Track F prompts.
- Boundary content for A/B is the composed vṛtti-gloss text (as in Track E, anonymized); F is the
  dictionary/etymology text; I is the Barnum lens; R is the off-topic control.

## 7. Model output schema

The answer model must return JSON only:
```
{"answer":"<task answer>","interpretation":"<chosen reading, if applicable>",
 "reasoning_summary":"<brief justification — a summary, NOT hidden chain-of-thought>",
 "confidence":<0..1>,"caveats":"<uncertainties or empty>",
 "selected_candidate":"<opt id or null>"}     // required only for candidate_ranking
```
- **No hidden chain-of-thought requirement**: `reasoning_summary` is a short, user-facing rationale,
  not an elicited private CoT.
- Malformed / non-JSON → dropped and rate-tracked; unknown/duplicate packet_id rejected.

## 8. Judge / scoring rubric

Blinded judge (human and/or a **judge model** distinct from the answer model) scores anonymized
outputs on:
- **correctness** (vs reference),
- **context fit**,
- **usefulness** (helps answer the task better),
- **specificity** (targeted vs vague),
- **non-genericity** (not a one-size-fits-all reading),
- **over-poetic / noise penalty** (evocative-but-empty language penalized),
- **hallucination penalty** (invented facts penalized),
- **task obedience** (did the requested task in the requested format),
- **delta from X** (how much this output differs from the same task's X output),
- **specificity vs B/I** (is A's shift distinct from scrambled/Barnum shifts).

Judge packets are arm-blinded; a contamination probe checks the judge cannot name a Sanskrit/varṇa/
root token from an anonymized output; judge agreement reported; low-agreement items excluded.

## 9. Primary metrics

- **`A_vs_X` inference delta** — magnitude of A's change vs normal prompt (necessary, not
  sufficient).
- **`A_vs_B` specificity** — A's steering distinct from scrambled.
- **`A_vs_I` non-Barnum specificity** — A's steering distinct from a generic symbolic lens.
- **`A_vs_F` incremental** — A adds over dictionary/etymology.
- **Correctness preservation** — A's correctness ≥ X's (no degradation).
- **Usefulness gain** — A's judged quality > X (and > B/I).
- **Hallucination / noise penalty** — A does not raise hallucination/over-poetic rates.
- **Stability** — pattern holds across ≥ a few seeds and prompt phrasings; family-aware bootstrap
  CIs on the deltas (CI lower > 0 for a positive).

Primary falsifier: unless A is **specific (≠ B and ≠ I)** *and* **correctness-preserving**, H_F
fails regardless of raw `A_vs_X`.

## 10. Decision labels

Allowed only:
- `INFERENCE_STEERING_SIGNAL` — A: specific (≠ B, ≠ I, ≠ F), useful, correctness-preserving,
  seed-stable delta over X.
- `PROMPT_PRIMING_ONLY` — A changes output no more specifically than a generic boundary (A ≈ B/I).
- `SCRAMBLE_EQUIVALENT` — scrambled steers as well as real.
- `BARNUM_EQUIVALENT` — Barnum steers as well as real.
- `CORRECTNESS_DEGRADED` — A changes output but reduces correctness.
- `NO_EFFECT` — A barely changes output vs X.
- `INCONCLUSIVE` — CIs include 0, high malformed rate, low judge agreement, or arms not separable.

Forbidden: `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking / validation language.

## 11. Synthetic-first harness plan (build + prove before real data)

A toy harness (like `track_e_smoke_runner.py`) that accepts **synthetic** judge scores *in* (no
LLM), anonymizes arms/outputs with a hidden key, computes §9 metrics, and assigns a §10 label. Toy
fixtures marked `toy_not_for_scoring=true` + `synthetic_only=true` (nonsense tokens; no real words),
covering:
- **A-specific useful steering** (A distinct from B/I, useful, correctness kept) → `INFERENCE_STEERING_SIGNAL`,
- **all boundary arms shift equally** → `PROMPT_PRIMING_ONLY`,
- **scrambled equals real** → `SCRAMBLE_EQUIVALENT`,
- **Barnum equals real** → `BARNUM_EQUIVALENT`,
- **A shifts but correctness drops** → `CORRECTNESS_DEGRADED`,
- **no arm changes output** → `NO_EFFECT`,
- **malformed model/judge output** → rejected loudly,
- **contamination** (varṇa/root/Sanskrit token, forbidden label) → rejected.
Tests assert: every allowed label producible; forbidden labels rejected; real-run path unavailable;
toy flags mandatory; `A_vs_X` necessary but specificity (`A_vs_B`/`A_vs_I`) + correctness gate the
positive; leak scanner catches surface/varṇa/root/arm/role leaks; malformed fails loudly. **No real
scoring.** A refusal-gated, no-model-call runner (separate approved config, like Track E) emits the
prompt/judge packets for external execution; it never calls a model itself.

## 12. Smoke-pilot recommendation (recommendation only — not frozen, not approved)

- **20–30 prompts**; **3–5 task types** from §5;
- **same base LLM** and **same decoding settings** across all arms;
- **randomized / blinded arms**; boundary texts length/register-matched;
- **no memory / no carryover** between prompts;
- **judge model separate** from the answer model where feasible (answer ≠ judge; and where a
  generator is used, generator ≠ answer ≠ judge);
- **JSON/structured** answers + judge scores; contamination probe; malformed-rate gate;
- **result exploratory only** — smoke size cannot validate; a positive only justifies a larger
  pre-registered pilot with CIs, seed stability, and independent replication.

## 13. Controls against prompt priming (hard requirements)

- **Length/register-matched** boundary texts across A/B/F/I/R.
- **Scrambled boundary (B)** — the specific varṇa mapping must matter.
- **Barnum boundary (I)** — the effect must not be generic symbolic language.
- **Random unrelated boundary (R, if used)** — bounds the pure "any added text" effect.
- **Blinded judge packets** — arm identity never judge-visible.
- **Over-poetic / noise penalty** — evocative-but-empty answers penalized, not rewarded.
- **Correctness-preservation gate** — any correctness drop vs X blocks a positive
  (`CORRECTNESS_DEGRADED`), even with high specificity.

## 14. Guardrails (hard gates)

- **No Track B movement**; the confirmatory path stays blocked regardless of any Track F outcome.
- **No semantic-truth claims**; no claim that varṇa meanings are true.
- **No ontological claims**; `ONTOLOGICAL_SIGNAL` asserted against.
- **No Sanskrit privilege.**
- **Four-sphere not integrated** unless separately approved (a four-sphere Track F variant is a
  distinct future prereg/config).
- **Prior negatives preserved** (Track C / D0 / Track E-flat unchanged; no rescue).
- **No real-run path** until explicit approval (env gate + completed checklist + frozen
  `track_f_config` + separate approved run config), and no model calls in this phase (synthetic
  only); `frozen/manifest.json` and Stage A never touched.

## 15. Boundary statement

Track F implementation planning only. It tests inference-steering behavior, not varṇa truth. Track C/D0/E negatives remain unchanged. Track B remains blocked. Structure, not validated meaning.
