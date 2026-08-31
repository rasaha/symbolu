# Native ActionGate Vocabulary Contract (Phase 5 — MANDATORY)

*`bounded_shadow_pilot/actiongate_contract.py`. The pilot's answer to the non-negotiable mandate: the
native ActionGate semantics must survive end-to-end without collapse. This contract invokes the real
frozen gate read-only and preserves **all six** native outcomes and their metadata with **zero loss**.*

## The problem it fixes

The customer-shadow-readiness adapter (`real_action_gate.py`, consumed read-only) mapped the gate's six
native outcomes onto a four-value shadow vocabulary, collapsing three of them:

| Native outcome | Shadow value | Information lost |
|---|---|---|
| `ALLOW_WITH_CONSTRAINTS` | `CONSTRAIN` | applied constraints identity |
| `REQUEST_MORE_EVIDENCE` | `INDETERMINATE` | evidence-request semantics |
| `SIMULATE_AND_RETRY` | `CONSTRAIN` | simulation + retry semantics |

That was a tracked integration refinement in the readiness track. This pilot must not carry it forward:
**a semantic loss in a safety-relevant native outcome is a pilot blocker.**

## What the contract preserves (verbatim, never collapsed)

- **Outcomes** — `ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`,
  `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY`, each kept in `native_outcome` exactly as the gate
  returned it.
- **Metadata** — applied constraints; approvals required/satisfied; evidence requirements; simulation;
  retry; reason codes / dispositive rules; policy references; `action_hash`; `policy_hash`;
  `hash_algorithm_id`; full `state_trace`; `terminal`; `reason`.
- **Semantic role flags** — each outcome carries structured flags (`requires_human`,
  `requires_evidence`, `requires_simulation`, `requires_retry`, `requires_constraints`, `permits`,
  `blocks`) that *describe* it without remapping it. The flags are additive; the identity is untouched.

## Conformance — all six outcomes reproduced

Deterministic fixtures (drawn from the reference gate's own acceptance/transition suites) drive the real
gate to each native outcome; the contract reproduces every one verbatim:

| Expected | Reproduced | Dispositive rule | Notes |
|---|---|---|---|
| ALLOW | ALLOW | R2 | DEPLOY happy path |
| ALLOW_WITH_CONSTRAINTS | ALLOW_WITH_CONSTRAINTS | R5 | SECRET_READ; carries constraints |
| DENY | DENY | R3 | DB_DELETE missing hard MUST_HAVE (backup) |
| ESCALATE_TO_HUMAN | ESCALATE_TO_HUMAN | R3 | irreversible op, fully approved, still needs a human |
| REQUEST_MORE_EVIDENCE | REQUEST_MORE_EVIDENCE | R1 | IAM grant, dual approval, no attestation |
| SIMULATE_AND_RETRY | SIMULATE_AND_RETRY | R2 | DEPLOY artifact present, simulation absent |

`conformance().all_native_outcomes_preserved == True` (6/6).

## Pilot-blocker gate

`semantic_loss_report()` is the blocker check:

- **native_semantic_loss_pct = 0.0** — no native outcome is lost or downgraded.
- **safety_relevant_outcomes_lost = []** — none of the five safety-relevant outcomes
  (`ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`, `REQUEST_MORE_EVIDENCE`,
  `SIMULATE_AND_RETRY`) is collapsed.
- **recovered_by_native_contract = {ALLOW_WITH_CONSTRAINTS, REQUEST_MORE_EVIDENCE, SIMULATE_AND_RETRY}**
  — exactly the three the shadow mapping collapsed (`outcomes_collapsed_under_shadow_mapping = 3`).
- **blocker = False.**

The percentage here is a *structural* measure (distinct-vocabulary and per-outcome preservation); it is
labelled precisely so it is not confused with the readiness track's case-level 25% figure. The two
describe different things and do not conflict: the readiness study measured loss over decided cases; this
contract measures preservation of the outcome vocabulary itself.

## Fail-closed and non-enforcing

- A gate error or malformed operation yields `native_outcome="GATE_ERROR"`, `is_native=False`,
  `blocks=True`/`fail_closed=True` — a **non-native, never-permissive** decision. A gate error is never
  silently mapped onto a real outcome.
- `evaluate(None)` returns `None` — an advisory-only artifact proposes no action, so there is nothing to
  gate.
- The gate only **decides**; the pilot never executes. Deterministic (fixed reference clock).

## Tests

`bounded_shadow_pilot/tests/test_actiongate_contract.py` — 8 tests: all-six preserved, metadata
preserved, distinct semantic roles, zero safety-relevant loss / no blocker, recovery of the three
shadow-collapsed outcomes, fail-closed gate error, no-action → None, determinism.
