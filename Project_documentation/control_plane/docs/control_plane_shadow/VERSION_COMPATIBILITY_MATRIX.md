# Version Compatibility Matrix

*Phase 14. Versioning was the top operational risk in the prior track. This matrix pins every
version dimension and defines behavior on mismatch. **No silent coercion across incompatible
majors.** Source of truth: `control_plane_shadow/versioning.py`.*

## Pinned versions (this pilot)

| Dimension | Pinned | Supported majors | On mismatch | On missing |
|---|---|---|---|---|
| envelope | `1` | {1} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |
| contracts | `1` | {1} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |
| policy | `policy_v1` | {policy_v1} | `POLICY.POLICY_VERSION_MISMATCH` | fail-closed |
| registry | `reg_v1` | {reg_v1} | `POLICY.REGISTRY_VERSION_MISMATCH` | fail-closed |
| tap | `tap_e4_governance_F` | {…_F} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |
| action_gate | `action_gate_ref_v1` | {…_v1} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |
| audit | `control_plane_audit_v1` | {…_v1} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |
| vocabulary | `gov_vocab_v1` | {gov_vocab_v1} | `POLICY.CONTRACT_VERSION_UNSUPPORTED` | fail-closed |

## Scenario behavior (verified)

| Scenario | Behavior | Verified |
|---|---|---|
| backward-compatible read (supported major) | `OK` | `check('envelope','1') → OK` |
| forward-incompatible (higher unsupported major) | rejected, no coercion | `check('envelope','2') → FORWARD_INCOMPATIBLE` |
| missing version | fail-closed | `check(...,None) → MISSING` |
| unsupported/unknown dimension | fail-closed | `check('bogus',...) → UNKNOWN` |
| mixed-version trace | first incompatible dimension terminates | `first_incompatible()` returns the offender |
| mid-trace policy update | rejected — versions pinned per trace (invariant 10) | orchestrator layer-1 check |
| mid-trace registry update | rejected — `REGISTRY_VERSION_MISMATCH` | trace T16 |
| replay under historical versions | uses the pinned versions from the record | `control_plane.replay` (prior track) |
| adapter downgrade | supported-major check; downgrade below supported ⇒ rejected | `SUPPORTED` sets |
| rolling deployment mismatch | each trace pins its own set; mismatched node fails that trace closed, not the fleet | per-trace pinning |

## Rules

- **Pins are per-trace immutable** (invariant 10). A version cannot change mid-trace; a change is
  a new trace under new pins, never a silent upgrade.
- **No silent coercion across majors.** An unsupported major is `FORWARD_INCOMPATIBLE` and
  terminates the trace with a namespaced `POLICY.*` code — it is never read "best-effort."
- **Missing ⇒ fail-closed**, never assumed-latest.
- **Rolling deployments stay correct per request:** a node on an unsupported version fails only
  the traces it touches (closed), so a partial rollout degrades availability, not safety. This is
  the operational-fragility/​safety trade-off flagged in the prior track, made explicit here.

## Traces exercising versioning

- T16 stale registry ⇒ `REJECTED / POLICY.REGISTRY_VERSION_MISMATCH`
- T17 stale policy version ⇒ `REJECTED / POLICY.POLICY_VERSION_MISMATCH`
- T25 incompatible envelope version ⇒ `REJECTED / POLICY.CONTRACT_VERSION_UNSUPPORTED`
