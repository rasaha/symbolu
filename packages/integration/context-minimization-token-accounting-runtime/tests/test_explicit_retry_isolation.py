"""N3 — explicit retry linkage is tenant-scoped and fails closed on any cross-tenant ref.

Reproduces the original defect (tenant-A child + tenant-B retry reference) and proves the
corrected implementation rejects it before any accounting evidence is stored, never invokes
a provider, and cannot be bypassed concurrently. Barriers, no sleep.
"""

from __future__ import annotations

import threading

import pytest

from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus

from ugence_context_minimization.api import (
    InMemoryTokenAccountingSink,
    RequestAttribution,
    canonical_tenant_namespace,
    prepare_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError

from ugence_cm_token_accounting_runtime import (
    ExplicitAttemptReference,
    derive_attempt_id,
    translate_attempt,
)

from support_itg import sample_minimization_result


def _att(n=1, instance_id="wf-1", task_id="t1"):
    return ProviderAttempt(
        provider_id="prov", operation="op", attempt_number=n,
        status=ProviderAttemptStatus.SUCCEEDED, ok=True, provider_invoked=True,
        instance_id=instance_id, task_id=task_id, correlation_id="c",
    )


def _prep(tenant, lr="req-1"):
    return prepare_api_call_measurement(
        minimization_result=sample_minimization_result(), logical_request_id=lr,
        provider_id="prov", attribution=RequestAttribution(tenant_id=tenant),
    )


# --------------------------------------------------------------------------- #
# Original defect reproduction → now rejected.
# --------------------------------------------------------------------------- #
def test_original_defect_tenant_A_child_tenant_B_reference_is_rejected():
    sink = InMemoryTokenAccountingSink()
    # A tenant-B parent id, referenced by a tenant-A child (the exact N3 construction).
    tenant_b_parent = ExplicitAttemptReference(attempt_id="P", tenant_id="tenantB")
    with pytest.raises(InvalidRequestError):
        translate_attempt(_prep("tenantA"), _att(n=2), attempt_id="A-att-2",
                          retry_of=tenant_b_parent, sink=sink)
    # Fail closed BEFORE any evidence is stored.
    assert sink.records == ()


def test_same_tenant_explicit_retry_accepted():
    sink = InMemoryTokenAccountingSink()
    parent = ExplicitAttemptReference(attempt_id="P", tenant_id="tenantA")
    rec = translate_attempt(_prep("tenantA"), _att(n=2), attempt_id="A-att-2",
                            retry_of=parent, sink=sink)
    assert rec.retry_of_attempt_id == "P"
    assert len(sink.records) == 1


def test_named_tenant_cannot_reference_missing_tenant_attempt():
    with pytest.raises(InvalidRequestError):
        translate_attempt(_prep("tenantA"), _att(n=2), attempt_id="c",
                          retry_of=ExplicitAttemptReference(attempt_id="P"))  # tenant None


def test_missing_tenant_cannot_reference_named_tenant_attempt():
    with pytest.raises(InvalidRequestError):
        translate_attempt(_prep(None), _att(n=2), attempt_id="c",
                          retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="tenantA"))


def test_two_tenants_same_opaque_parent_id_unambiguous():
    sink = InMemoryTokenAccountingSink()
    rA = translate_attempt(_prep("A"), _att(n=2), attempt_id="childA",
                           retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="A"), sink=sink)
    rB = translate_attempt(_prep("B"), _att(n=2), attempt_id="childB",
                           retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="B"), sink=sink)
    # Both children reference opaque parent "P", but resolve within their own tenant.
    assert rA.retry_of_attempt_id == "P" and rB.retry_of_attempt_id == "P"
    assert rA.attribution.tenant_id == "A" and rB.attribution.tenant_id == "B"
    # The parent reference of each child is its own tenant namespace.
    assert canonical_tenant_namespace(rA.attribution.tenant_id) != canonical_tenant_namespace(rB.attribution.tenant_id)
    assert len(sink.records) == 2


