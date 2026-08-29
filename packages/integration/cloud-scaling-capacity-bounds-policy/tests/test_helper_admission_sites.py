"""One test per helper-admission call site, each isolating that site alone.

The guard-coverage ADR §4.2 (D-GC-4) ratified that an unconditional statement-level call
to a raising helper is a decision point **distinct from the helper's own `if`**: covering
the helper proves the check works, not that it is applied here, and the operator that
neutralises it is call deletion, which no `if False:` can reach.

The package's first scored sweep measured that claim. All 23 `if` guards died; ten of the
fourteen call sites survived — the helper was covered everywhere, and ten of its
applications were not. The owner ruled those ten closed by tests rather than exclusions:
removing any of them admits an unchecked field, which is neither a diagnostic-only guard
nor an equivalent mutant.

Each test below is built to the same shape, so a reader can check the isolation rather
than take it on trust:

1. **a control** — the identical construction with only the named field corrected, which
   must succeed. That is the precondition: if every other field is admissible, the refusal
   below cannot be attributed to any other call site;
2. **a malformedness assertion** on the input itself, so a fixture that drifted into being
   valid fails here rather than passing for the wrong reason;
3. **the typed refusal**, asserted as the pair — class *and*
   `CapacityBoundsRejectionReason` — never the message;
4. **a docstring naming what the mutant does** when this one call is deleted. Measured:
   **eight sites admit** — six construct the artifact with the unchecked field in it, and
   the two `bound_for` sites answer the malformed query, one with `None` and one with the
   action type's default bound. The remaining **two**, `scope` and `lifecycle_state`, fall
   through to their membership guards and still refuse, but under a *different*
   `CapacityBoundsRejectionReason`. Those two are why the assertion is on the pair rather
   than the class: measured, removing the reason half from `_assert_refused_because` lets
   their mutants survive, while the other eight still die on the class alone.

Nothing here asserts a message, and nothing depends on a second call to the same helper:
in every case the site under test is the first refusal the input can reach.
"""

from __future__ import annotations

import pytest
from _bounds_fixtures import TENANT
from ugence_cloud_scaling_capacity_bounds_policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    CapacityBound,
    CapacityBoundsFieldError,
    CapacityBoundsPolicy,
    CapacityBoundsPolicyMetadata,
    CapacityBoundsRejectionReason as Reason,
    LIFECYCLE_APPROVED_ACTIVE,
    POLICY_SCOPE_TENANT,
    rejection_reason_of,
)

ACTION = "cloud_scaling.scale_out"


def _bound_fields(**overrides) -> dict:
    fields = dict(
        action_type=ACTION,
        max_permitted_magnitude=100,
        max_permitted_delta=25,
        resource_class="",
    )
    fields.update(overrides)
    return fields


def _metadata_fields(**overrides) -> dict:
    fields = dict(
        policy_id="cloud-scaling-capacity-bounds",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
        supersedes_ref="",
    )
    fields.update(overrides)
    return fields


def _refused(build) -> BaseException:
    """The refusal ``build`` raises.

    Deliberately catches the family root's ancestor rather than the leaf class: a test
    that caught only ``CapacityBoundsFieldError`` would report a *pass* as an error rather
    than a failure if the mutation changed the class, and the assertions below are what
    must decide, not the ``raises`` line.
    """

    with pytest.raises(Exception) as caught:  # noqa: PT011 - the pair is asserted below
        build()
    return caught.value


def _assert_refused_because(error: BaseException, reason: Reason) -> None:
    """The typed refusal, asserted as the pair §9.1 defines and nothing else."""

    assert isinstance(error, CapacityBoundsFieldError)
    assert rejection_reason_of(error) is reason


# ---------------------------------------------------------------------------------
# CapacityBound.__post_init__
# ---------------------------------------------------------------------------------


