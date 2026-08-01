"""Deterministic detection AND non-detection tests (§10).

Each scenario proves both that the analyzer fires when it should and that it does
NOT fire when it should not. Signals are advisory only; policy binding is tested
separately in ``test_policy.py``.
"""

from __future__ import annotations

import dataclasses

import pytest

from composite_threat_detector import (
    BY_ACTOR,
    BY_CASE,
    DIGITAL_ONTOLOGY,
    PHYSICAL_FIREARM_ONTOLOGY,
    SequenceRiskAnalyzer,
    StateLimits,
    signals,
)
from composite_threat_detector import recipes as R
from demos import scenarios


def dig(op, seq, eid, args=None, *, tenant="acme", workflow="wf-9",
        actor="agent://etl/1", correlation="sess-9", **extra):
    e = {"tenant_id": tenant, "workflow_id": workflow, "actor": actor,
         "correlation_id": correlation, "sequence_id": seq, "event_id": eid,
         "operation": op, "credential_scope": {"principal": actor},
         "arguments": args or {}}
    e.update(extra)
    return e


def signals_of(findings, recipe_id=None):
    return [f.signal for f in findings
            if recipe_id is None or f.recipe_id == recipe_id]


def run(ont, events, **kw):
    az = SequenceRiskAnalyzer(ont, **kw)
    out = []
    for ev in events:
        out.extend(az.observe(ev))
    return az, out


def trusted_registry(records):
    from composite_threat_detector.providers import FixtureProvider, ProviderRegistry
    return ProviderRegistry(providers=(
        FixtureProvider("trusted-fixture", "1.0.0", records, source_system="test"),))


EXFIL = "DATA_EXFILTRATION_ASSEMBLY"


# 1. True harmful sequence -------------------------------------------------
def test_01_true_harmful_sequence_escalates():
    _, out = run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 2. Benign look-alike (approved/internal sink, no EGRESS_PATH) ------------
def test_02_benign_lookalike_does_not_escalate():
    _, out = run(DIGITAL_ONTOLOGY, scenarios.benign_migration_events, specs=(BY_CASE,))
    assert signals.ESCALATE not in signals_of(out)


# 3. Authorized security test (TRUSTED, verified approval) -> not escalate -
def test_03_authorized_security_test_qualified():
    events = [
        dig("SECRET_READ", "t:1", "e1", {"enumerate": True}, workflow="wf-test"),
        dig("DB_MUTATION", "t:2", "e2", {}, workflow="wf-test",
            target_resource=["arn:aws:rds:::customers"]),
        dig("NET_EXPOSE", "t:3", "e3", {"cidr": "203.0.113.1/32"}, workflow="wf-test",
            approval={"tag": "authorized_security_test", "approver": "user://red",
                      "ticket": "PT-1", "workflow_id": "wf-test"}),
    ]
    registry = trusted_registry([{
        "record_id": "PT-1", "provider_type": "penetration_test_authorization",
        "tag": "authorized_security_test", "tenant": "acme", "workflow": "wf-test",
        "actor": "*", "target_family": "*", "operations": "*", "destinations": "*",
        "environment": "*", "tools": "*", "approver_identity": "user://red",
        "approver_authority": "security_lead"}])
    az, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,), providers=registry)
    assert signals.ESCALATE not in signals_of(out)
    key = out[0].assembly_key
    exfil = [f for f in az.standing_findings("acme", key) if f.recipe_id == EXFIL][0]
    assert exfil.benign_context_evidence["status"] == "NEUTRALIZED"
    assert exfil.purpose["purpose_consistency_status"] == "VERIFIED_CONSISTENT"
    assert exfil.signal == signals.OBSERVE


