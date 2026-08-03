# H16 Canonicalization Status

The Phase 0 reconciliation ADR
(`docs/architecture/ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`, Option A)
canonicalizes deterministic agent selection into AWC while H16 retains runtime
coordination, dispatch, recovery, live availability, runtime fallback, and
`LLMRouter`. **P1 does not modify H16, does not move any H16 runtime class, and adds
no H16 compatibility facade.** Runtime migration belongs to a later phase (P4).

## Canonical `AgentProfile` vs H16 runtime `AgentProfile`

The live H16 runtime profile is `agentic/agentic_framework/coordination.py:116`:
`agent_id, role, capabilities: FrozenSet[str], permissions: FrozenSet[str],
owned_tools: FrozenSet[str], supported_goals: FrozenSet[str], execution_limits,
trust_level: int`.

| Aspect | H16 runtime `AgentProfile` | AWC `AgentProfile` (this package) |
|---|---|---|
| Purpose | runtime **authority envelope** | planning-time **evidence-backed selection manifest** |
| Capabilities | flat `FrozenSet[str]` | `AgentCapability` claims + DECLARED/MEASURED/OBSERVED evidence |
| Evidence / provenance | none | first-class (`AgentCapabilityEvidence`, `provenance`) |
| Versioning | none | `agent_version`, validity window, content `profile_fingerprint` |
| Mutability | availability tracked externally | frozen, immutable, hashable |
| Namespace | `agentic.agentic_framework` | `ugence_agent_workforce_composer` (distinct type) |

Because the field sets diverge substantially, the Phase 0 "identity-preserving
re-export" is **not** viable; AWC's profile is a distinct canonical type. The
`COMPATIBILITY_FACADE_CANDIDATE` disposition is therefore deferred, consistent with
the ADR open question resolved by this field diff.

Maturity: `h16_migration_implemented = false`.
