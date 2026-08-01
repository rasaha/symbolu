"""Historical-replay readiness gates H1–H8 + verdict (§14, §15).

Runs the synthetic readiness gates and emits exactly one phase verdict. This
phase caps at ``CONTINUE — historical replay ready`` (or a STOP) — it never issues
production-ready / enterprise-validated / enforcement-ready.
"""

from __future__ import annotations

from ugence_storygraph import (
    BY_ACTOR, BY_CASE, DIGITAL_ONTOLOGY, DurableAuditLog, FailingProvider,
    FixtureProvider, ProviderRegistry, SequenceRiskAnalyzer, StateLimits, ordering,
    recover_from_audit, signals,
)

from . import alerts, benchmark, corpus_gen, freeze

VERDICTS = (
    "STOP — freeze integrity inadequate",
    "STOP — durable reconstruction inadequate",
    "STOP — state exhaustion unsafe",
    "STOP — trusted-context failure unsafe",
    "STOP — ordering ambiguity unsafe",
    "STOP — operational cost excessive",
    "STOP — false-escalation burden excessive",
    "CONTINUE — synthetic robustness only",
    "CONTINUE — historical replay ready",
)


def _gate(passed, detail, label):
    return {"pass": bool(passed), "detail": detail, "evidence_label": label}


def _h1_freeze():
    fz = freeze.build_freeze("readiness", profile="final")
    ok_unchanged = True
    try:
        freeze.require_frozen(fz, official=True)
    except freeze.FreezeViolation:
        ok_unchanged = False
    tampered = dict(fz); tampered["recipes"] = ["X@9"]
    refused = False
    try:
        freeze.require_frozen(tampered, official=True)
    except freeze.FreezeViolation:
        refused = True
    dev_refused = False
    try:
        freeze.require_frozen(freeze.build_freeze("x", profile="dev"), official=True)
    except freeze.FreezeViolation:
        dev_refused = True
    return _gate(ok_unchanged and refused and dev_refused,
                 {"accepts_unchanged": ok_unchanged, "refuses_changed": refused,
                  "refuses_dev_profile": dev_refused},
                 "Measured — unit/integration test")


def _run_corpus_digests(seed):
    scen = corpus_gen.generate("adversarial_evasion", 40, seed)
    digests = []
    for sc in scen:
        specs = (BY_ACTOR,) if sc["family"] == "cross_session" else (BY_CASE,)
        prov = ProviderRegistry(providers=(FixtureProvider("fx", "1.0.0", sc["providers"]),)) \
            if sc["providers"] else None
        az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=specs, providers=prov)
        for ev in sc["events"]:
            for f in az.observe(ev):
                if f.signal == signals.ESCALATE:
                    digests.append(f.finding_id)
    return digests


def _h2_determinism():
    a = _run_corpus_digests(11)
    b = _run_corpus_digests(11)
    return _gate(a == b and a, {"escalations": len(a), "identical": a == b},
                 "Measured — synthetic behavioral corpus")


def _h3_durable(tmp="/tmp/ctd_readiness_audit.sqlite"):
    import os
    if os.path.exists(tmp):
        os.remove(tmp)
    from ugence_storygraph.demos import scenarios
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), audit=DurableAuditLog(tmp))
    live = [f.finding_id for ev in scenarios.exfiltration_events
            for f in az.observe(ev) if f.signal == signals.ESCALATE]
    az.audit.close()
    rec = recover_from_audit(DurableAuditLog(tmp), DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    akey = list(rec.ledger._by_tenant["acme"].keys())[0]
    recovered = sorted(f.finding_id for f in rec.standing_findings("acme", akey)
                       if f.signal == signals.ESCALATE)
    return _gate(sorted(live) == recovered and live,
                 {"live": len(live), "recovered": len(recovered)},
                 "Measured — restart/recovery test")


def _h4_state():
    limits = StateLimits(max_assemblies_per_tenant=2)
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), limits=limits)

    def op(t, w, n):
        return az.observe({"tenant_id": t, "workflow_id": w, "actor": f"a{w}",
                           "correlation_id": w, "sequence_id": f"{w}:1",
                           "event_id": f"{t}{n}", "operation": "SECRET_READ",
                           "credential_scope": {"principal": f"a{w}"}, "arguments": {}})
    op("a", "w1", 1); op("a", "w2", 2)
    over = op("a", "w3", 3)
    isolated = all(f.signal != signals.UNAVAILABLE for f in op("b", "w4", 1))
    fail_visible = any(f.signal == signals.UNAVAILABLE for f in over)
    return _gate(fail_visible and isolated,
                 {"fail_visible": fail_visible, "tenant_isolated": isolated},
                 "Measured — synthetic operational load")