# 4. Out-of-order arrival (positions still correct) -----------------------
def test_04_out_of_order_still_detected():
    e = scenarios.exfiltration_events
    shuffled = [e[3], e[1], e[0], e[2]]  # egress, data, cred, monitoring
    _, out = run(DIGITAL_ONTOLOGY, shuffled, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 5. Long-and-slow (persistent fragments survive a short window) ----------
def test_05_long_and_slow_detected_via_persistent_ledger():
    from composite_threat_detector import TimescalePolicy
    # aggressive decay + tiny window: transient evidence would vanish, but the
    # capability fragments are PERSISTENT, so the assembly still completes.
    ts = TimescalePolicy(unit="steps", decay_half_life=2.0, decay_floor=0.4,
                         short_window=2)
    events = [
        dig("SECRET_READ", "s:1", "e1", {}),                     # cred (persistent)
        dig("DB_MUTATION", "s:150", "e2", {},
            target_resource=["arn:aws:rds:::customers"]),        # data, far later
        dig("NET_EXPOSE", "s:900", "e3", {"cidr": "203.0.113.4/32"}),  # egress
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,), timescale=ts)
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 6. Cross-session (same actor, different correlations) -------------------
def test_06_cross_session_by_actor():
    events = [
        dig("SECRET_READ", "A:1", "e1", {}, workflow="wf-A", correlation="A",
            timestamp="2026-07-31T10:00:00.000Z"),
        dig("DB_MUTATION", "B:1", "e2", {}, workflow="wf-B", correlation="B",
            target_resource=["arn:aws:rds:::customers"],
            timestamp="2026-07-31T10:05:00.000Z"),
        dig("NET_EXPOSE", "C:1", "e3", {"cidr": "203.0.113.4/32"}, workflow="wf-C",
            correlation="C", timestamp="2026-07-31T10:10:00.000Z"),
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_ACTOR,))
    assert signals.ESCALATE in signals_of(out, EXFIL)
    esc = [f for f in out if f.signal == signals.ESCALATE][0]
    assert len(esc.related_correlations) >= 2


