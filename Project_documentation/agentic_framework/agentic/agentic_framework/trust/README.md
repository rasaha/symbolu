# `trust/` — Trust-Observable layer (Phase 1, product)

The explicit, typed formalization of the Agentic Framework's **proven** governance
signals. It is the product realization of
[`AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md`](../../../root_brief/AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md),
Phase 1. It adds **no new ML** and **no CG research features** — it wraps and structures
logic the gateway already runs, and makes the trust decision auditable.

## Trust Signal vs Validator (the core distinction)

- A **trust signal** is something the **model emits/claims** ("this is safe", high
  confidence). It is *gameable* — a prompt-injected or sycophantic model can assert it
  for free. Therefore trust signals are **asymmetric**: admitted doubt may *lower* trust,
  but a confident claim can **never raise** it.
- A **validator** is an **independent inferred check** (raw entropy, tool validity, the
  confidence-risk gap). Validators *cap* trust — a single proven validator that says
  UNSAFE/UNSURE dominates; it is never averaged away by confident claims.

The decision **compares** them: when the model claims "safe" but a validator disagrees on
a non-trivial action → escalate or block. This is the confidence-risk gap, generalized.

## Why this is NOT CG read-out governance

The earlier CG path derived governance from **unsupervised hidden-state read-outs**
(vritti/guna/kosha) and a heuristic JEPA rulebook. Those measured the wrong objects
(guna *imbalance*, not predictive uncertainty) and underperformed raw entropy. This layer
uses only **proven, independently-inferred** signals; CG-state read-outs are declared
`RESEARCH` (see `CG_RESEARCH_OBSERVABLES`) and **never affect the decision**.

## The model

Two axes per observable (`observables.py`):

| `ObservableType` | role | `EvidenceStatus` | authority |
|---|---|---|---|
| `HARD_VETO` | deterministic correctness check | `PROVEN` | may BLOCK |
| `VALIDATOR` | independent inferred check | `PROVISIONAL` | may CONFIRM, never BLOCK |
| `TRUST_SIGNAL` | model-emitted claim (asymmetric) | `RESEARCH` | recorded only, never affects decision |
| `ADVISORY` | surfaced/logged, may CONFIRM | | |

Decision rules (`decision.py`), most-severe-wins (BLOCK > CONFIRM > ALLOW):
1. **Hard gates first** — a PROVEN `HARD_VETO` UNSAFE → BLOCK.
2. **Staged authority** — only PROVEN may BLOCK; PROVISIONAL/ADVISORY cap at CONFIRM;
   RESEARCH never affects the decision.
3. **Validators cap trust** — PROVEN `VALIDATOR`: UNSAFE → BLOCK, UNSURE → CONFIRM.
4. **Asymmetry** — `TRUST_SIGNAL`: admitted doubt → CONFIRM; confident claim → no upgrade.
5. **Weakest link** — the final decision is the most severe proposed; nothing averages it.

## Phase-1 production observables (`registry.observe_tool_call`)

| observable | type | source (existing, proven) |
|---|---|---|
| `tool_validity` | HARD_VETO | caller registration flag |
| `budget_gate` | HARD_VETO | caller budget-exceeded flag |
| `raw_entropy` | VALIDATOR | `raw_entropy_adapter.resolve_raw_entropy_signal` |
| `confidence_risk_gap` | VALIDATOR | `confidence_risk_gap.assess_confidence_risk_gap` |
| `approval_required` | VALIDATOR | `MCPToolDefinition.requires_confirmation` |
| `verbalized_safety` | TRUST_SIGNAL | `MCPToolCall.verbalized_safety_confidence` |
| `action_risk` | ADVISORY | tool risk level (modulates the gap; not a blocker) |

**First production observables:** `raw_entropy` and the `confidence_risk_gap` — the two
signals that survived falsification and demonstrated practical value.

## Promotion path for future observables

A new observable advances **research → advisory → validator → veto**, each stage gated by
evidence (see the architecture doc §4): it must beat the proven baseline (risk taxonomy +
raw entropy + tool validity) on held-out confident-unsafe scenarios — DeLong-significant,
replicated, with operational lift — before it can *cap trust*; and clear additional
stability/over-block bars before it can *block*. CG-derived candidates may compete on
exactly these terms; until then they stay `RESEARCH` and off.

## CG off-by-default note

Phase 1 also closes a partial off-switch in the gateway: `enable_cg_state_signals=False`
now drops CG-derived `vritti_result`/`entropy_result` before they reach the JEPA regime
(previously only the CG-entropy *penalty* was gated). With the default adapters (no CG
metadata) this is a no-op.
