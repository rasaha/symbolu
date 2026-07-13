# REAL_LLM_VALIDATION_PREREGISTRATION

**Frozen before measurement.** Evaluates whether the FROZEN ActionGate Context
Minimization compressor (0ae0fea) preserves real LLM performance, not merely
ActionGate decision invariance. No redesign, no compressor change, no ActionGate
change, no threshold change, no synthetic improvement after benchmarking begins.

## Question

Does ActionGate-protected context minimization preserve real downstream LLM utility
(instruction following, QA, reasoning, summarization, extraction, tool selection,
tool-argument generation, envelope extraction) at the same token budgets where it
already preserves the ActionGate decision?

## Methods compared (same budgets)

1. original (no compression)
2. structural-only compression
3. **ActionGate-protected compression (current frozen implementation)**
4. protection-unaware compression (control)
5. LLMLingua-2 or closest open implementation — only if runnable

Budgets: {10, 20, 30, 40, 50, 60}%.

## Metrics (per method × budget)

token reduction · latency · runtime/API cost estimate · task accuracy ·
ActionGate decision preservation · envelope preservation · hallucination rate ·
instruction-following failures · tool-call correctness.

## Primary success criteria (measured, with a REAL LLM)

- ActionGate decision flips: **0**
- Task-accuracy degradation (protected vs original): **< 2%**
- Tool-argument correctness: **≥ 98%**
- Envelope preservation: **100%**

## Recommendation rule (measured evidence only)

- `GO` — all four criteria met **with a real LLM**.
- `LIMITED_GO` — decision/envelope preserved but a task-quality criterion misses.
- `STOP` — a decision flip, envelope break, or material task degradation.
- `BLOCKED_NO_MODEL` — **no real LLM ran** (no open weights, no API key). This is
  NOT one of the three graded outcomes; emitting GO/LIMITED_GO/STOP without real
  evidence would fabricate results, which the rules forbid. The harness emits a
  graded recommendation automatically once real results exist.

## Model availability (honest, this environment)

No runnable open-weight LLM is present: `transformers`/`torch` are not installed,
HuggingFace is policy-blocked (403 CONNECT), and no `ANTHROPIC_API_KEY`/
`OPENAI_API_KEY` is set. Per the milestone instruction, the harness is built and the
missing dependency is documented; **no results are fabricated.** The deterministic
reader validates plumbing only and is labelled non-scientific everywhere.

## Ground truth & grading

Every task's ground truth is derived from the FROZEN ActionGate envelope/decision on
the original context, so grading is model-agnostic and deterministic. Decision and
envelope preservation are computed structurally against the real gate, independent
of the LLM.

## Scientific rules (restated)

No tuning after seeing results. No threshold changes. No compressor changes. No
ActionGate changes. Frozen implementations only. Negative results reported honestly.
