# TAP-E4 — Governance Resolution (canonical import package)

This package is the **canonical engineering import path** for the Governance Resolution
layer. It is a **thin re-export / compatibility layer only** — it contains no copy of the
engine. All symbols are re-exported *by identity* from the historical implementation package
`truth_assurance_pipeline.tap_e4_governance_truth`.

> **Historical package path retained for experiment reproducibility. The canonical
> engineering name is Governance Resolution.** The directory `tap_e4_governance_truth/`,
> its experiment IDs, stored manifests, result JSONs, and `frozen_components_hash` are
> unchanged; they embed the original name by necessity.

## Canonical import contract

**All new downstream work must import E4 through this package:**

```python
from truth_assurance_pipeline.tap_e4_governance_resolution import (
    GovernanceResolver, GovernanceSituation, GovernanceRecord, config,
)
rec = GovernanceResolver(config("F")).resolve(intent, retrieval, relationship, situation)
```

The historical import path continues to work unchanged and is retained only for frozen
experiments, stored manifests, backward compatibility, reproducibility, and existing
internal references that cannot safely move:

```python
from truth_assurance_pipeline.tap_e4_governance_truth import GovernanceTruthLayer, Situation
```

Hash-protected source files are **not** edited merely to change import wording.

## Public symbols (re-exported by identity)

| Canonical name | Historical symbol | Kind |
|---|---|---|
| `GovernanceResolver` | `GovernanceTruthLayer` | resolver class (`.resolve(...)`) |
| `GovernanceSituation` | `Situation` | caller-supplied input record |
| `GovernanceDecision` | `GoverningDecision` | per-decision structure |
| `GovernanceRecord` | `GovernanceRecord` | sole serialized output |
| `GovernanceConflict`, `GovernanceGap`, `GovProvenance`, `GovernanceConfidence`, `RejectedAuthority` | same | record sub-structures |
| `GovStatus`, `GovConflictType`, `GovGapCode`, `AuthorityTier` | same | enums |
| `GovernanceConfig`, `BASELINES`, `config` | same | ablation configuration |
| `validate_record`, `SCHEMA_VERSION`, `AUTHORITY_MODEL_VERSION` | same | schema helpers/versions |

`GovernanceResolver`, `GovernanceSituation`, and `GovernanceDecision` are **aliases** — the
identical objects (`canonical.X is historical.Y`). No new serialized type is created, no
dataclass field is added or changed, and the schema version is unchanged. There is no
module-level `resolve_governance` function in the implementation; resolution is
`GovernanceResolver(config(name)).resolve(...)`.

## `GovernanceSituation` — the input contract

`GovernanceSituation` is *a normalized representation of the operational facts needed to
determine whether a documented authority, policy, version, scope, exception, or temporal
rule applies to the present case.* It is an **explicit caller-visible input**, not hidden
ground truth magically supplied to the resolver, and not a fact source owned by E4.

```
IntentRecord
      +
Explicit application / runtime metadata
        ↓
GovernanceSituation
        ↓
Governance Resolution
```

### Governance Situation Ownership

- **TAP-E1** owns analysis of the user's intent.
- **The calling application or runtime** owns authoritative operational metadata.
- **TAP-E4** may normalize those inputs into a `GovernanceSituation`.
- **TAP-E4 does not** discover operational facts from the real world.
- **TAP-E4 does not** retrieve missing situation metadata.
- **TAP-E4 does not** invent a role, jurisdiction, customer, contract, environment,
  effective time, or emergency state.
- **TAP-E4 may only** apply bounded deterministic normalization to explicitly supplied
  inputs.
- **Missing or contradictory situation facts must remain unresolved and must not be
  silently repaired.**

### Actual implemented fields

The current `Situation` dataclass implements exactly these fields (all optional; string
defaults `""`, `date_year` defaults `None`). No other fields exist; none are added here.

| Field | Meaning | Normalized form | Source | Optional? | Absent → | Contradiction → |
|---|---|---|---|---|---|---|
| `jurisdiction` | governing jurisdiction of the case | lower-case token (e.g. `us`, `eu`) | application/runtime metadata | required only for jurisdiction-scoped authorities | candidate kept at **reduced** `jurisdiction_confidence` (0.4); a global/empty-jurisdiction authority applies broadly; no value is invented | not representable (single value) — must be detected before construction |
| `user_role` | actor role in the case | lower-case token (e.g. `contractor`, `engineers`) | application/runtime metadata | required only for role-scoped authorities | role-scoped candidates kept at **reduced** `scope_confidence` (0.4); no role value is invented | not representable — detect before construction |
| `environment` | operating environment (e.g. `production`, `emergency`) | lower-case token | application/runtime metadata | required only for environment-scoped authorities | environment filter is skipped; `scope_confidence` unaffected/low | not representable — detect before construction |
| `date_year` | effective year of the case | `int` (e.g. `2026`) | application/runtime metadata | required for temporal/expiry/supersession/future resolution | temporal status defaults to `EFFECTIVE` at **reduced** `temporal_confidence` (0.4–0.5); expired/future cannot be ruled in/out | not representable — detect before construction |
| `contract` | governing customer contract id | lower-case token | application/runtime metadata | informational; contract precedence derives from the evidence unit's document type | no effect beyond contract-tier evidence | not representable — detect before construction |
| `product` | product in scope | lower-case token | application/runtime metadata | not consumed by the current resolver | no effect | n/a |
| `business_unit` | business unit in scope | lower-case token | application/runtime metadata | not consumed by the current resolver | no effect | n/a |

