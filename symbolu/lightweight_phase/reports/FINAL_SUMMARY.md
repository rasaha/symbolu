# Lightweight Phase Transformer — Final Summary

Canonical, auditable, dependency-light Phase reference. 98 tests pass; freeze gate
green (`python -m symbolu.lightweight_phase.freeze` → FREEZE OK).

## Completion criteria

1. Lightweight Phase core exists — **YES** (`phase_core.py`).
2. Equations explicit — **YES** (`reference_equations.md`, line-mapped in code).
3. Batch and streaming execution match — **YES** (≤2.4e-7 float32).
4. State memory bounded — **YES** (O(D), constant over N).
5. Detached normalizer implemented — **YES** (frozen contract; test-verified load-bearing).
6. Decay separately validated — **YES** (4 modes; γ=1 reproduces core).
7. Production equivalence demonstrated / divergences documented — **YES** (≤2.4e-7; full divergence table).
8. Lightweight Phase Transformer trains — **YES** (LM + trivial-pattern learning).
9. Sliding-window integration validated — **YES** (O(N·W), protected additive fusion).
10. A vs B reproducible — **YES** (`stage7_ab_results.json`, fixed seeds).
11. Bounded slots use streaming/chunked memory-efficient updates — **YES** (O(M·D) state).
12. A/B/C/C-no-Phase reproducible — **PARTIAL**: A/B done; C ladder deferred (harness ready).
13. Causal ablations identify load-bearing components — **PARTIAL**: Phase-removal
    (config A → chance) shows Phase is load-bearing for distant recall; slot
    ablations deferred.
14. Every stage separately frozen — **YES** (manifest per-stage hashes + reports).
15. No quadratic path exists — **YES** (invariant-enforced; local path is O(N·W)).

## Required closing statements

**Phase Core:** implemented at v1.0; mathematical fidelity verified against an
independent hand-derivation (atol 1e-6) and against production standard-mode Phase
(≤2.4e-7); **frozen**.

**Streaming Phase:** batched scan equals token-by-token and chunked streaming to
≤2.4e-7 in float32 (bf16 ≤3e-2, documented); recurrent state memory is O(D),
constant across context length — **frozen (v1.1)**.

**Decay:** supported modes = none, fixed scalar, fixed per-head, learned per-head;
measured horizons H≈1/(1−γ) span ~2→~10⁵ tokens; γ=1 reproduces the non-decay
core; learned γ stays within [γ_min, γ_max]. Limitation: production's learned-decay
γ range/parameterization differs (matched by value in the harness) — **frozen (v1.2)**.

**Production equivalence:** max abs output difference ≤ **2.4e-7** in float32 for
the supported configuration (standard cosine, bounded phase, no/fixed/learned
decay, causal, train/eval, forward + gradients + state). Remaining differences
(shifted/complex modes, zero-mean cosine, dual-channel intent, multi-channel,
write gate, warm-start, learned-decay init) are enumerated, not silently weakened.

**Sliding window + Phase:** B−A distant-recall = **+0.741** (A≈chance 0.133, B=0.874),
across all 3 seeds, at 900 steps; resource cost = one extra O(N·D) additive path;
**verdict: Phase adds decisive value beyond local context at the tested scale.**
Full LM-quality/perplexity and natural-language long-context study deferred.

**Phase + bounded binding:** C−B and C−C-no-Phase are **not yet measured** (training
ladder deferred). Bounded slots: capacity = fixed M slots, O(M·D) persistent state,
O(N·M·D) compute, streaming updates; structure and complexity **frozen (v1.5)**.
No binding capability is claimed as demonstrated.

**The canonical lightweight Phase implementation is: FROZEN** (v1.0–v1.4 fully;
v1.5 structure/complexity frozen, validation ladder deferred).

**The next permitted extension is:** the Stage 8 binding validation ladder
(A/B/C/C-no-Phase) on a multi-fact/supersession task, **gated by** the acceptance
criterion `C > B` (binding adds value given Phase) **and** the diagnostic
`C > C-no-Phase` (Phase still contributes when binding is present), with the
C-no-Phase arm mandatory.

## The critical design choice

The minimal Phase core was frozen (v1.0) — with explicit equations, a golden gate,
and production equivalence — **before** training larger combinations. This prevents
the failure mode where the experiment, the documentation, and the production class
each implement a slightly different meaning of "Phase."