def _h5_provider():
    from ugence_storygraph.demos import scenarios
    ev = list(scenarios.approved_export_events)
    ev[-1] = dict(ev[-1]); ev[-1]["approval"] = {"tag": "compliance_export", "approver": "u"}
    results = {}
    for name, prov in [
        ("unavailable", ProviderRegistry(providers=(FailingProvider(),))),
        ("revoked", ProviderRegistry(providers=(FixtureProvider("fx", "1.0.0", [{
            "record_id": "", "tag": "compliance_export", "tenant": "acme",
            "workflow": "wf-exp", "approver_authority": "dpo", "revoked": True}]),))),
    ]:
        az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), providers=prov)
        esc = any(f.signal == signals.ESCALATE for e in ev for f in az.observe(e))
        results[name] = esc  # must remain escalated (not neutralized)
    return _gate(all(results.values()), results, "Measured — unit/integration test")


def _h6_ordering():
    def e(op, seq, eid, args=None, **kw):
        d = {"tenant_id": "t", "workflow_id": "w", "actor": "a",
             "correlation_id": "c", "sequence_id": seq, "event_id": eid,
             "operation": op, "credential_scope": {"principal": "a"}, "arguments": args or {}}
        d.update(kw); return d
    evs = [e("SECRET_READ", "c:1", "1", timestamp="2026-07-31T10:03:00.000Z",
             ordering={"source_sequence": 1}),
           e("DB_MUTATION", "c:2", "2", target_resource=["arn:aws:rds:::x"],
             timestamp="2026-07-31T10:02:00.000Z", ordering={"source_sequence": 2}),
           e("NET_EXPOSE", "c:3", "3", {"cidr": "203.0.113.4/32"},
             timestamp="2026-07-31T10:01:00.000Z", ordering={"source_sequence": 3})]
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    esc = any(f.signal == signals.ESCALATE and f.recipe_id == "DATA_EXFILTRATION_ASSEMBLY"
              for ev in evs for f in az.observe(ev))
    return _gate((not esc) and az.report.order_conflicting >= 1,
                 {"escalated_under_conflict": esc,
                  "order_conflicting": az.report.order_conflicting},
                 "Measured — synthetic behavioral corpus")


def _h7_performance(threshold_ms=5.0):
    rep = benchmark.run_load("balanced", scale=30, seed=7)
    p95 = rep["runtime_ms_per_event"]["p95"]
    return _gate(p95 is not None and p95 <= threshold_ms,
                 {"p95_ms": p95, "threshold_ms": threshold_ms,
                  "events_per_second": rep["events_per_second"],
                  "note": "development host; not a production capacity claim"},
                 "Measured — synthetic operational load")


def _h8_benign_burden(max_false_escalation_rate=0.02):
    av = alerts.alert_volume("enterprise_like", scale=200, seed=7)
    m = av["measured"]
    total_benign_events = max(1, m["total_events"])
    fe_rate = m["false_escalations"] / total_benign_events
    return _gate(fe_rate <= max_false_escalation_rate,
                 {"false_escalations": m["false_escalations"],
                  "alerts_per_1000": m["alerts_per_1000_events"],
                  "false_escalation_rate": round(fe_rate, 5),
                  "threshold": max_false_escalation_rate,
                  "modeled_alerts_per_tenant_day": av["modeled"]["alerts_per_tenant_day"]},
                 "Measured — synthetic behavioral corpus + Modeled — operator workload")


def run() -> dict:
    gates = {
        "H1_freeze_integrity": _h1_freeze(),
        "H2_deterministic_replay": _h2_determinism(),
        "H3_durable_reconstruction": _h3_durable(),
        "H4_bounded_state_safety": _h4_state(),
        "H5_provider_safety": _h5_provider(),
        "H6_ordering_safety": _h6_ordering(),
        "H7_operational_performance": _h7_performance(),
        "H8_realistic_benign_burden": _h8_benign_burden(),
    }
    verdict = _verdict(gates)
    return {"gates": gates, "verdict": verdict,
            "phase_cap": "CONTINUE — historical replay ready",
            "disclaimer": ("Synthetic gates only. No enterprise-accuracy, intent, "
                           "novelty, enforcement, or production-readiness claim.")}


def _verdict(gates) -> str:
    if not gates["H1_freeze_integrity"]["pass"]:
        return "STOP — freeze integrity inadequate"
    if not gates["H3_durable_reconstruction"]["pass"]:
        return "STOP — durable reconstruction inadequate"
    if not gates["H4_bounded_state_safety"]["pass"]:
        return "STOP — state exhaustion unsafe"
    if not gates["H5_provider_safety"]["pass"]:
        return "STOP — trusted-context failure unsafe"
    if not gates["H6_ordering_safety"]["pass"]:
        return "STOP — ordering ambiguity unsafe"
    if not gates["H8_realistic_benign_burden"]["pass"]:
        return "STOP — false-escalation burden excessive"
    if not (gates["H2_deterministic_replay"]["pass"]
            and gates["H7_operational_performance"]["pass"]):
        return "CONTINUE — synthetic robustness only"
    return "CONTINUE — historical replay ready"