> The current engine's names differ from generic examples: the role field is **`user_role`**
> (not `actor_role`), effective time is **`date_year`** (a year int, not a timestamp), and
> there is **no** dedicated `customer`, `system`, or `emergency_state` field — emergency is
> expressed through `environment` and through the authority's own `is_emergency_override`
> flag on the evidence side.

## Field-level situation provenance — current reality (honest)

**The current prototype accepts normalized situation values but does not yet preserve
field-level provenance inside the `Situation` object.** `Situation` fields are bare values;
they carry no per-field source, confidence, timestamp, or normalization method.

Provenance preservation in TAP-E4 applies to **upstream evidence and governance decisions**
(`GovProvenance` traces each selected authority → relationship assertion → evidence unit →
source), **not** to the situation input. Do not describe the situation input itself as
provenance-preserving.

Intended future model (conceptual only — **not implemented**; do not assume it exists):

```
SituationFact
    field_name
    value
    source_type          # INTENT_RECORD | APPLICATION_METADATA | RUNTIME_METADATA
                         #   | CALLER_ASSERTION | EVALUATION_FIXTURE
    source_reference
    confidence
    observed_at
    normalization_method
```

Adding field-level situation provenance is a **documented limitation and future schema
extension**. Any such change requires a schema-version increment, a migration note,
downstream compatibility analysis, and architectural justification.

## Missing situation facts

**Missing facts must never be replaced with invented values** — and the current engine does
not invent them. A missing field lowers the relevant confidence axis rather than
fabricating a value:

- absent `jurisdiction` → `jurisdiction_confidence` = 0.4; broadly-scoped authorities still
  apply; specific ones are retained at low confidence, never rejected on a fabricated match.
- absent `user_role` → `scope_confidence` = 0.4 on role-scoped candidates.
- absent `date_year` → temporal status defaults to `EFFECTIVE` at 0.4–0.5 confidence.

**Documented limitation.** With permissive matching, a *totally* unspecified situation can
still resolve to a scope-specific authority reported as `GOVERNING` at a lowered confidence
band, and the engine emits **no dedicated per-missing-field gap** (e.g. no
`ACTOR_ROLE_UNRESOLVED`). The engine's implemented gap vocabulary is `NO_GOVERNING_POLICY`,
`CONFLICTING_AUTHORITIES`, and `INSUFFICIENT_UPSTREAM_RELATIONSHIPS`; the schema also defines
`UNRESOLVED_SCOPE` / `AMBIGUOUS_JURISDICTION` / `MISSING_TEMPORAL_BASIS` / `MISSING_VERSION`
/ `UNRESOLVED_EXCEPTION` / `EXPIRED_AUTHORITY` which are **not currently emitted**. Forcing an
unresolved state on absent *mandatory* scope facts would require changing the frozen
resolver (`scope.py` / `applicability.py`) and therefore the E4 `frozen_components_hash`; it
is deferred to a future, version-incremented engine revision and recorded here rather than
silently patched.

## Contradictory situation facts

**Contradictory material facts must produce an unresolved state, conflict, or explicit gap —
never an arbitrary-ordering resolution.** The current `Situation` schema holds a **single
normalized value per field**, so it *cannot represent* contradictory facts
(`user_role = employee` **and** `user_role = contractor`; `jurisdiction = germany` **and**
`united_states`; `emergency_state active` **and** `inactive`). Therefore:

> **Contradiction detection must occur before `GovernanceSituation` construction in the
> current prototype.** The caller must resolve or surface the contradiction; TAP-E4 does not
> claim contradictory-fact detection it cannot represent.

## Relationship to upstream records

TAP-E4 consumes four inputs, each with a distinct role:

- `IntentRecord` — what the user is asking and relevant intent-level entities/constraints.
- `RetrievalRecord` — the evidence units available.
- `RelationshipRecord` — the relationships expressed by that evidence.
- `GovernanceSituation` — the operational facts against which applicability is resolved.

`GovernanceSituation` **does not replace** the upstream records. TAP-E4 **must not** derive
new evidence relationships or repair upstream gaps; upstream gaps are preserved into the
`GovernanceRecord`.

## Relationship to ActionGate

```
Governance Resolution:  Which documented authority governs this information case?
ActionGate:             May this exact proposed action execute?
```

Governance Resolution may determine that a policy *states* an action is permitted or
prohibited; it **does not issue execution authorization**. E4 and ActionGate are not merged.

## Supported claim (narrow)

Verdict **`PASS_WITH_LIMITED_CLAIM`** (unchanged; no numeric result is modified by this
boundary work).

> TAP-E4 demonstrates a deterministic, provenance-preserving Governance Resolution
> architecture for applying encoded authority, applicability, jurisdiction, scope, temporal,
> version, exception, precedence, conflict, and gap mechanisms **when supplied with
> normalized synthetic governance-situation facts**.

> The study does **not** validate operational extraction of governance facts, production
> legal reasoning, arbitrary enterprise-policy understanding, real-world authority
> correctness, or external generalization.

Provenance preservation refers to **upstream evidence and governance decisions**; **field-
level situation provenance is not implemented** and is a documented limitation.

## Next layer

**TAP-E5 — Evidence Assembly**, producing an `EvidencePacket`.
