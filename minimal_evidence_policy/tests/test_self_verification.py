"""Phase 4 tests: all self-verification traps rejected; 0 escapes."""
from minimal_evidence_policy import self_verification as sv
from minimal_evidence_policy import schema as s


def test_no_self_verification_escapes():
    m = sv.validate()
    assert m["self_verification_escape"] == 0
    assert m["all_rejected"] is True


def test_all_traps_raised_to_independent_evidence():
    for r in sv.validate()["rows"]:
        assert s.RANK[r["final"]] >= s.RANK[s.E3], r["case"]