# 7. Multi-actor contributing to one case ---------------------------------
def test_07_multi_actor_one_case():
    events = [
        dig("SECRET_READ", "m:1", "e1", {}, actor="user://alice",
            timestamp="2026-07-31T10:00:00.000Z"),
        dig("DB_MUTATION", "m:2", "e2", {}, actor="user://bob",
            target_resource=["arn:aws:rds:::customers"],
            timestamp="2026-07-31T10:01:00.000Z"),
        dig("NET_EXPOSE", "m:3", "e3", {"cidr": "203.0.113.4/32"},
            actor="agent://svc/1", timestamp="2026-07-31T10:02:00.000Z"),
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 8. Human + agent in the same case ---------------------------------------
def test_08_human_plus_agent():
    events = [
        dig("SECRET_READ", "h:1", "e1", {}, actor="user://alice",
            timestamp="2026-07-31T10:00:00.000Z"),
        dig("DB_MUTATION", "h:2", "e2", {}, actor="agent://etl/1",
            target_resource=["arn:aws:rds:::customers"],
            timestamp="2026-07-31T10:01:00.000Z"),
        dig("NET_EXPOSE", "h:3", "e3", {"cidr": "203.0.113.4/32"},
            actor="agent://etl/1", timestamp="2026-07-31T10:02:00.000Z"),
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 9. Interleaved unrelated workflows -> no contamination ------------------
def test_09_interleaved_workflows_isolated():
    harmful = scenarios.exfiltration_events
    noise = [dig("SECRET_READ", "n:1", "z1", {}, workflow="wf-other",
                 correlation="other")]
    interleaved = [harmful[0], noise[0], harmful[1], harmful[2], harmful[3]]
    _, out = run(DIGITAL_ONTOLOGY, interleaved, specs=(BY_CASE,))
    escs = [f for f in out if f.signal == signals.ESCALATE]
    assert len(escs) == 1
    assert escs[0].entity_link_evidence["link_dims"]["workflow"] == "wf-9"


# 10. Repeated duplicate events (same event_id) ---------------------------
def test_10_duplicate_events_suppressed():
    e = scenarios.exfiltration_events
    with_dupes = [e[0], e[0], e[1], e[1], e[2], e[3], e[3]]
    az, out = run(DIGITAL_ONTOLOGY, with_dupes, specs=(BY_CASE,))
    assert az.report.duplicates_suppressed >= 3
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 11. Retried events (same idempotency_key) -------------------------------
def test_11_retries_suppressed():
    events = [
        dig("SECRET_READ", "r:1", "e1", {}, idempotency_key="k1"),
        dig("SECRET_READ", "r:1b", "e1b", {}, idempotency_key="k1"),  # retry
        dig("DB_MUTATION", "r:2", "e2", {},
            target_resource=["arn:aws:rds:::customers"]),
        dig("NET_EXPOSE", "r:3", "e3", {"cidr": "203.0.113.4/32"}),
    ]
    az, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert az.report.retries_suppressed >= 1
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 12. Same fragments across different tenants -> isolation ----------------
def test_12_tenant_isolation():
    events = [
        dig("SECRET_READ", "x:1", "e1", {}, tenant="A", workflow="wf"),
        dig("DB_MUTATION", "x:2", "e2", {}, tenant="A", workflow="wf",
            target_resource=["arn:aws:rds:::customers"]),
        dig("NET_EXPOSE", "x:3", "e3", {"cidr": "203.0.113.4/32"},
            tenant="B", workflow="wf"),  # egress lands under a DIFFERENT tenant
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert signals.ESCALATE not in signals_of(out)


# 13. Unknown threat not represented by any recipe -> miss (no finding) ----
def test_13_unknown_threat_missed_but_processed():
    events = [
        dig("CLOUD_SPEND_INCREASE", "u:1", "e1", {}),   # STAGING
        dig("SECRET_READ", "u:2", "e2", {"enumerate": True}),  # CRED + RECON
    ]
    az, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert not out                       # no recipe encodes this combination
    assert az.report.fragments_extracted >= 3   # but it WAS processed


# 14. Renamed tools with equivalent capability metadata -------------------
def test_14_capability_metadata_over_tool_name():
    events = [
        dig("X", "c:1", "e1", {}, capability="credential.read",
            tool={"name": "acme-vault-v2"}),
        dig("X", "c:2", "e2", {}, capability="data.read",
            tool={"name": "query-tool-x"},
            target_resource=["arn:aws:rds:::customers"]),
        dig("X", "c:3", "e3", {}, capability="network.egress",
            tool={"name": "egress-9000"}),
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 15. Expired approval -> not neutralized -> escalate ---------------------
def test_15_expired_approval_escalates():
    events = [
        dig("SECRET_READ", "p:1", "e1", {}, timestamp="2026-07-31T10:00:00.000Z"),
        dig("DB_MUTATION", "p:2", "e2", {}, target_resource=["arn:aws:rds:::customers"],
            timestamp="2026-07-31T10:01:00.000Z"),
        dig("NET_EXPOSE", "p:3", "e3", {"cidr": "203.0.113.4/32"},
            timestamp="2026-07-31T10:02:00.000Z",
            approval={"tag": "compliance_export", "approver": "user://dpo",
                      "ticket": "CHG-1", "workflow_id": "wf-9",
                      "exp": "2026-07-31T09:00:00.000Z"}),  # already expired
    ]
    _, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)


# 16. Valid TRUSTED approval matching scope -> neutralized ----------------
def test_16_valid_approval_neutralizes():
    registry = trusted_registry([{
        "record_id": "CHG-771", "provider_type": "compliance_export",
        "tag": "compliance_export", "tenant": "acme", "workflow": "wf-exp",
        "actor": "*", "target_family": "*", "operations": "*", "destinations": "*",
        "environment": "*", "tools": "*", "approver_identity": "user://dpo",
        "approver_authority": "data_protection_officer"}])
    az, out = run(DIGITAL_ONTOLOGY, scenarios.approved_export_events,
                  specs=(BY_CASE,), providers=registry)
    assert signals.ESCALATE not in signals_of(out)
    key = out[0].assembly_key
    exfil = [f for f in az.standing_findings("acme", key) if f.recipe_id == EXFIL][0]
    assert exfil.benign_context_evidence["status"] == "NEUTRALIZED"


# 16b. The SAME approval claim WITHOUT a trusted provider does NOT neutralize
def test_16b_self_declared_purpose_does_not_neutralize():
    az, out = run(DIGITAL_ONTOLOGY, scenarios.approved_export_events, specs=(BY_CASE,))
    assert signals.ESCALATE in signals_of(out, EXFIL)  # self-declared != verified
    esc = [f for f in out if f.signal == signals.ESCALATE][0]
    assert esc.purpose["purpose_consistency_status"] == "UNVERIFIED"
    assert esc.purpose["neutralizes"] is False


# 17. Ambiguous entity linkage (no key dim present) -----------------------
def test_17_ambiguous_linkage_recorded_not_grouped():
    # spec groups by workflow, but these events carry no workflow id
    events = [dig("SECRET_READ", "", "e1", {}, workflow="", correlation="")]
    az, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,))
    assert not out
    assert az.report.ambiguous_links >= 1


# 18. Analyzer unavailable (bounded-state exhaustion) ---------------------
def test_18_bounded_state_emits_unavailable():
    limits = StateLimits(max_instances_per_assembly=1)
    events = [
        dig("SECRET_READ", "b:1", "e1", {"enumerate": True}),  # 2 instances > cap
        dig("DB_MUTATION", "b:2", "e2", {},
            target_resource=["arn:aws:rds:::customers"]),
    ]
    az, out = run(DIGITAL_ONTOLOGY, events, specs=(BY_CASE,), limits=limits)
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    assert az.report.unavailable_events >= 1


# 19. Recipe-version change during an active case -------------------------
def test_19_recipe_version_change_mid_case():
    v2 = tuple(dataclasses.replace(r, version="9.9.9")
               for r in R.DIGITAL_ONTOLOGY.recipes)
    ont2 = dataclasses.replace(R.DIGITAL_ONTOLOGY, version="9.9.9", recipes=v2)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    az.observe(scenarios.exfiltration_events[0])
    az.observe(scenarios.exfiltration_events[1])
    az.load_ontology(ont2)
    out = []
    out += az.observe(scenarios.exfiltration_events[2])
    out += az.observe(scenarios.exfiltration_events[3])
    esc = [f for f in out if f.signal == signals.ESCALATE and f.recipe_id == EXFIL]
    assert esc and esc[0].recipe_version == "9.9.9"


# 20. Policy converts escalation to HOLD_FOR_REVIEW (authoritative layer) --
def test_20_policy_binds_consequence():
    from composite_threat_detector import PolicyBinding, policy
    _, out = run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events, specs=(BY_CASE,))
    esc = [f for f in out if f.signal == signals.ESCALATE][0]
    decision = PolicyBinding().decide(esc)
    assert decision["consequence"] == policy.HOLD_FOR_REVIEW
    assert decision["authority"] == "ACTIONGATE_POLICY"


