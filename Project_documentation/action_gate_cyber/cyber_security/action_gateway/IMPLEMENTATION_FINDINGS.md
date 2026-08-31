# Implementation Findings — Action Gateway (runtime enforcement path)

Contradictions, gaps, or under-specifications the *runtime* layer exposed against
the frozen specifications. Per the integrity rule, the gateway does not silently
reinterpret the specs; genuine gaps are recorded here with the fail-closed
resolution taken. Findings internal to the reference harness itself are in
`../action_gate_reference/IMPLEMENTATION_FINDINGS.md` and are inherited unchanged.

Frozen sources:
- `../AGENT_ACTION_ADMISSIBILITY_MVP.md`
- `../ACTION_GATE_SPECIFICATION.md`
- `../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`
- `../ROADMAP.md`

---

## Finding #G1 — The frozen operation taxonomy is not tool-generic (gap)

**Where.** `ACTION_GATE_SPECIFICATION.md §2` fixes a ten-value operation
taxonomy (`IAM_GRANT_ADMIN`, `DEPLOY`, `DB_DELETE`, `NET_EXPOSE`, `SECRET_READ`,
`MONITORING_DISABLE`, `DB_MUTATION`, `KEY_ROTATE`, `CLOUD_SPEND_INCREASE`,
`EXTERNAL_COMMS`), and `schema.validate_envelope` rejects any other `operation`.
The gateway's mandate (this task, ROADMAP "generic tool interface first") is to
sit in front of *arbitrary* tools (filesystem, shell, HTTP, Terraform,
Kubernetes), whose verbs are not members of that taxonomy.

**Gap.** There is no frozen mapping from a generic tool verb to an operation
class, and the taxonomy cannot be extended without breaking the frozen
canonicalization/validation contract. A runtime gateway therefore *must*
introduce a translation layer, and any such mapping is a semantic approximation
(e.g. "filesystem delete" is modelled as `DB_DELETE` because both are
irreversible destructive operations; "terraform apply" as `DEPLOY`).

**Resolution (mapping layer, fail-closed on unknowns).** `action_gateway/mapping.py`
owns an explicit, auditable `(tool, verb) -> operation` table and per-verb
permission strings. An unmapped tool/verb raises (no default-allow). The mapping
performs **no** policy reasoning — admissibility is still decided solely by the
frozen gate against the mapped operation. The current table:

| tool.verb | operation | rationale |
|-----------|-----------|-----------|
| filesystem.write | DB_MUTATION | bounded mutation of stored state |
| filesystem.delete | DB_DELETE | irreversible destructive |
| filesystem.read | SECRET_READ | read of potentially sensitive data |
| shell.run | DEPLOY | executes an environment-changing action |
| http.request | NET_EXPOSE | outbound network interaction |
| terraform.apply / plan | DEPLOY | infrastructure change |
| kubernetes.delete | DB_DELETE | destructive resource removal |
| kubernetes.apply | DEPLOY | infrastructure change |

**Blast radius.** Mapping only. No hashing/approval/token/audit semantics are
affected; the mapped operation is a normal envelope field that flows through the
frozen pipeline unchanged.

**Recommended spec evolution (out of scope here).** A future spec revision
should either (a) define an extensible operation-class registry with per-class
invariant templates, or (b) standardize a `tool_taxonomy -> operation_class`
binding as a signed, versioned policy artifact so mappings are themselves
governed rather than hard-coded in the transport layer.

---

## Finding #G2 — Two decision outcomes share one runtime state (under-specification, benign)

**Where.** The task enumerates eight runtime states (`pending, approved,
executing, completed, failed, denied, escalated, expired`). The frozen gate
emits **six** decision outcomes, two of which (`SIMULATE_AND_RETRY`,
`REQUEST_MORE_EVIDENCE`) describe "not admissible yet, supply more inputs."

**Observation.** There is no dedicated runtime state for either; both are
non-executable "awaiting inputs" verdicts. Mapping both to `PENDING` is the only
consistent reading (a request stays pending until it is `APPROVED`, `DENIED`, or
`ESCALATED`). The specific outcome is preserved losslessly in the decision record
and the audit chain, so no information is lost — only the coarse lifecycle label
is shared.

**Resolution.** `state.OUTCOME_TO_STATE` maps both to `PENDING`; the exact
outcome is available via `status()` / the audit log. Re-evaluation with added
evidence/simulation advances the request. No spec change required.

---

## Finding #G3 — Approval-time vs. commit-time state ("TOCTOU") needs a state oracle the spec leaves abstract (note)

**Where.** `ACTION_GATE_SPECIFICATION.md §13/§15` require that a token only
authorizes a commit while the world still matches the approved-against
`current_state_hash`, but the source of that hash is (correctly) left to the
integrator.

**Observation.** Enforcing this at runtime requires a *state oracle* the frozen
harness deliberately does not provide. The gateway supplies a deterministic
`MockStateOracle` purely to demonstrate the TOCTOU rejection path; it is not a
real infrastructure state source.

**Resolution / boundary.** Modeled as a mock (see README "out of scope"). The
enforcement mechanism (`verify_token(current_state_hash=...)` →
`E_STALE_STATE`) is real and exercised; only the oracle behind it is mocked.

---

## Non-findings (checked, consistent)

- **Runtime state machine vs. spec state machine.** The task explicitly scopes
  the eight states as *runtime lifecycle* states, separate from the frozen
  decision `state_trace` (RECEIVED → … → COMMITTED/DENIED). The gateway records
  the frozen trace verbatim inside each decision and never mutates it. No
  conflict.
- **Present-but-invalid approval → DENY.** Inherited from harness finding #3;
  the gateway surfaces it via the normal decision path (e.g. the expired-approval
  demo). Consistent.
- **`ALLOW_WITH_CONSTRAINTS` execution.** The gateway executes constrained
  allows and carries the constraints into the token and audit record; constraints
  are not dropped (harness finding #2). Consistent.
