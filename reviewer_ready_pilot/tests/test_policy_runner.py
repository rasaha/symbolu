"""M8 tests - frozen policy runner (Phase 13)."""
from reviewer_ready_pilot import policy_runner as pr
from reviewer_ready_pilot import dataset


def test_runs_on_every_final_item_deterministically():
    final = dataset.load_final()
    first = {i["artifact_id"]: pr.run(i).as_dict() for i in final}
    second = {i["artifact_id"]: pr.run(i).as_dict() for i in final}
    assert first == second
    for r in first.values():
        assert r["final_obligation"]
        assert r["enforced"] is False


def test_native_actiongate_preserved_never_collapsed():
    final = dataset.load_final()
    seen = set()
    for i in final:
        r = pr.run(i)
        if r.action_present and r.native_actiongate_outcome:
            assert r.native_actiongate_outcome in pr.NATIVE_ACTIONGATE_OUTCOMES
            assert r.native_actiongate_outcome not in ("allow", "deny", "ALLOW/DENY")
            seen.add(r.native_actiongate_outcome)
    # action-bearing traps exist, so at least one native outcome should be produced
    assert seen


def test_replay_signature_present():
    r = pr.run(dataset.load_final()[0])
    assert r.replay_signature
    assert r.policy_version


def test_reveal_view_has_no_enforcement_toggle():
    r = pr.run(dataset.load_final()[0])
    v = pr.reveal_view(r)
    assert v["enforced"] is False
    assert "obligation" in v and "native_actiongate_outcome" in v


def test_high_risk_never_e0():
    for i in dataset.load_final():
        if i.get("risk_tier") in ("high", "critical"):
            r = pr.run(i)
            assert not r.final_obligation.startswith("E0"), (i["artifact_id"], r.final_obligation)
