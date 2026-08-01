"""Deterministic adversarial synthetic corpus (§9, §10).

Substantially more variation than the unit-test scenarios, across 25 families
including hard benign look-alikes intended to *expose* false escalations. Labels
are authored independently of analyzer outputs (they describe the ground-truth
activity, not what the analyzer does), and the scenarios are deliberately NOT all
built so the current rules pass — several are designed to miss or to false-alarm
so the evaluation is honest.

Everything is synthetic and deterministic (no randomness, no wall-clock). This is
``Measured — synthetic corpus`` evidence only; it is NOT enterprise performance.

Splits: ``dev`` / ``calibration`` / ``final``. The ``final`` split MUST NOT be
used to tune thresholds, linkage, decay, or benign exclusions (§10).
"""

from __future__ import annotations

from composite_threat_detector.canonical import digest

GENERATOR_VERSION = "ctd.corpus/1.0.0"

# ground-truth labels
HARMFUL = "harmful"       # a genuinely risky capability assembly
BENIGN = "benign"         # legitimate activity (some are hard look-alikes)
UNKNOWN = "unknown"       # genuinely risky but NOT encoded by any recipe
INFRA = "infra"           # exercises linkage/governance, not a threat label

FAMILIES = [
    "confirmed_harmful", "legit_backup", "legit_migration", "approved_pentest",
    "disaster_recovery", "incident_response", "admin_maintenance",
    "mixed_human_agent", "cross_session", "multi_actor", "long_and_slow",
    "reordered", "missing_events", "duplicate_retried", "renamed_tools",
    "noise_inserted", "expired_approval", "scope_mismatched_approval",
    "destination_mismatch", "actor_identity_mismatch", "competing_explanations",
    "ambiguous_linkage", "cross_tenant_attempt", "state_exhaustion",
    "unknown_threat",
]


def _e(op, seq, eid, args=None, *, tenant="acme", workflow="wf", actor="agent://a",
       correlation="c", **extra):
    d = {"tenant_id": tenant, "workflow_id": workflow, "actor": actor,
         "correlation_id": correlation, "sequence_id": seq, "event_id": eid,
         "operation": op, "credential_scope": {"principal": actor},
         "arguments": args or {}}
    d.update(extra)
    return d


def _cred(seq, eid, **kw):
    return _e("SECRET_READ", seq, eid, {}, **kw)


def _data(seq, eid, **kw):
    kw.setdefault("target_resource", ["arn:aws:rds:::customers"])
    return _e("DB_MUTATION", seq, eid, {}, **kw)


def _egress_ext(seq, eid, **kw):
    return _e("NET_EXPOSE", seq, eid, {"cidr": "203.0.113.4/32"}, **kw)


def _egress_internal(seq, eid, **kw):
    return _e("NET_EXPOSE", seq, eid, {"cidr": "10.0.0.4/32", "sink_approved": True}, **kw)


def _approval(tag, **over):
    a = {"tag": tag, "approver": "user://approver", "ticket": "TCK-1"}
    a.update(over)
    return a


def _record(tag, **over):
    r = {"record_id": "TCK-1", "tag": tag, "tenant": "acme", "workflow": "*",
         "actor": "*", "target_family": "*", "operations": "*", "destinations": "*",
         "environment": "*", "tools": "*", "approver_identity": "user://approver",
         "approver_authority": "authority"}
    r.update(over)
    return r


