"""N1 — the reference sink partitions idempotency by (tenant_namespace, attempt_id).

Two tenants may store the same explicit attempt_id; same-tenant replay is idempotent;
same-tenant conflict is rejected; missing tenant is a distinct namespace; whitespace tenant
is rejected; concurrency is isolated per tenant. Deterministic barriers, no sleep.
"""

from __future__ import annotations

import threading

import pytest

from ugence_context_minimization.api import (
    ApiCallTokenRecord,
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    RequestAttribution,
    UsageAvailability,
    canonical_tenant_namespace,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError

from support_accounting import sample_minimization_result


def _prep(tenant=None, lr="lr"):
    return prepare_api_call_measurement(
        minimization_result=sample_minimization_result(),
        logical_request_id=lr,
        provider_id="prov",
        attribution=RequestAttribution(tenant_id=tenant),
    )


def _rec(prep, attempt_id, n=1, status=AttemptStatus.SUCCEEDED, usage=None, sink=None):
    return reconcile_api_call_measurement(
        prep, attempt_id=attempt_id, attempt_number=n, status=status,
        provider_usage=usage, sink=sink,
    )


# --------------------------------------------------------------------------- #
# Namespace canonicalization.
# --------------------------------------------------------------------------- #
def test_canonical_namespace_absent_is_domain_separated_not_empty():
    assert canonical_tenant_namespace(None) == "s"
    assert canonical_tenant_namespace("t") == "t:t"
    # a tenant literally named "s" cannot collide with the single-tenant namespace
    assert canonical_tenant_namespace("s") == "t:s" != canonical_tenant_namespace(None)


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_whitespace_tenant_rejected(bad):
    with pytest.raises(InvalidRequestError):
        RequestAttribution(tenant_id=bad)
    with pytest.raises(InvalidRequestError):
        canonical_tenant_namespace(bad)


# --------------------------------------------------------------------------- #
# Sink partitioning.
# --------------------------------------------------------------------------- #
def test_two_tenants_same_explicit_attempt_id_both_retained():
    sink = InMemoryTokenAccountingSink()
    pa = _prep(tenant="tenantA")
    pb = _prep(tenant="tenantB")
    _rec(pa, "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1), sink=sink)
    _rec(pb, "att-1", usage=ProviderTokenUsage(input_tokens=2, output_tokens=2), sink=sink)
    assert len(sink.records) == 2  # NOT deduplicated, NOT rejected
    assert {r.attribution.tenant_id for r in sink.records} == {"tenantA", "tenantB"}


def test_missing_tenant_is_distinct_from_named_tenant():
    sink = InMemoryTokenAccountingSink()
    _rec(_prep(tenant=None), "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1), sink=sink)
    _rec(_prep(tenant="tenantA"), "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1), sink=sink)
    assert len(sink.records) == 2  # single-tenant namespace ≠ named tenant


def test_same_tenant_identical_replay_idempotent():
    sink = InMemoryTokenAccountingSink()
    p = _prep(tenant="tenantA")
    for _ in range(3):
        _rec(p, "att-1", usage=ProviderTokenUsage(input_tokens=5, output_tokens=1), sink=sink)
    assert len(sink.records) == 1


def test_same_tenant_conflicting_rejected():
    sink = InMemoryTokenAccountingSink()
    p = _prep(tenant="tenantA")
    _rec(p, "att-1", usage=ProviderTokenUsage(input_tokens=5, output_tokens=1), sink=sink)
    with pytest.raises(InvalidRequestError):
        _rec(p, "att-1", status=AttemptStatus.FAILED, sink=sink)


def test_cross_tenant_not_silently_deduplicated_even_with_equal_content():
    """Records that would be byte-identical except for tenant must both survive."""
    sink = InMemoryTokenAccountingSink()
    # identical everything except tenant → different sink keys, both stored
    _rec(_prep(tenant="A"), "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1), sink=sink)
    _rec(_prep(tenant="B"), "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1), sink=sink)
    assert len(sink.records) == 2
    # tenant is bound into each record's fingerprint too (serialization consistency)
    fps = {r.record_fingerprint for r in sink.records}
    assert len(fps) == 2


# --------------------------------------------------------------------------- #
# Concurrency isolation (barrier-synchronized).
# --------------------------------------------------------------------------- #
def _barrier(fns):
    b = threading.Barrier(len(fns)); errs = []
    def wrap(f):
        def inner():
            b.wait()
            try: f()
            except Exception as e: errs.append(e)
        return inner
    ts = [threading.Thread(target=wrap(f)) for f in fns]
    [t.start() for t in ts]; [t.join() for t in ts]
    return errs


def test_concurrent_same_id_across_tenants_retains_one_per_tenant():
    sink = InMemoryTokenAccountingSink()
    tenants = [f"tenant-{i}" for i in range(20)]
    recs = [_rec(_prep(tenant=t), "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1))
            for t in tenants]
    errs = _barrier([lambda r=r: sink.record(r) for r in recs])
    assert errs == []
    assert len(sink.records) == 20  # one per tenant, same attempt_id
    assert len({r.attribution.tenant_id for r in sink.records}) == 20


def test_concurrent_conflicting_duplicates_isolated_within_tenant():
    sink = InMemoryTokenAccountingSink()
    pa = _prep(tenant="A")
    good = _rec(pa, "att-1", usage=ProviderTokenUsage(input_tokens=1, output_tokens=1))
    conflict = _rec(pa, "att-1", status=AttemptStatus.FAILED)
    # tenant B stores its own att-1 concurrently; must be unaffected by A's conflict.
    b_rec = _rec(_prep(tenant="B"), "att-1", usage=ProviderTokenUsage(input_tokens=9, output_tokens=9))
    errs = _barrier([lambda: sink.record(good)] * 4 + [lambda: sink.record(conflict)] * 4
                    + [lambda: sink.record(b_rec)])
    # A keeps exactly one record; the conflicting fingerprint is rejected; B is retained.
    a_recs = [r for r in sink.records if r.attribution.tenant_id == "A"]
    b_recs = [r for r in sink.records if r.attribution.tenant_id == "B"]
    assert len(a_recs) == 1 and len(b_recs) == 1
    assert any(isinstance(e, InvalidRequestError) for e in errs)
