"""Regression tests proving audit findings F1-F7 are closed. Stdlib only; fixtures 883000-883004 only."""
from __future__ import annotations

from .. import (base_capability as bc, gates as G, generator as gen, manifest as MAN,
                metrics as M, output, replay as RP, shortcuts as SC, verdict as V)
from ..execution import ExecutionNotAuthorized
from ..schema_ext import ReasoningOutput

FIXT = 883000
RESERVED = (8100, 8101, 8102, 8103, 81600, 81601, 81602, 81603, 81604)


# ---- F1: seed authorization at every scientific primitive ----
def test_F1_generate_episode_fails_closed():
    for s in (8100, 8101, 81600):
        try:
            gen.generate_episode("R9", s, 0); assert False, s
        except ExecutionNotAuthorized:
            pass

def test_F1_generate_split_fails_closed():
    for s in (8100, 81600):
        try:
            gen.generate_split("R1", s, 2); assert False, s
        except ExecutionNotAuthorized:
            pass

def test_F1_p0_primitives_fail_closed():
    for s in (8100, 8103, 81604):
        try:
            bc.generate_p0_episode("B1", s, 0); assert False
        except ExecutionNotAuthorized:
            pass
        try:
            bc.generate_p0("B1", s, 2); assert False
        except ExecutionNotAuthorized:
            pass

def test_F1_replay_fails_closed():
    for s in (8100, 81600):
        try:
            RP.replay_matches("R1", s, 0); assert False
        except ExecutionNotAuthorized:
            pass

def test_F1_fixtures_still_run():
    assert gen.generate_episode("R9", FIXT, 0) is not None
    assert len(bc.generate_p0("B1", FIXT, 2)) == 2

def test_F1_no_bypass_flag():
    # a bogus token cannot authorize a reserved seed (registry empty)
    try:
        gen.generate_episode("R9", 81600, 0, authorization_token="anything"); assert False
    except ExecutionNotAuthorized:
        pass


# ---- F2: R9 full-chain correctness metric + gate ----
def _r9_ctx():
    return gen.generate_episode("R9", FIXT, 0)

def test_F2_full_chain_all_correct():
    ctx = _r9_ctx()
    m = M.compute([(ctx, output.serialize_output(ctx.authoritative_output))])
    assert m["r9_full_chain_correct"] == 1.0

def _mutate(g: ReasoningOutput, **kw):
    return ReasoningOutput(kw.get("answer", g.answer),
                           kw.get("reasoning_path", g.reasoning_path),
                           kw.get("evidence_ids", g.evidence_ids),
                           kw.get("status", g.status))

def test_F2_full_chain_conjunction():
    ctx = _r9_ctx(); g = ctx.authoritative_output
    # wrong path (drop last node) with right answer -> 0
    bad_path = _mutate(g, reasoning_path=g.reasoning_path[:-1])
    assert M.compute([(ctx, output.serialize_output(bad_path))])["r9_full_chain_correct"] == 0.0
    # wrong answer, right path -> 0
    bad_ans = _mutate(g, answer="NO_ACTION")
    assert M.compute([(ctx, output.serialize_output(bad_ans))])["r9_full_chain_correct"] == 0.0
    # wrong latest event node (swap an Event node) -> 0
    swapped = tuple(("Event:ZZZ999" if n.startswith("Event:") else n) for n in g.reasoning_path)
    bad_evt = _mutate(g, reasoning_path=swapped)
    assert M.compute([(ctx, output.serialize_output(bad_evt))])["r9_full_chain_correct"] == 0.0
    # wrong policy node -> 0
    swapped_p = tuple(("Policy:ZZZ999" if n.startswith("Policy:") else n) for n in g.reasoning_path)
    bad_pol = _mutate(g, reasoning_path=swapped_p)
    assert M.compute([(ctx, output.serialize_output(bad_pol))])["r9_full_chain_correct"] == 0.0

def test_F2_gate_enforced_in_verdict():
    gates = G.evaluate_gates({"r9_full_chain_correct": 0.50})["gates"]  # below 0.60
    r = V.decide(protocol_valid=True, base_capability_established=True, shortcut_detected=False,
                 resource_ok=True, gates=gates, discovery_ok=True, composite_ok=True)
    assert r["primary_verdict"] == "POLICY_REASONING_FAILED"
    # passing full-chain does not by itself trip the failure
    gates2 = G.evaluate_gates({"r9_full_chain_correct": 0.65})["gates"]
    assert gates2["R9_full_chain_correct"]["pass"] is True


