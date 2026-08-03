# Evidence & Provenance

Capability claims and capability *evidence* are distinct. A declared claim
(`AgentCapability.declared=True`) is audited but never treated as measured evidence.

## Provenance classes and precedence

`EvidenceClass` ∈ {`DECLARED`, `MEASURED`, `OBSERVED`}. Trust precedence:

```
OBSERVED (3)  >  MEASURED (2)  >  DECLARED (1)
```

This matches the AWC Phase 0 design (observed > measured > declared) and is
consistent with Model Selection's source precedence (live_probe/telemetry over
config/provider-declared).

## Enforcement (`_check_capability_evidence`)

For each required capability the agent claims, the engine finds the
highest-precedence **non-expired** evidence class for the exact `(agent_id,
agent_version, capability_id)` and compares its rank to the required rank
(strongest of the role's / enterprise's `required_evidence_classes`, defaulting to
`MEASURED` when `require_measured_or_observed_for_hard`):

- no evidence, but declared, and MEASURED+ required → `DECLARED_ONLY_WHEN_MEASURED_REQUIRED`
- only expired matching evidence → `CAPABILITY_EVIDENCE_EXPIRED`
- evidence only for a different agent version → `CAPABILITY_EVIDENCE_VERSION_MISMATCH`
- no evidence and none required-satisfiable → `UNKNOWN_REQUIRED_EVIDENCE` (fail-closed)
- best class below required rank → `CAPABILITY_EVIDENCE_INSUFFICIENT`
  (or `DECLARED_ONLY_WHEN_MEASURED_REQUIRED` when best is DECLARED)

Expiry is controlled by the **injected** `logical_time` (`valid_until`), so replays
are deterministic. Evidence for one agent version never satisfies another (version
pinning). Synthetic fixtures set `provenance.synthetic = True`; no fixture asserts
real empirical evidence.
