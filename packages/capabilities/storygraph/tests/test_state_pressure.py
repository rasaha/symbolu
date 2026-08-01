"""H4 — sustained state pressure is fail-visible, tenant-isolated, no silent loss."""

from __future__ import annotations

from ugence_storygraph import (
    BY_CASE, DIGITAL_ONTOLOGY, SequenceRiskAnalyzer, StateLimits, signals,
)


def _open(az, tenant, workflow, n):
    """Open an assembly by ingesting one credential-read event."""
    return az.observe({"tenant_id": tenant, "workflow_id": workflow,
                       "actor": f"a-{workflow}", "correlation_id": workflow,
                       "sequence_id": f"{workflow}:1", "event_id": f"{tenant}-{n}",
                       "operation": "SECRET_READ",
                       "credential_scope": {"principal": f"a-{workflow}"},
                       "arguments": {}})


def test_reject_mode_is_fail_visible_and_tenant_isolated():
    limits = StateLimits(max_assemblies_per_tenant=2)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), limits=limits)
    _open(az, "a", "wfA1", 1)
    _open(az, "a", "wfA2", 2)
    out = _open(az, "a", "wfA3", 3)               # 3rd assembly for tenant A -> over cap
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    # tenant B is unaffected by tenant A saturating its own quota
    outB = _open(az, "b", "wfB1", 1)
    assert all(f.signal != signals.UNAVAILABLE for f in outB)
    assert az.ledger.assembly_count("a") == 2 and az.ledger.assembly_count("b") == 1
    # no silent loss: the rejected event still has a durable INGEST record
    assert any(r.kind == "INGEST" and r.event_id == "a-3" for r in az.audit.all())


def test_evict_mode_audits_eviction_and_bounds_state():
    limits = StateLimits(max_assemblies_per_tenant=2, evict_on_pressure=True)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), limits=limits)
    _open(az, "a", "wfA1", 1)
    _open(az, "a", "wfA2", 2)
    _open(az, "a", "wfA3", 3)                     # evicts lowest-priority, admits new
    assert az.ledger.assembly_count("a") == 2     # bounded
    assert az.report.evictions >= 1
    assert any(r.kind == "EVICTION" for r in az.audit.all())
    # evicted assembly remains reconstructable via durable replay (INGEST retained)
    assert sum(1 for r in az.audit.all() if r.kind == "INGEST") == 3


def test_noisy_tenant_cannot_exhaust_another_tenant():
    limits = StateLimits(max_assemblies_per_tenant=3)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), limits=limits)
    for i in range(10):                            # tenant NOISY floods well past its cap
        _open(az, "noisy", f"w{i}", i)
    assert az.ledger.assembly_count("noisy") == 3  # capped
    # a quiet tenant still gets its full allocation
    for i in range(3):
        out = _open(az, "quiet", f"q{i}", i)
        assert all(f.signal != signals.UNAVAILABLE for f in out)
    assert az.ledger.assembly_count("quiet") == 3


def test_candidate_linkage_and_instance_caps_still_fail_visible():
    az = SequenceRiskAnalyzer(
        DIGITAL_ONTOLOGY, specs=(BY_CASE,),
        limits=StateLimits(max_instances_per_assembly=1))
    out = []
    out += az.observe({"tenant_id": "t", "workflow_id": "w", "actor": "a",
                       "correlation_id": "c", "sequence_id": "c:1", "event_id": "1",
                       "operation": "SECRET_READ", "credential_scope": {"principal": "a"},
                       "arguments": {"enumerate": True}})   # 2 instances > cap
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    assert any(r.kind == "EVICTION" for r in az.audit.all())
