"""Phase 2-3 tests: obligation schema fail-closed validation and taxonomy defaults/escalation."""
from evidence_obligation import schema as s
from evidence_obligation import taxonomy as t


def test_fourteen_obligation_types():
    assert len(s.OBLIGATION_TYPES) == 14
    assert s.NO_FACTUAL_EVIDENCE_GATE in s.OBLIGATION_TYPES


def test_no_gate_on_high_risk_is_structural_error():
    o = s.new_obligation("c", "a", evidence_obligation_type=s.NO_FACTUAL_EVIDENCE_GATE, risk_tier="high")
    assert "OBL.NO_GATE_ON_HIGH_RISK" in s.validate_obligation(o)


def test_low_burden_on_action_is_structural_error():
    o = s.new_obligation("c", "a", evidence_obligation_type=s.CONTEXTUAL_SUPPORT_SUFFICIENT,
                         claim_actionability="action_directive")
    assert "OBL.LOW_BURDEN_ON_ACTION" in s.validate_obligation(o)


def test_valid_obligation_has_no_violations():
    o = s.new_obligation("c", "a", evidence_obligation_type=s.IMPLEMENTATION_EVIDENCE_SUFFICIENT,
                         risk_tier="low")
    assert s.validate_obligation(o) == []


def test_taxonomy_unknown_family_fails_closed():
    assert t.default_obligation("no_such_family", "low") == s.QUALIFY_BY_DEFAULT


def test_risk_never_lowers_obligation():
    # disguise defense: preference/opinion/hypothetical never reach no-gate at high risk
    for fam in ("user_preference", "subjective_opinion", "hypothetical"):
        assert t.default_obligation(fam, "low") == s.NO_FACTUAL_EVIDENCE_GATE
        assert t.default_obligation(fam, "high") != s.NO_FACTUAL_EVIDENCE_GATE


def test_hard_floor_families_never_shortcut():
    for fam in ("medical", "financial"):
        assert t.default_obligation(fam, "low") == s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED
        assert t.default_obligation(fam, "high") == s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED
