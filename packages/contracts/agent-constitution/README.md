# ugence-agent-constitution

**Scope: AC-0.** Immutable, versioned, content-addressed artifacts for an agent's
constitutional text, plus the deterministic, fail-closed validation that decides
whether such an artifact is well-formed.

This package is a **leaf contract**. It depends on `pydantic` and the standard
library, and on **no other Ugence package**.

## What this is not

It is **not an authority**. It ratifies nothing, approves nothing, authorizes
nothing, clears nothing, resolves no capability, and binds nothing at runtime.
It records that an issuer *claims* to have ratified content, and it checks that
the record is internally coherent. Whether that issuer had standing is not a
question AC-0 answers.

AC-0 ships **no** compiler, **no** capability registry, **no** conformance
findings or verdicts, **no** signing or key material, **no** UI, **no** LLM
assistance, **no** runtime binding, and **no** authority decision. Those are out
of scope by ratified decision, not merely unimplemented; `version_info()` reports
each as `False` and `tests/packaging/test_public_api.py` asserts the surface
carries no such name.

## The artifacts

| Artifact | What it is | Ratified? |
|---|---|---|
| `AgentRoleManifest` | The **draft**. Where a role is worked out. | Never |
| `AgentConstitution` | The **ratified** text: immutable, versioned, content-addressed. | By construction |
| `CapabilityRequirement` | One obligation, optionally pinning a registry entry. | — |
| `CapabilityRegistryEntryRef` | An opaque `namespace/entry@version` + digest token. Resolved by nobody here. | — |
| `DeveloperImplementationContract` | What a developer is told to build, pinned to one constitution version. | — |
| `ConformanceSubject` | What *would* be assessed. AC-0 assesses nothing. | — |

Every artifact is a frozen pydantic model with `extra="forbid"`. Frozen is not
decoration: an artifact that can be mutated after its digest is computed is an
artifact whose digest means nothing. Forbidding unknown fields is the same rule
from the other side — a field this build would silently drop is content the digest
would fail to attest to.

### A draft is not a constitution

The two are separate **types**, not one type with a `ratified` flag, because a
flag is a field somebody sets and a type is a thing somebody has to construct.
`AgentRoleManifest.carries_authority` and `.is_ratified` are permanently `False`;
a manifest payload handed to `validate_constitution()` is refused by name
(`AC_DRAFT_IS_NOT_A_CONSTITUTION`); and `is_ratified_constitution()` rejects both
a draft and any duck-typed impostor.

"Mutable draft" and "frozen model" are reconciled by copy-on-write:
`manifest.revise(...)` returns a *new* draft with `draft_revision` advanced and
the stale digest cleared.

## Canonical serialization and fingerprints

```python
from ugence_agent_constitution import dumps, fingerprint, compute_content_digest
```

Canonical JSON is sorted keys, compact separators, UTF-8 preserved, enums by
value, sets sorted.

**This package owns canonicalization.** It is the canonical owner of the
deterministic representation and fingerprinting rules for Agent Constitution
contracts, and `to_canonical_obj` / `dumps` / `dumps_pretty` / `loads` are that
published contract. A compiler or any other consumer must use it rather than
maintain an independently authoritative implementation.

`ugence_policy_workflow_compiler` predates this package and still carries its own
copy of the same semantics. That copy is a legacy consumer implementation awaiting
migration, not a second source of truth.
`tests/serialization/test_canonical_json_compatibility_ratchet.py` loads it off disk
and asserts it still matches **this package's** output — a one-directional migration
ratchet, so the copy cannot drift before it is retired. If the two disagree, this
package is correct and the copy is wrong.

A fingerprint is `sha256:<64 hex>` over the canonical encoding. A digest-bearing
artifact excludes its own digest field from its own scope, so stamping is
idempotent; everything nested is in scope, so any material edit moves the digest.
A fingerprint is **not** a signature — it attests to content identity only, never
to who produced it.

## Validation: three outcomes, fail-closed

```python
report = validate_artifact(payload, ArtifactKind.AGENT_CONSTITUTION)
if report.is_usable:      # VALID and only VALID
    ...
```

* `VALID` — well-formed and internally consistent under every rule this build
  implements. Says nothing about whether the content is *good*.
* `INVALID` — a rule is definitely broken. A better-informed build would agree.
* `INDETERMINATE` — this build cannot decide: an unrecognized schema version, an
  ambiguous mandatory field, a mandatory requirement that pins nothing resolvable.

`INDETERMINATE` is **not** a softer `VALID`. It is a refusal to answer, and a
caller that treats it as permission has defeated the point. `report.is_usable` is
true for `VALID` alone. Aggregation is `INVALID` > `INDETERMINATE` > `VALID`.

The split between the two non-`VALID` outcomes is the design: a **contradiction**
is `INVALID`; an **ambiguity** is `INDETERMINATE`, because picking an
interpretation would be this package silently making a decision that belongs to a
person.

Validation never raises for bad data, never reads a clock, environment,
filesystem or random source, and returns findings in a fully deterministic order.

## Version compatibility

Two independent questions, deliberately not merged:

* **Can this build read that shape?** `schema_compatibility()` — an unrecognized
  schema version is `UNRECOGNIZED` and validates as `INDETERMINATE`, not as a
  hopeful `VALID`.
* **Is this a legitimate successor?** `succession_compatibility()` — a successor
  must keep its lineage identity, bump `artifact_version` strictly upward, and
  actually differ in content. Reusing a predecessor's version or digest is
  `INVALID`.

Only release `MAJOR.MINOR.PATCH` versions are ordered. Pre-release and
build-metadata suffixes are refused rather than ordered, because their ordering is
subtle enough that a silent wrong answer is likelier than a right one — and this
comparison decides whether one governance artifact supersedes another.

## Self-ratification

An issuer may not be the author of the draft they ratify
(`AC_SELF_RATIFICATION`). This is a structural refusal, not an authority decision:
the package does not decide who *may* ratify, only that an artifact naming one
identity in both roles has recorded no independent act at all.

## Tests

```
pytest packages/contracts/agent-constitution/tests
```

Covers canonical-serialization stability, fingerprint stability and
change-on-material-edit, the required version bump, missing and ambiguous
mandatory fields, draft-is-not-a-constitution, self-ratification rejection,
property-based mutation of both manifests (hypothesis), an import-boundary gate,
and **negative controls**: for each invariant, the intact artifact must be usable
*and* the same artifact with that one invariant inverted must not be. A passing
invariant test proves nothing on its own — the control is what makes it
load-bearing.

## Maturity

Deterministic and offline. Not pilot-validated. Not production-certified. See
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION.md`.