def test_a_non_string_resource_class_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.resource_class, …, allow_empty=True)`.

    Deleted, this call **admits the bound**: `resource_class` is read only by `selector`,
    so nothing downstream ever looks at it again and a bound whose narrowing is an integer
    is constructed, digested and issuable.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    # Control: the same bound with only this field corrected is admissible, so no other
    # call site in ``__post_init__`` can be the one that refuses below.
    assert CapacityBound(**_bound_fields(resource_class="gpu")).resource_class == "gpu"

    error = _refused(lambda: CapacityBound(**_bound_fields(resource_class=malformed)))
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_boolean_delta_ceiling_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_bound_magnitude(self.max_permitted_delta, …)`.

    Deleted, this call **admits the bound**: `True > 100` is False, so the ordering guard
    below lets it through and the artifact carries `max_permitted_delta is True`. That is
    precisely the `bool`-as-`1` coercion the module refuses to perform — and the magnitude
    call one line above cannot catch it, because it reads a different field.
    """

    malformed = True
    assert isinstance(malformed, bool)
    assert CapacityBound(**_bound_fields(max_permitted_delta=1)).max_permitted_delta == 1

    error = _refused(
        lambda: CapacityBound(
            **_bound_fields(max_permitted_magnitude=100, max_permitted_delta=malformed)
        )
    )
    _assert_refused_because(error, Reason.MAGNITUDE_NOT_AN_INT)


# ---------------------------------------------------------------------------------
# CapacityBoundsPolicyMetadata.__post_init__
# ---------------------------------------------------------------------------------


def test_a_non_string_policy_id_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.policy_id, …)`.

    Deleted, this call **admits the envelope**: `policy_id` is never read again in
    `__post_init__`, so an integer identity reaches the coordinate the authority registers.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert CapacityBoundsPolicyMetadata(**_metadata_fields(policy_id="p")).policy_id == "p"

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(**_metadata_fields(policy_id=malformed))
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_non_string_version_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.version, …)`.

    Deleted, this call **admits the envelope**: `version` is a coordinate component and is
    never re-read here, so an integer version reaches the registry.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert CapacityBoundsPolicyMetadata(**_metadata_fields(version="2.0.0")).version == "2.0.0"

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(**_metadata_fields(version=malformed))
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_non_string_scope_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.scope, …)`.

    Deleted, this call does **not** admit: the membership guard two lines below refuses an
    integer scope under `SCOPE_UNSUPPORTED`. So the class alone cannot see this site — it
    is the same `CapacityBoundsFieldError` either way — and only the reason distinguishes
    "this is not a scope token" from "this is a scope token I do not support". That is the
    §6 within-class criterion, and it is why the assertion is on the pair.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert (
        CapacityBoundsPolicyMetadata(**_metadata_fields(scope=POLICY_SCOPE_TENANT)).scope
        == POLICY_SCOPE_TENANT
    )

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(**_metadata_fields(scope=malformed))
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_non_string_lifecycle_state_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.lifecycle_state, …)`.

    The same shape as `scope`: deleted, the membership guard below refuses under
    `LIFECYCLE_STATE_UNSUPPORTED`, so the reason is the only thing that can tell the two
    apart.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert CapacityBoundsPolicyMetadata(
        **_metadata_fields(lifecycle_state=LIFECYCLE_APPROVED_ACTIVE)
    ).lifecycle_state == LIFECYCLE_APPROVED_ACTIVE

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(
            **_metadata_fields(lifecycle_state=malformed)
        )
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_bytes_tenant_id_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.tenant_id, …, allow_empty=True)`.

    `bytes` rather than `int` on purpose. The tenant guard further down calls
    `.strip()`, which `bytes` has and `int` has not: an integer would make the mutant die
    of an `AttributeError`, crediting this site with a kill it never earned. `b"…".strip()`
    is truthy, so deleting this call **admits the envelope** with a `bytes` tenant — the
    component the authority resolves a policy version by.
    """

    malformed = TENANT.encode()
    assert not isinstance(malformed, str) and hasattr(malformed, "strip")
    assert (
        CapacityBoundsPolicyMetadata(**_metadata_fields(tenant_id=TENANT)).tenant_id
        == TENANT
    )

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(
            **_metadata_fields(scope=POLICY_SCOPE_TENANT, tenant_id=malformed)
        )
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_non_string_supersedes_ref_is_refused_at_its_own_call_site():
    """`policy.py` — `_require_token(self.supersedes_ref, …, allow_empty=True)`.

    Deleted, this call **admits the envelope**: `supersedes_ref` is read by nothing else
    here, so a superseding reference that is not a reference reaches the descriptor.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert (
        CapacityBoundsPolicyMetadata(**_metadata_fields(supersedes_ref="prior")).supersedes_ref
        == "prior"
    )

    error = _refused(
        lambda: CapacityBoundsPolicyMetadata(**_metadata_fields(supersedes_ref=malformed))
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


# ---------------------------------------------------------------------------------
# CapacityBoundsPolicy.bound_for
# ---------------------------------------------------------------------------------


@pytest.fixture()
def policy() -> CapacityBoundsPolicy:
    """A policy carrying a default bound for one action type, and nothing else.

    The default matters: it is what makes the `resource_class` site's deletion *answer*
    rather than merely return `None`.
    """

    return CapacityBoundsPolicy(
        metadata=CapacityBoundsPolicyMetadata(**_metadata_fields()),
        bounds=(CapacityBound(**_bound_fields()),),
    )


def test_a_non_string_action_type_is_refused_at_its_own_call_site(policy):
    """`policy.py` — `_require_token(action_type, 'bound_for(action_type)')`.

    Deleted, the lookup misses and `bound_for` **returns `None`** — which this family
    documents as "this policy states no bound for that selector" and explicitly *not* as
    "unbounded". A malformed question would be answered as a well-formed one with no
    applicable bound.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    assert policy.bound_for(action_type=ACTION) is not None

    error = _refused(lambda: policy.bound_for(action_type=malformed))
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)


def test_a_non_string_resource_class_query_is_refused_at_its_own_call_site(policy):
    """`policy.py` — `_require_token(resource_class, …, allow_empty=True)`.

    The worse of the two: deleted, the exact-selector lookup misses and the call **falls
    back to the action type's default bound**, so a caller asking about a resource class
    that is not a resource class is handed a real ceiling to act on. `action_type` is valid
    here, so the call site one line above cannot be the one that refuses.
    """

    malformed = 7
    assert not isinstance(malformed, str)
    default = policy.bound_for(action_type=ACTION, resource_class="")
    assert default is not None, "the fallback the mutant would return must exist"

    error = _refused(
        lambda: policy.bound_for(action_type=ACTION, resource_class=malformed)
    )
    _assert_refused_because(error, Reason.FIELD_NOT_A_STRING)
