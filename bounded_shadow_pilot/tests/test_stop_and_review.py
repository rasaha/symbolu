"""Phase 8-10 tests: stop conditions fire correctly (positive + negative), review routing works, and
the dry run keeps a clean slice below every stop condition. Read-only; non-enforcing; deterministic.
"""
from bounded_shadow_pilot import stop_conditions as sc
from bounded_shadow_pilot import dry_run
from bounded_shadow_pilot.orchestrator_wrapper import ExtendedAudit, replay_signature
from customer_shadow_readiness import human_review, security, killswitch


def _rec(**over):
    base = dict(artifact_id="nat-x", use_case="u", source_kind="doc", source_path="p",
                final_shadow_disposition="WOULD_QUALIFY", stage_dispositions=[], reason_codes=[],
                replay_signature="sig", human_review_state="not_required", gt_expected_class="ALLOW")
    base.update(over)
    return ExtendedAudit(**base)


# ---- stop conditions -----------------------------------------------------------------------------

def test_clean_batch_does_not_stop():
    recs = [_rec(artifact_id=f"a{i}") for i in range(5)]
    text = {r.artifact_id: "benign documentation about deployment" for r in recs}
    res = sc.evaluate_stops(recs, text, replay_signature)
    assert res["should_stop"] is False


def test_unsafe_disagreement_stops():
    recs = [_rec(gt_expected_class="REVIEW", final_shadow_disposition="WOULD_ALLOW")]
    text = {"nat-x": "benign"}
    res = sc.evaluate_stops(recs, text, replay_signature)
    assert res["should_stop"] is True
    c1 = next(c for c in res["conditions"] if c["name"] == "unsafe_disagreement")
    assert c1["passed"] is False


def test_privacy_leak_stops():
    recs = [_rec()]
    text = {"nat-x": "contact ssn 123-45-6789"}
    res = sc.evaluate_stops(recs, text, replay_signature)
    c5 = next(c for c in res["conditions"] if c["name"] == "privacy_no_pii_reached_runtime")
    assert c5["passed"] is False and res["should_stop"] is True


def test_missing_replay_signature_stops():
    recs = [_rec(replay_signature="")]
    text = {"nat-x": "benign"}
    res = sc.evaluate_stops(recs, text, replay_signature)
    c4 = next(c for c in res["conditions"] if c["name"] == "audit_replay")
    assert c4["passed"] is False


# ---- review routing ------------------------------------------------------------------------------

def test_review_routing_enqueues_and_scopes():
    killswitch.restore_pilot()
    q = human_review.ReviewQueue()
    esc = _rec(final_shadow_disposition="WOULD_ESCALATE", reason_codes=["EA.CONFLICTED"])
    iid = q.maybe_enqueue("pilot-internal", esc)
    assert iid is not None                                  # escalation enqueued
    # cross-tenant reviewer cannot see the pilot queue
    import pytest
    with pytest.raises(PermissionError):
        q.queue_for(security.issue_token("tok-globex-analyst"), "pilot-internal")


# ---- dry run -------------------------------------------------------------------------------------

def test_dry_run_clean_slice_no_stop():
    res = dry_run.run(25)
    assert res["all_non_enforcing"] is True
    assert res["review_cross_tenant_blocked"] is True
    assert res["clean_slice_no_stop"] is True
    assert res["stop_conditions"]["should_stop"] is False
