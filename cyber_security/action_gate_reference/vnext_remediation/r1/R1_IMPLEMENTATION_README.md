# R1 — Additive Remediation Projection (implementation)

Implements the **first phase** of the vNext remediation design: optional, deterministic,
advisory remediation metadata on ActionGate decision responses. **ActionGate becomes more
informative without becoming more permissive.**

## What shipped
- `action_gate_ref/remediation.py` — a pure, deterministic, side-effect-free projection layer.
- `action_gate_ref/cli.py` — opt-in `decide --remediation-mode …` (default `off`).
- `tests/test_remediation.py` — 38 tests (compatibility, correctness, security, robustness, CLI).
- Docs in this folder.

## Core guarantees (all tested)
- **Decision purity.** The gate decision is finalized first; the projection only *reads*
  `(envelope, signed_policy, evidence, approvals, state)` and never feeds back. Removing the
  projection changes no outcome.
- **No new permissiveness.** DENY-causing conditions (FORBID, hard `MUST_HAVE`, `PRIV_MONO`,
  `TICKET_SOD`, present-but-invalid approval) are always `TERMINAL` and never retryable — no
  policy metadata can upgrade them.
- **Hash/binding invariance.** `action_hash`, `policy_hash`, approval/evidence binding, the
  audit payload, and all 24 conformance vectors are untouched (remediation is excluded from
  every hashed surface). Existing suite: **161 passed**, conformance **24/24**.
- **Determinism.** Byte-identical output for identical inputs + explicit `now`; stable
  ordering (severity → policy rule order → rule id → field path → change id); no random ids,
  no wall-clock access inside the projection.

## Correctness by construction
The projection re-uses the gate's OWN predicates (`gate.extract_facts`, `_has_evidence`,
`_attestation_ok`, `_approver_satisfied`, `_priv_monotonic`, `_ticket_self_authored`,
`_stale`, `_SEVERITY`, `_REVERSIBILITY_ORDER`) rather than re-implementing them, so the
unmet-condition set it reports cannot diverge from what the gate evaluated.

## Usage
```python
from action_gate_ref import gate, remediation
decision = gate.evaluate(envelope, signed_policy, evidence=ev, approvals=ap, now=NOW)
rem = remediation.project_remediation(
    decision, envelope, signed_policy, evidence=ev, approvals=ap, now=NOW,
    disclosure_mode="STANDARD")            # OFF|MINIMAL|STANDARD|TRUSTED_PLANNER|HUMAN_ONLY|FULL
response = remediation.attach(decision, rem)   # new dict; decision unchanged
# or one-shot:
response = remediation.decide_with_remediation(gate, envelope, signed_policy,
             evidence=ev, approvals=ap, now=NOW, disclosure_mode="STANDARD")
```
CLI:
```
python -m action_gate_ref.cli decide env.json --now <ts> --remediation-mode standard
# privileged (non-production) disclosure requires an explicit admin flag:
python -m action_gate_ref.cli decide env.json --now <ts> --remediation-mode full --trusted-admin
```

## What R1 does NOT do
No planner, no retry orchestration, no auto-execution, no prompt rewriting, **no seventh
outcome**, no reinterpretation of the six outcomes. R1 is response projection only. Every
revised action requires a fresh evaluation and, where material fields change, fresh approval
and authority.

See: `R1_RESPONSE_SCHEMA.md`, `R1_OPERATOR_MATRIX.md`, `R1_DISCLOSURE_EXAMPLES.md`,
`R1_MIGRATION_NOTES.md`, `R1_SECURITY_LIMITATIONS.md`, `R1_IMPLEMENTATION_FINDINGS.md`.
