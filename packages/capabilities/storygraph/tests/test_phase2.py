"""Phase-2 infrastructure tests: providers/purpose, ordering, raw-evidence,
governance, recipe-version binding, audit, shadow policy.
"""

from __future__ import annotations

import dataclasses

from ugence_storygraph import (
    BY_ACTOR,
    BY_CASE,
    DIGITAL_ONTOLOGY,
    FixtureProvider,
    PolicyBinding,
    ProviderRegistry,
    SequenceRiskAnalyzer,
    StateLimits,
    TimescalePolicy,
    ordering,
    signals,
)
from ugence_storygraph import fragments as F
from ugence_storygraph import recipes as R

EXFIL = "DATA_EXFILTRATION_ASSEMBLY"


def dig(op, seq, eid, args=None, *, tenant="acme", workflow="wf-9",
        actor="agent://etl/1", correlation="sess-9", **extra):
    e = {"tenant_id": tenant, "workflow_id": workflow, "actor": actor,
         "correlation_id": correlation, "sequence_id": seq, "event_id": eid,
         "operation": op, "credential_scope": {"principal": actor},
         "arguments": args or {}}
    e.update(extra)
    return e


def exfil_events(**kw):
    return [
        dig("SECRET_READ", "s:1", "e1", {}, **kw),
        dig("DB_MUTATION", "s:2", "e2", {}, target_resource=["arn:aws:rds:::customers"],
            **kw),
        dig("NET_EXPOSE", "s:3", "e3", {"cidr": "203.0.113.4/32"}, **kw),
    ]


def registry(records):
    return ProviderRegistry(providers=(
        FixtureProvider("fx", "1.0.0", records, source_system="test"),))


def run(events, **kw):
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, **kw)
    out = []
    for ev in events:
        out.extend(az.observe(ev))
    return az, out


def sigs(out, rid=EXFIL):
    return [f.signal for f in out if f.recipe_id == rid]


# --- trusted providers / purpose ------------------------------------------
def test_verified_authorization_neutralizes():
    reg = registry([{"record_id": "", "tag": "compliance_export", "tenant": "acme",
                     "workflow": "wf-9", "actor": "*", "target_family": "*",
                     "operations": "*", "destinations": "*", "environment": "*",
                     "tools": "*", "approver_identity": "u", "approver_authority": "dpo"}])
    evs = exfil_events()
    evs[-1]["approval"] = {"tag": "compliance_export", "approver": "u", "ticket": ""}
    az, out = run(evs, specs=(BY_CASE,), providers=reg)
    assert signals.ESCALATE not in sigs(out)


def test_expired_authorization_does_not_neutralize():
    reg = registry([{"record_id": "", "tag": "compliance_export", "tenant": "acme",
                     "workflow": "wf-9", "actor": "*", "target_family": "*",
                     "operations": "*", "destinations": "*", "environment": "*",
                     "tools": "*", "approver_identity": "u", "approver_authority": "dpo",
                     "expiry": 1000.0}])
    evs = [dig("SECRET_READ", "s:1", "e1", {}, timestamp="2026-07-31T10:00:00.000Z"),
           dig("DB_MUTATION", "s:2", "e2", {}, target_resource=["arn:aws:rds:::customers"],
               timestamp="2026-07-31T10:01:00.000Z"),
           dig("NET_EXPOSE", "s:3", "e3", {"cidr": "203.0.113.4/32"},
               timestamp="2026-07-31T10:02:00.000Z",
               approval={"tag": "compliance_export", "approver": "u"})]
    az, out = run(evs, specs=(BY_CASE,), providers=reg)
    assert signals.ESCALATE in sigs(out)  # expired window -> not neutralized


def test_scope_mismatched_authorization_does_not_neutralize():
    reg = registry([{"record_id": "", "tag": "compliance_export", "tenant": "acme",
                     "workflow": "OTHER-WF", "actor": "*", "target_family": "*",
                     "operations": "*", "destinations": "*", "environment": "*",
                     "tools": "*", "approver_identity": "u", "approver_authority": "dpo"}])
    evs = exfil_events()
    evs[-1]["approval"] = {"tag": "compliance_export", "approver": "u"}
    az, out = run(evs, specs=(BY_CASE,), providers=reg)
    assert signals.ESCALATE in sigs(out)