# --- cross-cutting invariants --------------------------------------------
def test_determinism_same_stream_same_finding_ids():
    a, _ = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    b, _ = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    assert [f["finding_id"] for f in a] == [f["finding_id"] for f in b]
    assert all(len(f["finding_id"].split(":")[1]) == 64 for f in a)


def test_analyzer_never_emits_authorization():
    az, out = run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events, specs=(BY_CASE,))
    for f in out:
        assert f.signal in (signals.OBSERVE, signals.ESCALATE, signals.UNAVAILABLE)
        assert f.signal not in signals.FORBIDDEN_SIGNALS


def test_removing_analyzer_does_not_increase_authority():
    from composite_threat_detector import PolicyBinding, policy
    # No findings (analyzer disabled/absent) => policy binds NO_CONSEQUENCE,
    # i.e. the per-action gate decision stands unchanged.
    assert policy.decide_batch([]) == []
    d = PolicyBinding().decide(
        {"signal": "OBSERVE", "severity": "LOW", "finding_id": "x"})
    assert d["consequence"] in (policy.LOG_ONLY,)


def test_evidence_adapter_is_advisory():
    from composite_threat_detector import to_advisory_evidence
    _, out = run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events, specs=(BY_CASE,))
    esc = [f for f in out if f.signal == signals.ESCALATE][0]
    ev = to_advisory_evidence(esc, bound_to="sha-256:" + "a" * 64,
                              generated_at="2026-07-31T00:00:00.000Z")
    p = ev["payload"]
    assert p["authority"] == "ADVISORY"
    assert p["effect"] == "ESCALATE"
    assert p["class"] == "behavioral"
    assert p["bound_to"] == "sha-256:" + "a" * 64


def test_report_integrity_fields_present():
    az, _ = run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events, specs=(BY_CASE,))
    d = az.report.to_dict()
    for field in ("analyzer_enabled", "recipe_versions", "events_ingested",
                  "fragments_extracted", "events_linked", "assemblies_touched",
                  "duplicates_suppressed", "unavailable_events"):
        assert field in d


# --- ontology / recipe validation ----------------------------------------
def test_recipe_rejects_unknown_fragment():
    from composite_threat_detector import Ontology, Recipe
    with pytest.raises(ValueError):
        Ontology(ontology_id="bad", version="0", fragments={},
                 recipes=(Recipe("r", "1", "r", frozenset({"NOPE"})),),
                 extract=lambda e, c: [])


def test_recipe_rejects_required_optional_overlap():
    from composite_threat_detector import Recipe
    with pytest.raises(ValueError):
        Recipe("r", "1", "r", frozenset({"X"}), optional=frozenset({"X"}))
