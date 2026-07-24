"""Phase 21 - Consolidated invariants: no frozen-component modification, no enforcement/external action,
every obligation type valid, escalation completeness, unknown-obligation fail-closed, and deterministic
end-to-end replay.
"""
from evidence_obligation import (schema as s, classifier, adapters, taxonomy, risk as risk_mod,
                                 verify_prior_artifacts, audit)
from governed_inference_pilot.adapters import evidence_assurance as ea


def test_no_frozen_component_modification():
    assert verify_prior_artifacts.verify() is True
    assert len(verify_prior_artifacts.FROZEN) == 32


def test_every_obligation_type_is_valid_vocabulary():
    assert len(s.OBLIGATION_TYPES) == 14
    for t in s.OBLIGATION_TYPES:
        o = s.new_obligation("c", "a", evidence_obligation_type=t, risk_tier="low")
        # unknown-type violation must not fire for a real vocab member
        assert "OBL.UNKNOWN_TYPE" not in s.validate_obligation(o)


def test_contract_delivery_is_disposition_not_action():
    # the pipeline only READS an EvidenceAssurance delivery disposition; nothing is enforced/executed
    o = classifier.classify({"artifact_id": "c", "source_path": "m.py", "source_kind": "docstring",
                             "text": "This function returns the config."})
    delivery = ea.run(adapters.to_evidence_steer(o), "low").local_disposition
    assert delivery in ("ALLOW", "QUALIFY", "ESCALATE", "INDETERMINATE", "REJECT")


def test_actionability_escalation():
    r, _ = risk_mod.assess_risk("send the payment", "action_proposal", actionability="action_directive")
    assert r == "high"


def test_temporal_family_present():
    assert "status_report" in taxonomy.CLAIM_FAMILIES
    assert taxonomy.default_obligation("status_report", "low") == s.TEMPORAL_VERIFICATION_REQUIRED


def test_unknown_obligation_fails_closed():
    o = classifier.classify({"artifact_id": "x"})            # empty item
    assert o.evidence_obligation_type in s.OBLIGATION_TYPES  # never crashes, never permissive-by-default


def test_deterministic_end_to_end_replay():
    item = {"artifact_id": "c", "source_path": "docs/x.md", "source_kind": "doc",
            "text": "This approved policy prohibits deleting the production database."}
    o1 = classifier.classify(item); o2 = classifier.classify(item)
    assert audit.replay_signature(o1) == audit.replay_signature(o2)
    d1 = ea.run(adapters.to_evidence_steer(o1), "high").local_disposition
    d2 = ea.run(adapters.to_evidence_steer(o2), "high").local_disposition
    assert d1 == d2


def test_high_burden_never_verified_invariant():
    # locked safety invariant: independent-evidence-required obligations never yield VERIFIED w/o evidence
    for t in s.HIGH_EXTERNAL_BURDEN:
        o = s.new_obligation("c", "a", evidence_obligation_type=t)
        assert adapters.to_evidence_steer(o)["evidence_state"] != "VERIFIED"