def test_missing_authority_does_not_neutralize():
    reg = registry([{"record_id": "", "tag": "compliance_export", "tenant": "acme",
                     "workflow": "wf-9", "actor": "*", "target_family": "*",
                     "operations": "*", "destinations": "*", "environment": "*",
                     "tools": "*", "approver_identity": "u", "approver_authority": ""}])
    evs = exfil_events()
    evs[-1]["approval"] = {"tag": "compliance_export", "approver": "u"}
    az, out = run(evs, specs=(BY_CASE,), providers=reg)
    assert signals.ESCALATE in sigs(out)


def test_cross_tenant_authorization_never_matches():
    # authorization is for tenant "other"; assembly is tenant "acme"
    reg = registry([{"record_id": "", "tag": "compliance_export", "tenant": "other",
                     "workflow": "*", "actor": "*", "target_family": "*",
                     "operations": "*", "destinations": "*", "environment": "*",
                     "tools": "*", "approver_identity": "u", "approver_authority": "dpo"}])
    evs = exfil_events()
    evs[-1]["approval"] = {"tag": "compliance_export", "approver": "u"}
    az, out = run(evs, specs=(BY_CASE,), providers=reg)
    assert signals.ESCALATE in sigs(out)


# --- ordering / clock -----------------------------------------------------
def test_conflicting_order_blocks_strict_recipe():
    # same correlation; source_sequence and event_time disagree
    evs = [
        dig("SECRET_READ", "c:1", "e1", {}, timestamp="2026-07-31T10:03:00.000Z",
            ordering={"source_sequence": 1}),
        dig("DB_MUTATION", "c:2", "e2", {}, target_resource=["arn:aws:rds:::customers"],
            timestamp="2026-07-31T10:02:00.000Z", ordering={"source_sequence": 2}),
        dig("NET_EXPOSE", "c:3", "e3", {"cidr": "203.0.113.4/32"},
            timestamp="2026-07-31T10:01:00.000Z", ordering={"source_sequence": 3}),
    ]
    az, out = run(evs, specs=(BY_CASE,))
    assert signals.ESCALATE not in sigs(out)
    assert az.report.order_conflicting >= 1


def test_ambiguous_order_caps_escalation_beyond_matcher():
    # cross-correlation, no timestamps, distinct positions: matcher ordering passes
    # (positions ascend) but clock order is AMBIGUOUS -> escalation withheld.
    evs = [
        dig("SECRET_READ", "a:1", "e1", {}, workflow="w", correlation="a"),
        dig("DB_MUTATION", "b:2", "e2", {}, workflow="w", correlation="b",
            target_resource=["arn:aws:rds:::customers"]),
        dig("NET_EXPOSE", "c:3", "e3", {"cidr": "203.0.113.4/32"}, workflow="w",
            correlation="c"),
    ]
    az, out = run(evs, specs=(BY_ACTOR,))
    assert signals.ESCALATE not in sigs(out)
    assert az.report.order_ambiguous >= 1
    key = out[0].assembly_key
    f = [x for x in az.standing_findings("acme", key) if x.recipe_id == EXFIL][0]
    assert f.ordering_status["clock_status"] == ordering.AMBIGUOUS_ORDER


# --- raw evidence survives active-risk decay / reset ----------------------
def test_raw_evidence_and_provenance_survive_reset():
    az, out = run(exfil_events(), specs=(BY_CASE,))
    assert signals.ESCALATE in sigs(out)
    key = out[0].assembly_key
    az.observe({"type": "reset", "tenant_id": "acme", "workflow_id": "wf-9",
                "correlation_id": "sess-9", "sequence_id": "r:9", "event_id": "rst"})
    assert az.ledger.get("acme", key) is None            # active state cleared
    recon = az.reconstruct("acme", key)
    kinds = {e["kind"] for e in recon["audit_events"]}
    assert "RAW_EVIDENCE" in kinds                        # raw evidence retained
    assert "FINDING" in kinds                             # finding provenance retained
    assert "ASSEMBLY_RESET" in kinds                      # reset is audited
    assert recon["chain_valid"] is True


