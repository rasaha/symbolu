"""Imperfect-benign context taxonomy (§11,§12) + evaluation-integrity controls
(§4,§5). Verification phase."""

from __future__ import annotations

import pytest

from composite_threat_detector import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO, Authorization,
    ObservedEvent, evaluate_proposed_action, storyverdict,
)
from composite_threat_detector import financial as F

V = storyverdict


def oe(frag, eid, pos, **ent):
    return ObservedEvent(frag, eid, pos, None, "u1", dict(ent))


def _benef_xfer():
    return ([oe(F.BENEFICIARY_ADD, "benef", 2, account="a1", beneficiary="bob")],
            oe(F.TRANSFER, "xfer", 9, account="a1", beneficiary="bob", device="d1",
               amount="9000"))


def _full_assembly():
    return [oe(F.CRED_RESET, "reset", 1, account="a1"),
            oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
            oe(F.BENEFICIARY_ADD, "benef", 3, account="a1", beneficiary="bob")]


def _transfer():
    return oe(F.TRANSFER, "xfer", 9, account="a1", beneficiary="bob", device="d1",
              amount="9000")


# ===========================================================================
# §12  context-status taxonomy
# ===========================================================================
@pytest.mark.parametrize("fact,expect", [
    ("provider_unavailable", V.CONTEXT_UNAVAILABLE),
    ("context_stale", V.CONTEXT_STALE),
    ("context_conflicting", V.CONTEXT_CONFLICTING),
])
def test_context_gap_statuses(fact, expect):
    asm, prop = _benef_xfer()
    r = evaluate_proposed_action(asm, prop, ATO, facts={fact: True})
    assert r.context_status == expect
    # a partial material story with a context gap requests context (advisory)
    assert r.category == V.ADDITIONAL_CONTEXT_REQUIRED
    assert r.signal == "OBSERVE"


def test_context_not_found_when_no_authorization():
    asm, prop = _benef_xfer()
    r = evaluate_proposed_action(asm, prop, ATO)
    assert r.context_status == V.CONTEXT_NOT_FOUND


def test_context_verified_and_partial():
    recov = Authorization("customer_account_recovery", True,
                          frozenset({"PASSWORD_RESET", "DEVICE_REGISTER"}), account="a1")
    # reset+device only, fully covered by recovery => VERIFIED
    r = evaluate_proposed_action(
        [oe(F.CRED_RESET, "reset", 1, account="a1")],
        oe(F.DEVICE_NEW, "device", 2, account="a1", device="d1"),
        ATO, legitimate_stories=[ACCOUNT_RECOVERY_STORY], authorizations=[recov])
    assert r.context_status == V.CONTEXT_VERIFIED_LEGITIMATE


def test_completion_is_harmful_positive_even_without_context():
    r = evaluate_proposed_action(_full_assembly(), _transfer(), ATO)
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.context_status == V.CONTEXT_HARMFUL_POSITIVE


# ===========================================================================
# missing context must NOT strengthen the harmful reading
# ===========================================================================
@pytest.mark.parametrize("fact", ["provider_unavailable", "context_stale",
                                  "context_conflicting"])
def test_missing_context_does_not_strengthen_harmful(fact):
    asm, prop = _benef_xfer()
    with_gap = evaluate_proposed_action(asm, prop, ATO, facts={fact: True})
    clean = evaluate_proposed_action(asm, prop, ATO, facts={})
    # the harmful structural vector is identical; only the context axis changes.
    assert with_gap.structural_vector == clean.structural_vector
    assert with_gap.risk_after["harmful_score"] == clean.risk_after["harmful_score"]
    assert with_gap.category != V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert with_gap.category != V.HARD_POLICY_VIOLATION


def test_unavailable_context_on_complete_story_still_escalates_but_labels_context():
    # a positively-proven completion is not weakened by missing context, and missing
    # context is not what caused the escalation (the structure did).
    r = evaluate_proposed_action(_full_assembly(), _transfer(), ATO,
                                 facts={"provider_unavailable": True})
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.context_status == V.CONTEXT_UNAVAILABLE   # honest context label


# ===========================================================================
# §4/§5  evaluation-integrity controls
# ===========================================================================
def test_holdout_is_disjoint_from_dev_corpus():
    from evaluation import final_eval
    assert final_eval.dev_corpus_excludes_holdout() is True


def test_holdout_hash_computable_without_evaluation():
    from evaluation import story_corpus_v2 as S
    h = S.holdout_hashes()
    assert h["generator_version"] == S.GENERATOR_VERSION
    assert h["holdout_id_hash"].startswith("sha-256:")


def test_official_final_refuses_development_mode(tmp_path):
    from evaluation import freeze, final_eval
    fz = freeze.build_freeze("t", profile="final")
    with pytest.raises(final_eval.FinalEvalError):
        final_eval.run_official_final(fz, commit="t", now="t",
                                      record_path=str(tmp_path / "r.json"),
                                      development_mode=True)


def test_official_final_refuses_drift(tmp_path):
    from evaluation import freeze, final_eval
    fz = dict(freeze.build_freeze("t", profile="final"))
    fz["story_corpus_generator"] = "ctd.storycorpus.gen/9.9.9"
    with pytest.raises(freeze.FreezeViolation):
        final_eval.run_official_final(fz, commit="t", now="t",
                                      record_path=str(tmp_path / "r.json"))


def test_official_final_writes_immutable_record_and_refuses_second(tmp_path):
    from evaluation import freeze, final_eval
    fz = freeze.build_freeze("t", profile="final")
    rp = str(tmp_path / "rec.json")
    res = final_eval.run_official_final(fz, commit="t", now="2026-08-01T00:00:00Z",
                                        record_path=rp)
    assert res["gates"]["all_pass"] is True
    assert res["record"]["generation"] == 1
    with pytest.raises(final_eval.FinalEvalError):
        final_eval.run_official_final(fz, commit="t", now="2026-08-01T00:00:00Z",
                                      record_path=rp)   # second run refused


def test_new_generation_allowed_explicitly(tmp_path):
    from evaluation import freeze, final_eval
    fz = freeze.build_freeze("t", profile="final")
    rp = str(tmp_path / "rec.json")
    final_eval.run_official_final(fz, commit="t", now="t1", record_path=rp)
    res2 = final_eval.run_official_final(fz, commit="t", now="t2", record_path=rp,
                                         allow_new_generation=True)
    assert res2["record"]["generation"] == 2


# ===========================================================================
# §2  all historical runs preserved
# ===========================================================================
def test_all_three_runs_preserved():
    from evaluation.prior_runs import RUN_1, RUN_2, RUN_3, PRIOR_RUNS
    assert [r["run_id"] for r in PRIOR_RUNS] == \
        ["run-1-ato-partial-match-defect", "run-2-partial-match-correction",
         "run-3-verification-and-proof-semantics"]
    assert RUN_1["commit"] == "78911a9f" and RUN_1["status"] == "SUPERSEDED"
    assert RUN_2["commit"] == "019e1f0d"
    assert "EXPOSED" in RUN_2["verification_finding"]
    assert RUN_3["verdict"] == "CONTINUE — evaluation integrity and proof semantics passed"


def test_holdout_final_gates_pass_recorded():
    from evaluation.prior_runs import RUN_3
    m = RUN_3["metrics"]
    assert m["encoded_completion_detection_rate"] == 1.0
    assert m["benign_false_completion_rate"] == 0.0
    assert m["incorrect_harmful_strengthening_from_missing_context"] == 0
