# `ugence-cloud-scaling-capacity-bounds-policy`

The Cloud Scaling **capacity-bounds** policy family, and its adapter for the
shared Ugence Policy Authority.

## Why this exists

R-8 asked for the verified policy-authenticity artifact to carry a bound. The
audit found the prerequisite underneath it: **no shipped policy family states a
capacity bound at all.** The Phase 5A authorization candidate already carries
`max_permitted_magnitude` and `max_permitted_delta` and already enforces
`requested <= max_permitted` — but those maxima are *self-asserted by the
caller*, bound to no signed policy. There was nothing authentic to reconcile them
against, so R-8 could not be closed by comparing anything.

This distribution is the missing half: an issuable, signable, digest-bound
statement of what capacity change is permitted.

## What it is

A `CapacityBoundsPolicy` carries one or more `CapacityBound`s, each stating
`max_permitted_magnitude` and `max_permitted_delta` for one `action_type`,
optionally narrowed by `resource_class`. It is issued, signed, registered,
resolved and revoked entirely by the shared Policy Authority — this package adds
an artifact and a `PolicyFamilyAdapter`, and nothing else.

It is the authority's **second** policy family, and the first registered from
*outside* the authority's own distribution. The authority ratified that a second
family requires no core change; `tests/test_authority_registration.py` exercises
that claim across a real package boundary, driving genuine issuance, real Ed25519
signing, the real registry and real resolution.

## Refusal is a pair

Every refusal names both an exception class and a `CapacityBoundsRejectionReason`.
The class alone was not enough: fifteen guards raise `CapacityBoundsFieldError`, so
`pytest.raises(CapacityBoundsFieldError)` is satisfied by any of them firing and
shows that the program refused, not that *this* guard decided the refusal. The
guard-coverage ADR §3 ruled that degenerate pair a defect in the package and
required the reason vocabulary before the family's first scored guard sweep.

```python
from ugence_cloud_scaling_capacity_bounds_policy import (
    CapacityBoundsRejectionReason,
    rejection_reason_of,
)

try:
    CapacityBound(action_type="scale_out", max_permitted_magnitude=-1, max_permitted_delta=0)
except Exception as error:
    assert rejection_reason_of(error) is CapacityBoundsRejectionReason.MAGNITUDE_NEGATIVE
```

The adapter's four refusals keep the shared authority's own exception classes —
those are the authority's contract with an adapter — and carry the reason as an
attribute. `rejection_reason_of` reads either half, so a caller never has to know
which side of the boundary refused it.

## What it deliberately does not do

| Not done | Why |
|---|---|
| Compare a bound against a candidate's maxima | A later reconciliation subphase with its own ruling. This package holds no candidate type. |
| Authorize, evaluate, or read runtime state | It is a declarative artifact, not a decision. |
| Sign anything | Issuance and signing belong to the authority. An import-boundary test refuses signing calls and key material in shipped source. |
| Reconcile `action_type` against the D-4 canonical set | Importing Phase 5A's contracts to borrow that set would place the Risk Authority behind a leaf policy family. Recorded as deferred, not silently assumed. |

## Boundary

Exactly one first-party dependency — `ugence-policy-authority` — reached only
through its public `api` module, and no third-party runtime dependency at all.
`tests/test_import_boundary.py` measures every prohibition above against the
shipped source and the packaging metadata, including that the authority's
`core.*` internals are never reached.

## Wiring

The composition root registers the adapter; nothing here wires itself.

```python
from ugence_policy_authority.api import AdapterRegistry
from ugence_cloud_scaling_capacity_bounds_policy import CapacityBoundsPolicyFamilyAdapter

adapters = AdapterRegistry([CapacityBoundsPolicyFamilyAdapter()])
```

No composition root calls this today. The family is issuable and resolvable; it
is not yet wired into any runtime path.

## Digest discipline

The canonical projection removes **exactly one declared path**,
`metadata.content_digest`, and removes it rather than blanking it — so no
sentinel participates in the body digest and no fixed-point iteration is
involved. Removal is by path, not by name. The artifact has no signature field,
so the projection is structurally incapable of depending on a signature. This
mirrors the UVI adapter, because the discipline is the authority's rather than
any one family's.
