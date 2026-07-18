# Kosha Control-Plane Gate — CPU Simulation RESULTS

Pre-reg: `docs/KOSHA_CONTROL_PLANE_GATE_PREREG.md`. Harness:
`scripts/conscious_generation/simulate_kosha_control_gate.py`. CPU-only, no runtime/prompt/generation
change, deterministic query-derived `p_k`, frozen default parameters (no tuning).

## Run 1 — Phase-3 audit traces (outcome-labelled)
- Input: `answer_audit_eval.jsonl` (n=72; balanced: 34 needs-rewrite, 38 not).
- **DECISION: `KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS`** (honest negative).
- Decision distribution: **DEFER = 72 / 72** (emit_rate 0.0, hedge_rate 0.0, defer_rate 1.0).
- separation (withhold|bad − withhold|good) = **0.0**; withhold_good_rate = **1.0**; beats-random-by = 0.0.
- corr(withhold, audit/frame/rejected) = `None` (withhold is constant → undefined).

**Why:** the audit queries are short, weak-cue prompts ("What is a doctor?"). Under the frozen params the
query-derived readiness `R_K` is near zero for nearly all of them, so `E_emit < τ_hedge` everywhere and the
gate **defers everything** — withholding 100% of *good* answers with **zero discrimination**. This trips
`withhold_good_rate > 0.5` → `DEGRADES_GUARDRAILS`. It does not beat NO_GATE or RANDOM_GATE (all separation
= 0.0). This is the **expected, honest** outcome of §19: a query-only `p_k` measures *query ambiguity*,
while audit outcomes depend on the *answer*, so there is no reason for them to align — and here they don't.

## Run 2 — K2 queries (no outcome labels)
- Input: `kosha_k2_queries.json` (n=105). **DECISION: `KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE`.**
- Distribution: HEDGE 53 · EMIT 29 · DEFER 23 (the gate does vary on richer, cue-bearing queries) — but
  with no trusted outcome labels, **no signal is claimed.**

## Run 3 — hidden-state `p_k`
- `--pk-source hidden` → **`KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED`** (blocked until real Kosha labels pass the
  surface-baseline gate; no simulation performed).

## Verdict
The control-plane readiness/entropy gate, as a **deterministic query-derived** signal under pre-registered
frozen parameters, **does not beat baselines and actively degrades the guardrail** on the only
outcome-labelled trace set available. This is **not** a K2 rescue and **not** a validation — it is an honest
negative for the *query-derived* version. The hidden-state version remains the only path that could show
signal, and it stays **blocked** behind the surface-baseline anti-circularity wall. No parameters were
tuned; the negative stands as recorded.

> Kosha control-plane readiness/entropy gating is pre-registered and simulated CPU-side only. It is distinct
> from the failed K2 prompt modifier, does not touch runtime or prompts, and remains unvalidated until it
> beats baselines on trusted outcome-labelled traces without post-hoc parameter tuning.
