# Internal Policy Controller v3

Corrected implementation of **draft → full Symbol-U state → ontology-driven policy →
LLM rewrite → independent judge**, fixing the v2 wiring defects found in
`../V2_AUDIT_AND_V3_PLAN.md`. **Self-contained** (local `llm.py`, `judge.py`,
`data.py` — relocated here from v2 during cleanup so the canonical line no longer
depends on deprecated code). v1/v2 kept intact only as the audited-defective record.

## Two vritti senses are SEPARATE fields, from TWO sources

- `dynamic_state` (inertia/activation/oscillation/tension/release — canonical motion
  system, `vritti_mapper.VrittiType`) is **phoneme/PSE-driven** → it is the
  **DELIVERY** signal (`delivery_pace`, energy/pace/tone).
- `classical_vritti` is now a **SENTENCE-LEVEL COGNITIVE evaluation of the draft
  answer's MEANING** (`cognitive_evaluator.py`, provenance
  **`sentence_semantic_rule_v1`**) → it is the **COGNITIVE/EPISTEMIC** signal.
  This replaces the earlier phonological `derived_bridge`, which was unfaithful:
  classical Patañjali vrittis are *modes of cognition*, so they should be read from
  what the sentence asserts, not from its sound.

### The 3+2 cognitive representation

The evaluator inspects the draft and returns a practical, canonical-schema-named state:

| field | values | what it detects |
|-------|--------|-----------------|
| `primary` | `pramana` / `viparyaya` / `vikalpa` | grounded answer / contradiction-false-certainty / speculation |
| `nidra` (flag) | `bool` | low-information / evasive — needs clarification |
| `smrti` (flag) | `bool` | memory-/prior-context reference |

The five names match the canonical schema `presentation.signals.VrittiDistribution`
exactly; `primary` is the dominant cognitive mode and `nidra`/`smrti` are independent
boolean flags. (`llm_judge_vritti` provenance is reserved for when an LLM does the
evaluation instead of the rule.)

## Key fix: every claimed Symbol-U variable drives a DISTINCT policy axis

The three cognitive signals each act on their own axis, separately from the phoneme
delivery signal:

```
classical_vritti.primary -> epistemic_stance       (correctness / epistemic posture)
classical_vritti.nidra   -> clarification_policy    (ask vs. pretend to answer)
classical_vritti.smrti   -> memory_policy           (recall provenance / caution)
dynamic_state            -> delivery_pace           (pace / energy)
guna                     -> tone
kosha                    -> reasoning_style
aspect_balance           -> caution
guna_resonance           -> uncertainty_handling
valence                  -> speculation_reduction
```

A **field-influence self-check** (`cli check`) fails if any of the **9**
policy-driving variables is inert — the exact defect that invalidated v2. A
**by-family** check additionally proves the four headline signals hit their *specific*
expected axes (cognitive primary→stance, nidra→clarification, smrti→memory,
dynamic→delivery). `pse_*`, `kosha_resonance`, `valence_sign` are kept as
**diagnostic-only** (not claimed to drive policy).

## Policy translation (cognitive vs. delivery)

`PolicySpec.render()` emits a two-section prompt: a **Cognitive policy** block
(stance, clarification, memory, reasoning, caution, uncertainty, speculation) and a
**Delivery policy** block (tone, pace, clarity).

## Coverage honesty note

`classical_vritti` is about **answers**. The benchmark prompts are mostly
**questions**, so on the prompt set they read `pramana`/`nidra` and rarely
`smrti`. Reachability of every cognitive state is therefore proven on crafted
**ANSWER probes** (`cognitive_evaluator.PROBE_ANSWERS`), surfaced in the coverage
audit as `evaluator_reachability`. The coverage report flags any value not seen on
the prompts rather than hiding it.

## Commands

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.v3.cli check     # self-check gate
python -m symbolu_neural.internal_policy_controller.v3.cli coverage  # signal/axis coverage + reachability
python -m symbolu_neural.internal_policy_controller.v3.cli state     # state + policy per prompt
python -m symbolu_neural.internal_policy_controller.v3.cli run --backend mock   # plumbing
# real verdict (needs a key):
export MISTRAL_API_KEY=...   # or ANTHROPIC_API_KEY
# rubric eval (absolute 1-5 — NOTE: ceiling-saturates on strong models, see report):
python -m symbolu_neural.internal_policy_controller.v3.cli run --backend mistral --seeds 3
# pairwise A/B eval (PREFERRED — forced choice, position-debiased, validity-gated):
python -m symbolu_neural.internal_policy_controller.v3.cli pairwise --backend mistral --seeds 3
python symbolu_neural/internal_policy_controller/v3/tests/test_v3.py
```

Throughput/rate-limit knobs for real runs: `LLM_MAX_WORKERS` (concurrency, default 8),
`LLM_MIN_INTERVAL` (global seconds/request floor, default 1.1 — the limiter caps the
GLOBAL rate regardless of workers, so concurrency hides latency without extra 429s),
`LLM_MAX_RETRIES` (backoff attempts on 429/5xx, default 6).

## Measurement validity (why the pairwise eval exists)

The first real run (Mistral) exposed a **ceiling effect**: the absolute 1-5 rubric
rated *every* arm ~4.8/5 and `prefer_final ≈ 1.0` everywhere, so it could not detect
small quality differences — a measurement failure, not a result. The `pairwise`
command fixes this with (1) **forced A/B choice** between symbolu and each control on
the same prompt, (2) **position-bias cancellation** (both orders judged and averaged),
and (3) a **judge validity gate** (`judge_discriminates`): the judge must prefer a
correct answer over an evasive one, or the whole verdict is declared invalid. Output
is a per-control preference margin in [-1,+1] with 95% CIs and win/loss/tie counts.

## Status

Structural self-checks **PASS** (17/17 tests; all 9 policy-driving variables
influence policy; the 4 headline signals hit their distinct axes; ≥6 distinct
policies; no dead axes; relabel permutes cognitive primary + flags + dynamic + guna +
kosha + valence). **Quality verdict UNTESTED** here (no API key) — run on a host with
a key. See `../INTERNAL_POLICY_CONTROLLER_V3_REPORT.md`.