# --------------------------------------------------------------------------- #
# Mode discipline + raw-string removal.
# --------------------------------------------------------------------------- #
def test_raw_string_retry_of_no_longer_accepted():
    # The old opaque parameter name is gone; passing it is a TypeError (unknown kwarg).
    with pytest.raises(TypeError):
        translate_attempt(_prep("A"), _att(n=2), attempt_id="c", retry_of_attempt_id="P")


def test_explicit_retry_requires_reference_type():
    with pytest.raises(ValueError):
        translate_attempt(_prep("A"), _att(n=2), attempt_id="c", retry_of="P")  # raw str, not a reference


def test_deriving_with_explicit_retry_of_rejected():
    with pytest.raises(ValueError):
        translate_attempt(_prep("A"), _att(n=2),
                          retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="A"))


def test_non_retry_with_retry_of_rejected():
    with pytest.raises(ValueError):
        translate_attempt(_prep("A"), _att(n=1), attempt_id="c",
                          retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="A"))


def test_explicit_retry_without_reference_rejected():
    with pytest.raises(ValueError):
        translate_attempt(_prep("A"), _att(n=2), attempt_id="c")  # retry but no retry_of


# --------------------------------------------------------------------------- #
# Derived mode unchanged; both modes converge on a tenant-scoped reference.
# --------------------------------------------------------------------------- #
def test_derived_retry_still_tenant_bound():
    p = _prep("A")
    rec = translate_attempt(p, _att(n=3))
    assert rec.retry_of_attempt_id == derive_attempt_id(_att(n=2), logical_request_id="req-1", tenant_id="A")
    # differs from other tenant / single-tenant
    assert rec.retry_of_attempt_id != derive_attempt_id(_att(n=2), logical_request_id="req-1", tenant_id="B")
    assert rec.retry_of_attempt_id != derive_attempt_id(_att(n=2), logical_request_id="req-1")


# --------------------------------------------------------------------------- #
# Fingerprints + serialization.
# --------------------------------------------------------------------------- #
def test_serialization_preserves_retry_namespace():
    rec = translate_attempt(_prep("A"), _att(n=2), attempt_id="c",
                            retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="A"))
    d = rec.to_dict()
    # The parent's tenant namespace is unambiguously the record's own (enforced equal).
    assert d["retry_of_attempt_id"] == "P"
    assert d["attribution"]["tenant_id"] == "A"
    assert canonical_tenant_namespace(rec.attribution.tenant_id) == "t:A"


def test_fingerprint_reflects_retry_reference_tenant():
    # Same child attempt_id + same parent id, different tenant → different fingerprint.
    rA = translate_attempt(_prep("A"), _att(n=2), attempt_id="c",
                           retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="A"))
    rB = translate_attempt(_prep("B"), _att(n=2), attempt_id="c",
                           retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="B"))
    assert rA.record_fingerprint != rB.record_fingerprint
    # and a record WITH a parent differs from one withOUT
    r0 = translate_attempt(_prep("A"), _att(n=1), attempt_id="c0")
    assert r0.record_fingerprint != rA.record_fingerprint


# --------------------------------------------------------------------------- #
# Concurrency cannot bypass validation.
# --------------------------------------------------------------------------- #
def test_concurrent_cross_tenant_references_all_rejected():
    sink = InMemoryTokenAccountingSink()
    errors = []
    results = []
    barrier = threading.Barrier(20)

    def worker(i):
        barrier.wait()
        try:
            # every worker: tenant-A child referencing a tenant-B parent → must reject
            translate_attempt(_prep("A"), _att(n=2), attempt_id=f"c{i}",
                              retry_of=ExplicitAttemptReference(attempt_id="P", tenant_id="B"),
                              sink=sink)
            results.append(i)
        except InvalidRequestError:
            errors.append(i)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(errors) == 20 and results == []  # all rejected, none bypassed
    assert sink.records == ()  # no evidence stored
