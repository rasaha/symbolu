"""N1 — tenant-safe derived attempt IDs + end-to-end two-tenant retention.

Demonstrates the ORIGINAL collision (identical tenant-local ids across two tenants) and
proves the corrected implementation derives different ids AND retains both records in a
shared sink. Retry linkage stays tenant-bound. Barriers, no sleep.
"""

from __future__ import annotations

import threading

import pytest

from ugence_agent_runtime.observability.attempts import ProviderAttempt, ProviderAttemptStatus

from ugence_context_minimization.api import (
    InMemoryTokenAccountingSink,
    RequestAttribution,
    prepare_api_call_measurement,
)

from ugence_cm_token_accounting_runtime import derive_attempt_id, translate_attempt

from support_itg import sample_minimization_result


def _att(instance_id="wf-1", task_id="t1", n=1):
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
# The original collision, now resolved.
# --------------------------------------------------------------------------- #
def test_identical_tenant_local_ids_across_tenants_derive_different_ids():
    att = _att()  # SAME logical_request_id/instance/task/attempt across both tenants
    idA = derive_attempt_id(att, logical_request_id="req-1", tenant_id="tenantA")
    idB = derive_attempt_id(att, logical_request_id="req-1", tenant_id="tenantB")
    assert idA != idB


def test_single_tenant_namespace_distinct_from_named_tenant():
    att = _att()
    id_none = derive_attempt_id(att, logical_request_id="req-1")  # tenant_id=None → "s"
    id_named = derive_attempt_id(att, logical_request_id="req-1", tenant_id="tenantA")
    assert id_none != id_named


@pytest.mark.parametrize("bad", ["", "   ", "\t"])
def test_empty_or_whitespace_tenant_rejected_in_derivation(bad):
    with pytest.raises(Exception):
        derive_attempt_id(_att(), logical_request_id="req-1", tenant_id=bad)


def test_stable_replay_within_same_tenant():
    att = _att(n=2)
    a = derive_attempt_id(att, logical_request_id="req-1", tenant_id="tenantA")
    b = derive_attempt_id(att, logical_request_id="req-1", tenant_id="tenantA")
    assert a == b


def test_end_to_end_two_tenants_both_records_retained_in_shared_sink():
    """The concrete N1 fix: two tenants, identical tenant-local ids, one shared sink."""
    sink = InMemoryTokenAccountingSink()
    att = _att()
    rA = translate_attempt(_prep("tenantA"), att, sink=sink)
    rB = translate_attempt(_prep("tenantB"), att, sink=sink)
    assert rA.attempt_id != rB.attempt_id            # tenant-bound derivation
    assert rA.record_fingerprint != rB.record_fingerprint
    assert len(sink.records) == 2                    # BOTH retained (was 1 before N1)
    assert {r.attribution.tenant_id for r in sink.records} == {"tenantA", "tenantB"}


def test_end_to_end_single_tenant_replay_still_idempotent():
    sink = InMemoryTokenAccountingSink()
    att = _att()
    p = _prep("tenantA")
    translate_attempt(p, att, sink=sink)
    translate_attempt(p, att, sink=sink)  # identical replay, same tenant
    assert len(sink.records) == 1


# --------------------------------------------------------------------------- #
# Retry linkage is tenant-bound.
# --------------------------------------------------------------------------- #
def test_derived_retry_linkage_uses_same_tenant_namespace():
    p = _prep("tenantA")
    att3 = _att(n=3)
    att2 = _att(n=2)
    rec = translate_attempt(p, att3, sink=None)
    # retry_of is derived with the SAME tenant → equals tenantA's attempt-2 id, NOT the
    # single-tenant or another tenant's id.
    assert rec.retry_of_attempt_id == derive_attempt_id(att2, logical_request_id="req-1", tenant_id="tenantA")
    assert rec.retry_of_attempt_id != derive_attempt_id(att2, logical_request_id="req-1", tenant_id="tenantB")
    assert rec.retry_of_attempt_id != derive_attempt_id(att2, logical_request_id="req-1")  # not single-tenant


def test_two_tenants_retry_chains_do_not_cross():
    a2 = derive_attempt_id(_att(n=2), logical_request_id="req-1", tenant_id="A")
    b3_retry_of = translate_attempt(_prep("B"), _att(n=3)).retry_of_attempt_id
    assert b3_retry_of != a2  # tenant B's retry never references tenant A's attempt


# --------------------------------------------------------------------------- #
# Concurrency: same id across tenants, one shared sink.
# --------------------------------------------------------------------------- #
def test_concurrent_two_tenant_translation_retains_both():
    sink = InMemoryTokenAccountingSink()
    preps = [_prep(f"tenant-{i}") for i in range(16)]
    att = _att()
    b = threading.Barrier(len(preps)); errs = []
    def work(p):
        b.wait()
        try: translate_attempt(p, att, sink=sink)
        except Exception as e: errs.append(e)
    ts = [threading.Thread(target=work, args=(p,)) for p in preps]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert errs == []
    assert len(sink.records) == 16
    assert len({r.attempt_id for r in sink.records}) == 16
