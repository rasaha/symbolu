# Final Evaluation Report (Phase 27)

*Synthesis against the frozen protocol (`EVALUATION_PROTOCOL.md`). All numbers come from the hash-pinned
artifacts (`verify_frozen.py`). Corpus: `gip_corpus_v1`, 384 end-to-end fixture cases, 12 partitions ×
8 domains. This is a shadow-only composition study; **no production validation is claimed.***

## 1. Headline

The completed components **compose into one coherent, auditable, replayable control plane**. The full
stack reaches **zero unsafe assertion escape and zero unsafe action escape at zero false-blocking**,
with **complete audit and deterministic replay on every case**, and **every injected fault fails
closed**. A small **mandatory safety core** (EvidenceAssurance + ActionGate) carries the safety;
several components are optional for the safety endpoint on this corpus.

## 2. Primary & co-primary endpoints (by baseline)

| Baseline | unsafe assertion ↓ | unsafe action ↓ | false-block ↓ | unresolved |
|---|--:|--:|--:|--:|
| **J_full (full stack)** | **0.000** | **0.000** | **0.000** | 0.125 |
| I_full_no_scope | 0.000 | 0.000 | 0.000 | 0.125 |
| L_full_no_ci | 0.000 | 0.000 | 0.000 | 0.125 |
| P_oracle | 0.000 | 0.000 | 0.000 | 0.083 |
| H_ea_assertion | 0.083 | 0.083 | 0.000 | 0.125 |
| K_full_no_ea | 0.167 | 0.000 | 0.000 | 0.083 |
| E_assertion_only / G / O_mvc | 0.250 | 0.083 | 0.000 | 0.000 |
| F_action_only | 0.333 | 0.000 | 0.000 | 0.000 |
| A–D (no / exec governance) | 0.500 | 0.167 | 0.000 | 0.000 |

The full stack is the **safety frontier at zero false-block**: every simpler baseline leaks 0.08–0.50
unsafe escape, and no baseline over-blocks a clean case.

## 3. Stratification (full stack)

- **By risk tier:** unsafe assertion + action escape is **0.000 in every tier** (low, medium, high).
  There is no unsafe high-risk subgroup.
- **By partition:** every failure partition resolves to a safe withhold; every CLEAN partition to a
  supported delivery; CONTRACT_OR_METADATA_FAILURE → CONTRACT_ERROR; AMBIGUOUS → INDETERMINATE. The
  unresolved 0.125 is the AMBIGUOUS + evidence-indeterminate cases (safe flags, not wrong deliveries).

## 4. Composition integrity

- **Audit completeness: 1.000.** Every non-catastrophic run produced a complete immutable trace.
- **Replay determinism: 1.000.** Every case reproduces its replay signature byte-for-byte.
- **Fault-injection safety:** all 21 faults fail closed on the clean partitions (0 unsafe fallbacks,
  auditable 1.0); integrity faults detected at replay.
- **Contract failures:** the 8 safety-critical handoffs fail closed; unknown vocabulary and missing
  fields never produce a permissive outcome.
- **Dispositions keep meaning across boundaries:** an action block outranks an assertion allow;
  reason codes are forwarded, never rewritten; stage-local outcomes are preserved alongside the final.

## 5. Cascade & mandatory core

- **EvidenceAssurance drives 128 of the safety withholds** — the dominant safety contributor.
- **ActionGate is the sole driver of the 64 action-policy withholds.**
- 256 cases carry a contradictory stage decision, all correctly resolved by precedence (never an allow
  averaged against a withhold); 48 redundant withholds.
- **MVC study:** mandatory core = {EvidenceAssurance, ActionGate}. Removing ExecutionGate, ModelPolicy,
  ClaimIntegrity, ScopeIntegrity, or AssertionGate leaves unsafe escape at 0 on this corpus
  (AssertionGate is redundant *with* EvidenceAssurance here; ClaimIntegrity/ScopeIntegrity's end-to-end
  value is narrow, matching their own studies).

## 6. Latency, cost, human review

- Latency (deterministic units): median 6, p95 7 — small governance overhead; production latency is
  dominated by the model call the pilot does not make.
- Cost: governance token cost ≈ 0 in fixture mode; not the deployment barrier.
- Human review (simulated, labeled): reviewer agreement 0.917, override 0.083 toward escalation on bare
  high-risk allows, reason-code coverage 1.0.

## 7. Serious examples

- **Adversarial composition** (aligned-but-wrong evidence, supportive signals): the full stack withholds
  all 32 (EvidenceAssurance rejects the correlated-failure evidence state) — a signal-only pipeline
  would deliver these.
- **Multi-stage failure** (conflicted evidence + irreversible action): resolves to WOULD_BLOCK_ACTION —
  the action block surfaces even though claim/execution succeeded.
- **No serious false-block or unsafe-escape example exists** in the full stack (both rates 0.000).

## 8. Negative / honest findings

- **ClaimIntegrity and ScopeIntegrity add no unsafe-escape reduction end-to-end on this corpus.** They
  serve claim traceability and the narrow scope-conjunction fix (validated in their own studies), but
  the pilot does not show an end-to-end safety gain for them here.
- **The unresolved rate (0.125) is the availability cost** of composing abstaining stages — safe, but
  a real operational load (human review or whole-span evaluation).
- **All rates are construction properties** of a deterministic self-built corpus. The pilot establishes
  composition correctness and structured-case safety; it does **not** establish production behavior.

## 9. Verdict against the frozen decision rules

| Rule | Outcome |
|---|---|
| Full stack materially lowers unsafe escape vs baselines | **Met** — 0.000 vs 0.08–0.50 |
| Bounded false-block | **Met** — 0.000 |
| No unsafe high-risk subgroup | **Met** |
| Deterministic replay + complete audit | **Met** — 1.000 / 1.000 |
| Every fault fails closed; no external action | **Met** |
| ≥1 commercially plausible minimum configuration | **Met** — the {EA, AssertionGate, ActionGate} core |

Every frozen success criterion is met **on the shadow corpus**. Production readiness is assessed
separately (Phase 28) and is **not** claimed here.