def _family(name):  # -> (events, providers, label, expected_escalation, difficulty)
    if name == "confirmed_harmful":
        return ([_cred("c:1", "1"), _data("c:2", "2"), _egress_ext("c:3", "3")],
                [], HARMFUL, True, "easy")
    if name == "legit_backup":
        # backup reads data and writes to an approved internal sink: no exfil egress
        return ([_cred("c:1", "1"), _data("c:2", "2"), _egress_internal("c:3", "3")],
                [], BENIGN, False, "medium")
    if name == "legit_migration":
        return ([_cred("c:1", "1"), _data("c:2", "2"), _egress_internal("c:3", "3")],
                [], BENIGN, False, "medium")
    if name == "approved_pentest":
        evs = [_cred("c:1", "1"), _data("c:2", "2"),
               _egress_ext("c:3", "3", approval=_approval("authorized_security_test"))]
        return (evs, [_record("authorized_security_test")], BENIGN, False, "hard")
    if name == "disaster_recovery":
        return ([_cred("c:1", "1"), _data("c:2", "2"), _egress_internal("c:3", "3")],
                [], BENIGN, False, "medium")
    if name == "incident_response":
        evs = [_cred("c:1", "1"), _data("c:2", "2"),
               _egress_ext("c:3", "3", approval=_approval("incident_response_case"))]
        # incident_response is not in the recipe's benign_exclusions -> not neutralized
        return (evs, [_record("incident_response_case")], BENIGN, True, "hard")
    if name == "admin_maintenance":
        return ([_cred("c:1", "1"),
                 _e("KEY_ROTATE", "c:2", "2", {}),
                 _e("CLOUD_SPEND_INCREASE", "c:3", "3", {})], [], BENIGN, False, "easy")
    if name == "mixed_human_agent":
        return ([_cred("c:1", "1", actor="user://alice", timestamp="2026-07-31T10:00:00.000Z"),
                 _data("c:2", "2", actor="agent://a", timestamp="2026-07-31T10:01:00.000Z"),
                 _egress_ext("c:3", "3", actor="agent://a", timestamp="2026-07-31T10:02:00.000Z")],
                [], HARMFUL, True, "medium")
    if name == "cross_session":
        return ([_cred("s1:1", "1", correlation="s1", timestamp="2026-07-31T10:00:00.000Z"),
                 _data("s2:1", "2", correlation="s2", timestamp="2026-07-31T10:05:00.000Z"),
                 _egress_ext("s3:1", "3", correlation="s3", timestamp="2026-07-31T10:10:00.000Z")],
                [], HARMFUL, True, "hard")
    if name == "multi_actor":
        return ([_cred("c:1", "1", actor="user://a", timestamp="2026-07-31T10:00:00.000Z"),
                 _data("c:2", "2", actor="user://b", timestamp="2026-07-31T10:01:00.000Z"),
                 _egress_ext("c:3", "3", actor="svc://c", timestamp="2026-07-31T10:02:00.000Z")],
                [], HARMFUL, True, "hard")
    if name == "long_and_slow":
        return ([_cred("c:1", "1"), _data("c:400", "2"), _egress_ext("c:900", "3")],
                [], HARMFUL, True, "hard")
    if name == "reordered":
        base = [_cred("c:1", "1"), _data("c:2", "2"), _egress_ext("c:3", "3")]
        return ([base[2], base[1], base[0]], [], HARMFUL, True, "medium")
    if name == "missing_events":
        # only credential + egress; data-access step missing -> incomplete recipe
        return ([_cred("c:1", "1"), _egress_ext("c:3", "3")], [], BENIGN, False, "medium")
    if name == "duplicate_retried":
        c = _cred("c:1", "1")
        return ([c, c, _data("c:2", "2", idempotency_key="k"),
                 _e("DB_MUTATION", "c:2b", "2b", {}, target_resource=["arn:aws:rds:::customers"],
                    idempotency_key="k"), _egress_ext("c:3", "3")],
                [], HARMFUL, True, "medium")
    if name == "renamed_tools":
        return ([_e("X", "c:1", "1", {}, capability="credential.read",
                    tool={"name": "vault-v9"}),
                 _e("X", "c:2", "2", {}, capability="data.read", tool={"name": "q-x"},
                    target_resource=["arn:aws:rds:::customers"]),
                 _e("X", "c:3", "3", {}, capability="network.egress",
                    tool={"name": "egr-7"})], [], HARMFUL, True, "hard")
    if name == "noise_inserted":
        return ([_cred("c:1", "1"),
                 _e("CLOUD_SPEND_INCREASE", "c:2", "2", {}),
                 _data("c:3", "3"),
                 _e("KEY_ROTATE", "c:4", "4", {}),
                 _egress_ext("c:5", "5")], [], HARMFUL, True, "medium")
    if name == "expired_approval":
        evs = [_cred("c:1", "1", timestamp="2026-07-31T10:00:00.000Z"),
               _data("c:2", "2", timestamp="2026-07-31T10:01:00.000Z"),
               _egress_ext("c:3", "3", timestamp="2026-07-31T10:02:00.000Z",
                           approval=_approval("compliance_export"))]
        return (evs, [_record("compliance_export", expiry=1000.0)], BENIGN, True, "hard")
    if name == "scope_mismatched_approval":
        evs = [_cred("c:1", "1"), _data("c:2", "2"),
               _egress_ext("c:3", "3", approval=_approval("compliance_export"))]
        return (evs, [_record("compliance_export", workflow="OTHER")], BENIGN, True, "hard")
    if name == "destination_mismatch":
        # exfil to external destination, approval bound to a different destination
        evs = [_cred("c:1", "1"), _data("c:2", "2"),
               _egress_ext("c:3", "3", approval=_approval("compliance_export"))]
        return (evs, [_record("compliance_export", destinations=["10.0.0.9/32"])],
                BENIGN, True, "hard")
    if name == "actor_identity_mismatch":
        evs = [_cred("c:1", "1", actor="agent://a"), _data("c:2", "2", actor="agent://a"),
               _egress_ext("c:3", "3", actor="agent://a",
                           approval=_approval("compliance_export"))]
        return (evs, [_record("compliance_export", actor="agent://different")],
                BENIGN, True, "hard")
    if name == "competing_explanations":
        # a valid approval AND harmful shape; verified approval should neutralize
        evs = [_cred("c:1", "1"), _data("c:2", "2"),
               _egress_ext("c:3", "3", approval=_approval("compliance_export"))]
        return (evs, [_record("compliance_export")], BENIGN, False, "hard")
    if name == "ambiguous_linkage":
        return ([_e("SECRET_READ", "", "1", {}, workflow="", correlation="")],
                [], INFRA, False, "easy")
    if name == "cross_tenant_attempt":
        return ([_cred("c:1", "1", tenant="A"), _data("c:2", "2", tenant="A"),
                 _egress_ext("c:3", "3", tenant="B")], [], HARMFUL, False, "hard")
    if name == "state_exhaustion":
        return ([_e("SECRET_READ", "c:1", "1", {"enumerate": True}),
                 _data("c:2", "2")], [], INFRA, False, "easy")
    if name == "unknown_threat":
        # genuinely risky in reality, but no recipe encodes this combination
        return ([_e("CLOUD_SPEND_INCREASE", "c:1", "1", {}),
                 _cred("c:2", "2")], [], UNKNOWN, False, "hard")
    raise KeyError(name)


