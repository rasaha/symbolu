"""Enterprise Story Policy Pack + historical-replay readiness tests (§3-§16).

Confirms: witness terminology, the two-commit evidence chain, StoryPolicyPack schema
validation + compiler rejections, that the compiled reference pack reproduces the
FROZEN graph (no semantics change), business/policy-as-code convergence, lifecycle
approvals, event/provider mappings, the §12 scenario matrix, and deterministic
synthetic replay with enterprise metrics held NOT RUN.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from composite_threat_detector import (
    ACCOUNT_TAKEOVER_TRANSFER as ATO, Authorization, MINIMALITY_BASIS,
    ObservedEvent, completion_witness, evaluate_proposed_action, financial as F,
    storyverdict as V,
)
from composite_threat_detector.policypack import (
    business_form as BF, compiler, event_mapping, lifecycle, providers_mapping,
    reference, replay, schema,
)
from evaluation import evidence_chain as EC
from evaluation import freeze

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(os.path.dirname(HERE), "composite_threat_detector",
                       "policypack", "fixtures", "account_takeover_replay.json")


def oe(fr, e, p, **k):
    return ObservedEvent(fr, e, p, None, "u1", dict(k))


# ===========================================================================
# §3  witness terminology
# ===========================================================================
def test_minimality_terminology():
    w = completion_witness(
        ATO, [oe(F.CRED_RESET, "r", 1, account="a1"),
              oe(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
              oe(F.BENEFICIARY_ADD, "b", 3, account="a1", beneficiary="bob")],
        oe(F.TRANSFER, "x", 9, account="a1", beneficiary="bob", device="d1", amount="9000"))
    d = w.to_dict()
    assert d["minimality_basis"] == "SEMANTIC_EQUIVALENCE_CLASS" == MINIMALITY_BASIS
    assert d["canonical_witness_minimal"] is True
    assert d["minimality_verified"] is True          # back-compat alias preserved
    assert w.canonical_witness_minimal is True


# ===========================================================================
# §4  two-commit evidence chain
# ===========================================================================
def test_evidence_chain_rejects_placeholder_commit():
    with pytest.raises(EC.EvidenceChainError):
        EC.build_evidence_record(
            evaluated_source_commit="pending-run3", invoked_at="t", freeze_digest="f",
            holdout_manifest_hash="h", generator_version="g", seeds=[1],
            graph_version="1", matcher_version="2", policy_version="1",
            witness_tiebreak_version="2", raw_metric_counts={"n": 1},
            derived_metrics={"r": 1.0}, verdict="CONTINUE")


def test_evidence_commit_paths_verified():
    ok = EC.verify_evidence_commit_paths(
        ["cyber_security/composite_threat_detector/evaluation/evidence/run4.json"])
    bad = EC.verify_evidence_commit_paths(
        ["cyber_security/composite_threat_detector/composite_threat_detector/storygraph.py"])
    assert ok["ok"] and not bad["ok"]


def test_evidence_record_seals_and_verifies():
    rec = EC.build_evidence_record(
        evaluated_source_commit="abc1234", invoked_at="2026-08-01",
        freeze_digest="sha-256:x", holdout_manifest_hash="sha-256:y",
        generator_version="g", seeds=[911], graph_version="1", matcher_version="2",
        policy_version="1", witness_tiebreak_version="2",
        raw_metric_counts={"n": 147}, derived_metrics={"r": 1.0}, verdict="CONTINUE")
    assert EC.verify_record(rec)["ok"]
    tampered = dict(rec); tampered["verdict"] = "STOP"
    assert not EC.verify_record(tampered)["ok"]


# ===========================================================================
# §5  schema validation + §7 compiler rejections
# ===========================================================================
def test_reference_pack_valid():
    assert schema.validate_pack(reference.ACCOUNT_TAKEOVER_PACK) == []


def test_json_schema_contract_matches_python_validator():
    path = os.path.join(os.path.dirname(HERE), "composite_threat_detector",
                        "policypack", "schemas", "storypolicypack.schema.json")
    with open(path) as fh:
        js = json.load(fh)
    assert js["$schema"].endswith("2020-12/schema") and js["$id"] and js["title"]
    # the machine-readable contract's required top-level sections match the
    # authoritative Python validator's required set.
    assert set(js["required"]) == set(schema._REQUIRED_TOP)


def _bad(mutate):
    p = reference.account_takeover_pack()
    mutate(p)
    return schema.validate_pack(p)


def test_reject_missing_required_field():
    assert _bad(lambda p: p.pop("governance"))


def test_reject_unknown_node_reference():
    assert _bad(lambda p: p["harmful_story"]["edges"].append(
        {"kind": "ORDER", "a": "ghost", "b": "xfer"}))


def test_reject_contradicts_without_condition():
    def m(p):
        p["harmful_story"]["edges"].append({"kind": "CONTRADICTS", "a": "reset", "b": "benef"})
    assert any("incompatible_when" in e for e in _bad(m))


def test_reject_unversioned_provider_mapping():
    def m(p):
        p["provider_mappings"][0].pop("schema_version")
    assert _bad(m)


def test_reject_consequence_outside_vocab():
    assert _bad(lambda p: p["consequences"].__setitem__("HARD_POLICY_VIOLATION", "ALLOW"))


def test_reject_enforcement_without_approvals():
    def m(p):
        p["policy_identity"]["status"] = "ENFORCED"
    assert any("approval" in e or "publication" in e for e in _bad(m))


# ===========================================================================
# §7  compiler reproduces the FROZEN graph (no semantics change)
# ===========================================================================
def test_compiled_reference_reproduces_frozen_graph():
    b = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
    frozen = freeze.current_config()["story_graphs"]["ACCOUNT_TAKEOVER_TRANSFER@1.0.0"]
    assert compiler.graph_freeze_digest(b) == frozen
    assert b.graph.ref == ATO.ref


def test_compiled_graph_behaves_like_frozen_graph():
    b = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
    asm = [oe(F.CRED_RESET, "r", 1, account="a1"),
           oe(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
           oe(F.BENEFICIARY_ADD, "bn", 3, account="a1", beneficiary="bob")]
    prop = oe(F.TRANSFER, "x", 9, account="a1", beneficiary="bob", device="d1", amount="9000")
    r_compiled = evaluate_proposed_action(asm, prop, b.graph)
    r_frozen = evaluate_proposed_action(asm, prop, ATO)
    assert r_compiled.category == r_frozen.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


def test_ai_draft_cannot_self_publish():
    b = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
    assert b.publishable is False
    with pytest.raises(compiler.CompilerError):
        compiler.publish(b)
    approved = compiler.compile_pack(
        reference.ACCOUNT_TAKEOVER_PACK,
        approvals={"business_owner": "a", "control_owner": "b", "technical_owner": "c"})
    # still needs human_publication_confirmed
    assert approved.publishable is False


# ===========================================================================
# §6  business form == policy-as-code canonical pack
# ===========================================================================
def test_business_form_compiles_to_same_canonical_pack():
    form_pack = BF.compile_form(BF.ACCOUNT_TAKEOVER_BUSINESS_FORM)
    assert schema.validate_pack(form_pack) == []
    assert BF.canonical_pack_digest(form_pack) == \
        BF.canonical_pack_digest(reference.ACCOUNT_TAKEOVER_PACK)


# ===========================================================================
# §8  lifecycle + approvals
# ===========================================================================
def test_valid_lifecycle_transition():
    log = lifecycle.transition("DRAFT", "VALIDATING", actor="u", actor_roles=["control_owner"],
                               author="author", at="t")
    assert log.entries[0]["to"] == "VALIDATING"


def test_invalid_lifecycle_transition_rejected():
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.transition("DRAFT", "ENFORCED", actor="u", actor_roles=["risk"],
                             author="a", at="t")


def test_enforcement_requires_role():
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.transition("ENFORCEMENT_CANDIDATE", "ENFORCED", actor="u",
                             actor_roles=["control_owner"], author="a", at="t")


def test_author_cannot_publish_enforced():
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.transition("ENFORCEMENT_CANDIDATE", "ENFORCED", actor="same",
                             actor_roles=["risk"], author="same", at="t")


# ===========================================================================
# §9/§10  event + provider mappings
# ===========================================================================
def test_event_mapping_normalizes_and_rejects_missing_tenant():
    m = reference.ACCOUNT_TAKEOVER_PACK["event_mappings"][0]
    assert event_mapping.validate_event_mapping(m) == []
    ok = event_mapping.normalize_event(m, {"id": "e1", "tenant": "t1", "user": "u1",
                                           "account_id": "a1"})
    assert not ok["rejected"] and ok["normalized"]["entities"]["account"] == "a1"
    bad = event_mapping.normalize_event(m, {"id": "e1", "user": "u1"})
    assert bad["rejected"]


def test_provider_mapping_rejects_allow_availability():
    p = copy.deepcopy(reference.ACCOUNT_TAKEOVER_PACK["provider_mappings"][0])
    assert providers_mapping.validate_provider_mapping(p) == []
    p["availability_behavior"] = "ALLOW"
    assert providers_mapping.validate_provider_mapping(p)


# ===========================================================================
# §12  reference-pack scenario matrix (via the compiled graph)
# ===========================================================================
def _graph():
    return compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK).graph


def _asm():
    return [oe(F.CRED_RESET, "r", 1, account="a1"),
            oe(F.DEVICE_NEW, "d", 2, account="a1", device="d1"),
            oe(F.BENEFICIARY_ADD, "bn", 3, account="a1", beneficiary="bob")]


def _xfer(**over):
    e = {"account": "a1", "beneficiary": "bob", "device": "d1", "amount": "9000"}
    e.update(over)
    return oe(F.TRANSFER, "x", 9, **e)


@pytest.mark.parametrize("mut,expect_complete", [
    ({}, True),
    ({"account": "a2"}, False),
    ({"device": "evil"}, False),
    ({"beneficiary": "eve"}, False),
])
def test_scenario_entity_matrix(mut, expect_complete):
    g = _graph()
    r = evaluate_proposed_action(_asm(), _xfer(**mut), g)
    completes = r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert completes is expect_complete


def test_scenario_expired_and_partial_coverage():
    g = _graph()
    recov = Authorization("customer_account_recovery", True,
                          frozenset({"PASSWORD_RESET", "DEVICE_REGISTER"}), account="a1")
    r = evaluate_proposed_action(
        _asm(), _xfer(), g, legitimate_stories=list(
            compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK).legitimate_stories),
        authorizations=[recov])
    # recovery covers reset+device but NOT the transfer => still would-complete
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


def test_scenario_provider_unavailable_requests_context():
    g = _graph()
    r = evaluate_proposed_action(
        [oe(F.BENEFICIARY_ADD, "bn", 2, account="a1", beneficiary="bob")],
        _xfer(), g, facts={"provider_unavailable": True})
    assert r.category == V.ADDITIONAL_CONTEXT_REQUIRED
    assert r.context_status == V.CONTEXT_UNAVAILABLE


# ===========================================================================
# §13-§16  replay
# ===========================================================================
def test_replay_data_quality_and_findings():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    pack = reference.account_takeover_pack()
    dq = replay.data_quality_report(pack, fx["records"])
    assert dq["replay_ready"] is True and dq["records_rejected"] == 0
    res = replay.run_replay(pack, fx["records"])
    cats = {f["workflow_id"]: f["category"] for f in res["findings"]}
    assert cats["wf-takeover"] == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert cats["wf-recovery"] == V.VERIFIED_LEGITIMATE_STORY
    assert cats["wf-provider-down"] == V.ADDITIONAL_CONTEXT_REQUIRED
    cons = {f["workflow_id"]: f["consequence"] for f in res["findings"]}
    assert cons["wf-takeover"] == "WOULD_HOLD_FOR_REVIEW"


def test_replay_is_deterministic():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    pack = reference.account_takeover_pack()
    assert replay.run_replay(pack, fx["records"])["report_digest"] == \
        replay.run_replay(pack, fx["records"])["report_digest"]


def test_replay_enterprise_metrics_not_run():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    res = replay.run_replay(reference.account_takeover_pack(), fx["records"])
    ent = res["metrics"]["enterprise_metrics"]
    assert ent["unauthorized_action_detection_rate"] == "REQUIRES ENTERPRISE DATA"
    assert ent["runtime_per_event_ms"] == "NOT RUN"


def test_replay_data_quality_fails_visibly_on_bad_record():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    records = copy.deepcopy(fx["records"])
    records.append({"tenant": "enterprise-bank-a", "source_system": "x",
                    "source_event_id": "junk", "record_kind": "event",
                    "canonical_event_type": "UNKNOWN_TYPE", "event_time": "t",
                    "ingestion_time": "t", "source_ordering": 9, "workflow_id": "wf-x"})
    dq = replay.data_quality_report(reference.account_takeover_pack(), records)
    assert dq["unknown_event_types"] >= 1 and dq["replay_ready"] is False