# ---- F3: latest-event effect over global-most-recent ----
def test_F3_effect_gate():
    temporal = gen.generate_split("R5", FIXT, 12)
    eff = SC.latest_event_effect(temporal, model_latest_event_accuracy=1.0)
    assert "global_most_recent_baseline" in eff and eff["required_effect"] == 0.20
    # gate present in evaluate_gates when baseline supplied
    gres = G.evaluate_gates({"latest_event": 1.0}, latest_event_baseline=eff["global_most_recent_baseline"])
    assert "latest_event_effect_over_global_most_recent" in gres["gates"]

def test_F3_effect_boundary_fail():
    # model barely above baseline (< 0.20 effect) must fail the effect gate
    g = G.evaluate_gates({"latest_event": 0.90}, latest_event_baseline=0.75)["gates"]
    assert g["latest_event_effect_over_global_most_recent"]["pass"] is False
    g2 = G.evaluate_gates({"latest_event": 0.96}, latest_event_baseline=0.75)["gates"]
    assert g2["latest_event_effect_over_global_most_recent"]["pass"] is True


# ---- F4: full structure-blind suite + margin rule ----
def test_F4_suite_runs_deterministically():
    ctxs = gen.generate_split("R9", FIXT, 10)
    a = SC.run_suite(ctxs, model_metric=1.0)
    b = SC.run_suite(ctxs, model_metric=1.0)
    assert a["baselines"] == b["baselines"]                       # deterministic
    assert set(a["baselines"].keys()) == set(SC.SUITE)
    assert not a["shortcut_detected"]                            # perfect model beats blind baselines

def test_F4_margin_triggers_shortcut():
    ctxs = gen.generate_split("R9", FIXT, 10)
    # a weak "model" tied with blind baselines must flag shortcut
    weak = max(SC.run_suite(ctxs, 0.0)["baselines"].values())
    flagged = SC.run_suite(ctxs, model_metric=weak + 0.05)       # within 0.10 margin
    assert flagged["shortcut_detected"]


# ---- F5: R10 vs R11 distinction ----
def test_F5_r10_r11_distinct():
    r10 = gen.generate_episode("R10", FIXT, 0)
    r11 = gen.generate_episode("R11", FIXT, 0)
    from ..serializer import serialize_input
    assert serialize_input(r10) != serialize_input(r11)          # not byte-identical
    # both unanswerable
    assert r10.authoritative_output.status == "INSUFFICIENT_EVIDENCE"
    assert r11.authoritative_output.status == "INSUFFICIENT_EVIDENCE"
    # R10: no path from the root at all
    assert all(rel.source_entity_id != r10.query.root_entity_id for rel in r10.relations)
    # R11: the root DOES originate a relation (path exists) but conclusion unsupported
    assert any(rel.source_entity_id == r11.query.root_entity_id for rel in r11.relations)

def test_F5_r10_tenant_pure():
    for ctx in gen.generate_split("R10", FIXT, 6):
        assert all(r.tenant_id == ctx.tenant_id
                   for r in (*ctx.entities, *ctx.relations, *ctx.events, *ctx.policies))


# ---- F6: length-shortcut robustness ----
def test_F6_length_control():
    mixed = (gen.generate_split("R9", FIXT, 12) + gen.generate_split("R10", FIXT, 12)
             + gen.generate_split("R11", FIXT, 12))
    r = SC.length_shortcut_control(mixed)
    assert r["applicable"]
    assert "length_only_status_accuracy" in r
    assert r["length_preserving"]                                # ranges overlap
    assert not r["length_is_trivial_separator"]                 # length alone cannot cleanly separate


# ---- F7: manifest/replay binding drift detection ----
def test_F7_binding_detects_drift():
    b = MAN.build_replay_binding(seed=FIXT, phase="R1-R12", checkpoint_digest="ck",
                                 prediction_digest="pr", metric_digest="me", verdict_digest="ve")
    assert MAN.verify_replay_binding(b, dict(b))["matches"]
    for fld in ("config_digest", "tokenizer_vocab_digest", "checkpoint_digest",
                "prediction_digest", "metric_digest", "verdict_digest"):
        drift = dict(b); drift[fld] = "CHANGED"
        res = MAN.verify_replay_binding(b, drift)
        assert not res["matches"] and fld in res["mismatched_fields"]

def test_F7_manifest_has_digests():
    man = MAN.build_manifest()
    assert man["config_digest"] and man["tokenizer_vocab_digest"]
    assert man["schema_serializer_version"] == MAN.SCHEMA_SERIALIZER_VERSION


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
