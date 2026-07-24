"""Phase 9 tests: the reference classifier assigns valid obligations, is fail-closed, never makes an
unsafe assignment on the adversarial set, and is deterministic.
"""
from evidence_obligation import classifier, schema as s, audit, metrics, dataset as d


def _item(text, **kw):
    base = dict(artifact_id="c1", source_path="pkg/mod.py", source_kind="docstring", text=text)
    base.update(kw)
    return base


def test_valid_obligation_and_no_structural_violation():
    o = classifier.classify(_item("This function returns the parsed config from the path."))
    assert o.evidence_obligation_type in s.OBLIGATION_TYPES
    assert s.validate_obligation(o) == [] or o.evidence_obligation_type == s.HUMAN_REVIEW_REQUIRED


def test_high_risk_never_no_gate():
    o = classifier.classify(_item("This medication completely cures the patient.",
                                  source_path="docs/x.md", source_kind="doc"))
    assert o.evidence_obligation_type != s.NO_FACTUAL_EVIDENCE_GATE


def test_action_gets_policy_authority_floor():
    o = classifier.classify(_item("Deploy the change and grant the user admin access.",
                                  claim_actionability="action_directive"))
    assert not o.is_low_external_burden()


def test_self_referential_source_is_escalated():
    # a generated doc making a current-fact claim cannot self-verify -> not a low artifact-dependent burden
    o = classifier.classify(_item("Currently the production system has 99.99% uptime.",
                                  source_path="docs/readme.md", source_kind="doc"))
    assert o.evidence_obligation_type not in (s.IMPLEMENTATION_EVIDENCE_SUFFICIENT,
                                              s.NO_FACTUAL_EVIDENCE_GATE)


def test_classifier_never_raises_fail_closed():
    o = classifier.classify({"artifact_id": "x"})            # missing fields
    assert o.evidence_obligation_type in s.OBLIGATION_TYPES


def test_zero_unsafe_on_adversarial_set():
    sc = metrics.score_obligations(d.load_partition("ADVERSARIAL_OBLIGATION"), classifier.classify)
    assert sc["unsafe_assignments"] == 0


def test_replay_deterministic():
    it = _item("This module documents the deployment runbook and rollback steps.")
    assert audit.replay_signature(classifier.classify(it)) == \
        audit.replay_signature(classifier.classify(it))
