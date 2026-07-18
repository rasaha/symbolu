# Implementation Findings — Action Gateway MCP integration

Contradictions, ambiguities, and decisions the protocol-facing integration
exposed. Per the integrity rules, nothing in the frozen specifications was
weakened to simplify the build, and no security primitive from
`action_gate_ref` was duplicated. Findings internal to the reference harness and
the runtime gateway are in their own `IMPLEMENTATION_FINDINGS.md` files and are
inherited unchanged.

For every finding below: **no frozen hash, approval, token, evidence, or decision
outcome semantics were changed.** Where the runtime gateway (`action_gateway`)
was modified, the changes are additive strengthenings or runtime-lifecycle
adjustments that the runtime gateway itself explicitly owns (its runtime states
are, by its own contract, separate from the frozen decision state machine).

Frozen sources: `../ACTION_GATE_SPECIFICATION.md`,
`../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`,
`../AGENT_ACTION_ADMISSIBILITY_MVP.md`, `../ROADMAP.md`. The frozen harness lives
at `../action_gate_reference/action_gate_ref/` (imported transitively via
`action_gateway`).

---

## Finding #M1 — `ESCALATED` had to become a non-terminal runtime state

**Clauses.** Task §9 (human-escalation) and demo #5 require: *"Kubernetes delete
escalates to a human and executes only after exact-action approval."* The runtime
gateway (`action_gateway/state.py`) originally modeled `ESCALATED` as **terminal**,
so an approval could never re-admit the request to evaluation.

**Resolution (narrow).** `ESCALATED` is now non-terminal: legal transitions
`ESCALATED -> {APPROVED, DENIED, PENDING, EXPIRED}` were added, and `DENY`
remains the only decision-terminal state. `evaluate_action` may re-run on an
`ESCALATED` request when a human approval arrives. This is a change to the runtime
lifecycle machine only.

**Security impact.** Strictly enabling, not weakening: an escalated request still
has **no execution token** and cannot execute; it can only advance to `APPROVED`
by a valid, exact-action, exact-policy approval that passes the frozen
`verify_approval` (dual-control, SoD, expiry, nonce, scope). Existing runtime
tests remain green.

**Frozen semantics changed?** No. The frozen decision outcomes and the frozen
decision `state_trace` are untouched; only the runtime lifecycle machine (which
`action_gateway` documents as distinct from the spec machine) changed.

---

## Finding #M2 — Read-only tools are served outside the mutating gate

**Clauses.** Task §4 defines a *discovery/read-only phase* that "may expose tool
schemas and non-sensitive metadata without execution authority." The frozen
operation taxonomy (`ACTION_GATE_SPECIFICATION.md §2`) has no generic READ
operation (only `SECRET_READ`, which requires an approver).

**Resolution.** `kubernetes.get`, `iam.inspect`, and `terraform.plan` are
registered as `read_only=True` and served by dedicated read-only handlers
(`readonly.py`) that return only mocked, non-sensitive metadata. They construct
no mutating action envelope, obtain no credential, and mint no execution token.
They are audited in the protocol chain.

**Security impact.** Reads carry no execution authority and cause no side effects.
A production deployment must guarantee read handlers expose only genuinely
non-sensitive data (e.g. a real `iam.inspect` must not leak secret material);
here they are mocks.

**Frozen semantics changed?** No.

---

## Finding #M3 — `kubernetes.delete` is mapped as `REVERSIBLE_WITH_COST`

**Clauses.** Demo #5 requires a Kubernetes delete to be *approvable* and then
executable. `DB_DELETE`'s default reversibility is `IRREVERSIBLE`, and rule `R3`
applies `MAX_IRREVERSIBILITY REVERSIBLE_WITH_COST`; an `IRREVERSIBLE` delete
therefore always escalates or denies and can never be approved to `ALLOW`.

**Resolution (narrow, explicit in the registry).** The mapping registry declares
`kubernetes.delete` with `reversibility=REVERSIBLE_WITH_COST` **and** requires a
`verified_restorable_backup` plus a rollback plan and dual-control approval — the
justification being that a cluster resource with a verified, restore-tested
backup is recoverable at cost. By deliberate contrast, `filesystem.delete` is
mapped `IRREVERSIBLE` and remains hard-denied (demo #3), so the distinction is
intentional and visible.

**Security impact.** The reversibility class is an envelope field the mapping
layer is responsible for; the gate still enforces the backup precondition
(hard `MUST_HAVE`) and dual-control approval. Mis-declaring reversibility would be
a mapping error, not a gate weakness — which is why the registry is explicit,
tested for coverage, and fails closed on unknown tools.

**Frozen semantics changed?** No — `reversibility` is per-action envelope data.

---

## Finding #M4 — Runtime gateway extended with IAM + monitoring adapters (additive)

**Clauses.** The exposed tool surface (task §1) includes `iam.grant` and
`monitoring.disable`, which map to the frozen operations `IAM_GRANT_ADMIN` and
`MONITORING_DISABLE` — both already in the taxonomy but not previously wired with
runtime adapters.

**Resolution.** `action_gateway` gained mock `IamTool` and `MonitoringTool`
adapters and the corresponding `(tool, verb) -> operation` and permission entries.
Purely additive.

**Security impact.** None negative; the new adapters are mock and, like all
others, require a broker capability.

**Frozen semantics changed?** No.

---

## Finding #M5 — Single-use capabilities + execution lock added to the runtime gateway (additive)

**Clauses.** Task §5 ("capability is single-use") and §6/demo #15 ("parallel
duplicate execution permits at most one commit", "replayed broker capability
rejected").

**Resolution.** `MockCredentialBroker.validate` now consumes a capability on use
(a second validation of the same capability fails closed), and `Gateway`
serializes evaluate/execute under a lock so a token nonce is reserved atomically
(at most one commit under concurrency). Both are additive strengthenings.

**Security impact.** Strictly strengthening. Existing runtime tests remain green.

**Frozen semantics changed?** No.

---

## Finding #M6 — Build provenance (`signed_artifact`) is auto-supplied for DEPLOY

**Clauses.** `DEPLOY` (rule `R2`) requires both a `signed_artifact` (`MUST_HAVE`)
and a high-fidelity simulation. Demo #4 emphasizes the *simulation* step.

**Resolution.** The registry marks `signed_artifact` as `auto_evidence` for
`terraform.apply` / `kubernetes.apply`: the MCP layer attaches it at evaluation
time as a stand-in for CI/registry-provided build provenance, leaving simulation
as the interactive requirement. The evidence is a bound envelope produced via the
frozen `evidence` primitive; it is not a bare assertion.

**Security impact.** In production the signed artifact must be a real verified
build attestation (e.g. SLSA provenance), not an auto-generated stand-in. This is
a reference modeling choice, clearly labeled.

**Frozen semantics changed?** No.

---

## Non-findings (checked, consistent)

- **A protocol request is never execution authority.** `prepare`/`evaluate` never
  execute; `execute` requires a gateway-minted token verified against the actual
  call plus a broker capability. No MCP handler invokes an adapter directly (the
  only adapter calls are inside `action_gateway.Gateway.execute_action`).
- **No debug/test bypass in runtime paths.** The `_commit` overrides
  (call_envelope / requested_permissions / active_policy_hash) used by the
  red-team demos can only *cause rejection*; the public `execute` never passes
  them. There is no path that relaxes a check.
- **Simulation is never `safe: true`.** `simulation.py` emits structured
  predicted-change content bound to the action hash, state hash, producer version,
  and validity interval; changing the action changes the hash and unbinds it.