def _split_for(index: int) -> str:
    return ("dev", "calibration", "final")[index % 3]


def build_corpus() -> list[dict]:
    """Return the full deterministic corpus (list of scenario dicts)."""
    out = []
    for i, fam in enumerate(FAMILIES):
        events, providers, label, expected, difficulty = _family(fam)
        scenario_id = f"{fam}-000"
        body = {"events": events, "providers": providers}
        out.append({
            "scenario_id": scenario_id,
            "family": fam,
            "label": label,
            "expected_escalation": expected,
            "difficulty": difficulty,
            "split": _split_for(i),
            "tenant": events[0].get("tenant_id", "") if events else "",
            "actors": sorted({e.get("actor", "") for e in events if e.get("actor")}),
            "generator_version": GENERATOR_VERSION,
            "content_hash": digest(body, domain="CTD-CORPUS"),
            "events": events,
            "providers": providers,
        })
    return out


def freeze(code_commit: str = "UNSET", policy_version: str = "ctd.policy/1.0.0") -> dict:
    """Produce the pre-evaluation freeze (§10).

    Captures recipe versions, linkage schema, per-recipe thresholds, corpus hash,
    code commit, and policy versions. The final split MUST NOT be used to tune any
    of these after freezing.
    """
    from composite_threat_detector.linkage import LINKAGE_SCHEMA_VERSION
    from composite_threat_detector.recipes import DIGITAL_ONTOLOGY

    thresholds = {r.ref: {"observe": r.observe_threshold,
                          "escalate": r.escalation_threshold,
                          "completion": r.completion_threshold}
                  for r in DIGITAL_ONTOLOGY.recipes}
    man = manifest()
    body = {
        "recipe_versions": sorted(r.ref for r in DIGITAL_ONTOLOGY.recipes),
        "linkage_schema": LINKAGE_SCHEMA_VERSION,
        "thresholds": thresholds,
        "corpus_hash": man["corpus_hash"],
        "corpus_generator_version": GENERATOR_VERSION,
        "code_commit": code_commit,
        "policy_version": policy_version,
        "final_split_scenarios": sorted(
            e["scenario_id"] for e in man["scenarios"] if e["split"] == "final"),
    }
    body["freeze_digest"] = digest(body, domain="CTD-FREEZE")
    body["_note"] = ("Frozen before the final evaluation run. The 'final' split "
                     "must not be used to tune recipes, linkage, decay, thresholds, "
                     "or benign exclusions (§10).")
    return body


def manifest(corpus: list[dict] | None = None) -> dict:
    corpus = corpus or build_corpus()
    entries = [{k: s[k] for k in ("scenario_id", "family", "label",
                                  "expected_escalation", "difficulty", "split",
                                  "tenant", "actors", "generator_version",
                                  "content_hash")} for s in corpus]
    return {
        "generator_version": GENERATOR_VERSION,
        "families": FAMILIES,
        "size": len(entries),
        "splits": {sp: sum(1 for e in entries if e["split"] == sp)
                   for sp in ("dev", "calibration", "final")},
        "corpus_hash": digest([e["content_hash"] for e in entries], domain="CTD-CORPUS-SET"),
        "scenarios": entries,
    }
