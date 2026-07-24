"""M4 tests - reviewer qualification scorer (Phase 7).

The scorer must GRADE supplied responses and never synthesize them. Mock responses below are explicitly
flagged is_mock=True and would be excluded from any real qualification record.
"""
from reviewer_ready_pilot import dataset, qualification as q


def _quiz():
    return q.build_quiz(dataset.load_training())


def _perfect_responses(quiz):
    """A safe, competent set of responses derived from the revealed training labels + trap types.
    This models what a strong candidate WOULD submit; it is mock input to the scorer, not scorer output."""
    resp = []
    risk_floor = {"E0": "low", "E1": "low", "E2": "medium", "E3": "high", "E4": "critical", "ER": "unknown"}
    for it in quiz:
        gold = it.get("gold_obligation")
        trap = it.get("trap_type")
        is_action = (it.get("claim_actionability") in ("action_directive", "action_recommendation")
                     or it.get("claim_family") == "action_proposal")
        resp.append({
            "artifact_id": it["artifact_id"],
            "obligation": gold,
            "risk_floor": it.get("risk_tier") or it.get("risk_floor") or "unknown",
            "trap_detected": trap if trap else "none",
            "action_requires_approval": bool(is_action),
        })
    return resp


def test_scorer_requires_responses():
    quiz = _quiz()
    try:
        q.score_candidate("REV-MOCK", quiz, None, is_mock=True)
        assert False, "scorer must reject None responses"
    except ValueError:
        pass


def test_strong_candidate_qualifies():
    quiz = _quiz()
    res = q.score_candidate("REV-MOCK-A", quiz, _perfect_responses(quiz), is_mock=True)
    assert res.is_mock is True
    assert res.qualified is True, [c.detail for c in res.criteria if not c.passed]


def test_high_risk_downgrade_fails():
    quiz = _quiz()
    resp = _perfect_responses(quiz)
    # force an unsafe downgrade on a high-risk trap item
    for r, it in zip(resp, quiz):
        if (it.get("risk_tier") in ("high", "critical")):
            r["obligation"] = "E0"
            break
    res = q.score_candidate("REV-MOCK-B", quiz, resp, is_mock=True)
    assert res.qualified is False
    assert not next(c for c in res.criteria if c.key == "C1").passed


def test_missing_selfverification_level_fails():
    quiz = _quiz()
    resp = _perfect_responses(quiz)
    for r, it in zip(resp, quiz):
        if it.get("trap_type") in ("self_verification", "circular_evidence"):
            r["obligation"] = "E1"
    res = q.score_candidate("REV-MOCK-C", quiz, resp, is_mock=True)
    assert res.qualified is False
    assert not next(c for c in res.criteria if c.key == "C4").passed


def test_blind_quiz_strips_labels():
    quiz = _quiz()
    blind = q.blind_quiz(quiz)
    for it in blind:
        assert "gold_obligation" not in it
        assert "gold_explanation" not in it


def test_result_is_serializable():
    quiz = _quiz()
    res = q.score_candidate("REV-MOCK-D", quiz, _perfect_responses(quiz), is_mock=True)
    d = res.as_dict()
    assert d["is_mock"] is True and "criteria" in d and d["n_items"] > 0