def test_audit_chain_is_tamper_evident():
    az, _ = run(exfil_events(), specs=(BY_CASE,))
    assert az.audit.verify_chain() is True
    assert len(az.audit) >= 3


# --- state governance -----------------------------------------------------
def test_candidate_linkage_fanout_is_fail_visible():
    limits = StateLimits(max_candidate_linkages_per_event=1)
    # BY_CASE + BY_ACTOR => 2 candidate links for an event with both -> overload
    az, out = run(exfil_events(), specs=(BY_CASE, BY_ACTOR), limits=limits)
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    assert az.report.governance_rejections >= 1
    assert any(e.kind == "OVERLOAD" for e in az.audit.all())


def test_per_actor_assembly_quota_fail_visible():
    limits = StateLimits(max_assemblies_per_actor=1)
    evs = [dig("SECRET_READ", "s:1", "e1", {}, workflow="wfA"),
           dig("SECRET_READ", "s:2", "e2", {}, workflow="wfB")]  # 2nd assembly, same actor
    az, out = run(evs, specs=(BY_CASE,), limits=limits)
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    assert az.report.governance_rejections >= 1


def test_instance_cap_emits_unavailable_and_audits_eviction():
    limits = StateLimits(max_instances_per_assembly=1)
    evs = [dig("SECRET_READ", "s:1", "e1", {"enumerate": True}),  # 2 instances > cap
           dig("DB_MUTATION", "s:2", "e2", {})]
    az, out = run(evs, specs=(BY_CASE,), limits=limits)
    assert any(f.signal == signals.UNAVAILABLE for f in out)
    assert any(e.kind == "EVICTION" for e in az.audit.all())


# --- recipe-version binding + dual evaluation -----------------------------
def _v2_requires_staging():
    recipes = []
    for r in R.DIGITAL_ONTOLOGY.recipes:
        if r.recipe_id == EXFIL:
            r = dataclasses.replace(
                r, version="2.0.0",
                required=frozenset(r.required | {F.STAGING}))
        else:
            r = dataclasses.replace(r, version="2.0.0")
        recipes.append(r)
    return dataclasses.replace(R.DIGITAL_ONTOLOGY, version="2.0.0",
                               recipes=tuple(recipes))


def test_recipe_version_divergence_recorded_without_rewriting_history():
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    evs = exfil_events()
    az.observe(evs[0])                       # binds EXFIL @ 1.1.0
    az.observe(evs[1])
    az.load_ontology(_v2_requires_staging())  # now requires STAGING too
    az.observe(evs[2])                       # completes old recipe, not the new one
    assert az.report.recipe_version_divergences >= 1
    key = az.report.assemblies_touched and next(iter(
        [k for (_t, k) in az.ledger._by_tenant.get("acme", {}).items()]
        or [None]), None)
    # inspect the standing finding's version binding
    akey = list(az.ledger._by_tenant["acme"].keys())[0]
    f = [x for x in az.standing_findings("acme", akey) if x.recipe_id == EXFIL][0]
    assert f.recipe_version_binding["bound_version"] == "1.1.0"
    assert f.recipe_version_binding["current_version"] == "2.0.0"
    assert f.recipe_version_binding["divergent"] is True


# --- shadow policy --------------------------------------------------------
def test_shadow_policy_computes_but_does_not_enforce():
    az, out = run(exfil_events(), specs=(BY_CASE,))
    esc = [f for f in out if f.signal == signals.ESCALATE][0]
    d = PolicyBinding(shadow=True).decide(esc)
    assert d["consequence"] == "HOLD_FOR_REVIEW"     # computed
    assert d["effective_consequence"] == "NO_CONSEQUENCE"  # not enforced in shadow
    assert d["enforced"] is False
    # explicit (non-shadow) promotion would enforce
    d2 = PolicyBinding(shadow=False).decide(esc)
    assert d2["enforced"] is True and d2["effective_consequence"] == "HOLD_FOR_REVIEW"


def test_findings_are_stamped_shadow_mode():
    az, out = run(exfil_events(), specs=(BY_CASE,))
    assert all(f.shadow_mode is True for f in out)
    assert az.report.shadow_mode is True
