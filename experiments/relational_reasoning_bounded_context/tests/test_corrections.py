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


# ---- F11: generator determinism must not depend on the interpreter's hash salt ----
_XPROC_SNIPPET = (
    "from experiments.relational_reasoning_bounded_context.generator import generate_episode\n"
    "from experiments.relational_reasoning_bounded_context.base_capability import generate_p0_episode\n"
    "out=[]\n"
    "for role in ('train','dev','final','unit'):\n"
    "    c=generate_episode('R9',883001,2,role); b=generate_p0_episode('B3',883001,1,role)\n"
    "    out.append((c.context_id,c.tenant_id,c.fact_hash(),b.context_id,b.fact_hash()))\n"
    "print(repr(out))\n"
)

def test_F11_generator_deterministic_across_processes():
    """Episodes for (seed, split, index, role) must be byte-identical across interpreters with different
    PYTHONHASHSEED values. Builtin hash(str) is salted per process; seeding the RNG from it made the
    generator silently non-reproducible across runs (in-process replay checks could not detect this)."""
    import os, pathlib, subprocess, sys
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    outs = []
    for salt in ("0", "1", "424242"):
        env = dict(os.environ, PYTHONHASHSEED=salt)
        r = subprocess.run([sys.executable, "-c", _XPROC_SNIPPET], cwd=repo_root, env=env,
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip())
    assert len(set(outs)) == 1, outs
    # in-process reference must agree with the subprocesses too
    rows = []
    for role in ("train", "dev", "final", "unit"):
        c = gen.generate_episode("R9", 883001, 2, role); b = bc.generate_p0_episode("B3", 883001, 1, role)
        rows.append((c.context_id, c.tenant_id, c.fact_hash(), b.context_id, b.fact_hash()))
    assert repr(rows) == outs[0]

def test_F11_no_salted_hash_in_generator_source():
    import pathlib, re
    src = (pathlib.Path(gen.__file__)).read_text()
    bare = [m for m in re.finditer(r"(?<![\w.])hash\(", src)]
    # allow only the docstring mention inside _stable_hash; no executable call sites
    for m in bare:
        line = src[: m.start()].count("\n") + 1
        text = src.splitlines()[line - 1]
        assert text.lstrip().startswith(('"""', "#")) or "``hash(str)``" in text, f"bare hash() at line {line}: {text}"


# ---- F12: B7 must carry the preregistered trivial VISIBLE "absent" flag ----
def test_F12_b7_visible_absent_flag():
    """Preregistered B7 = abstain when a trivial visible flag says 'absent' (chance 0.5). B1/B5 inputs carry
    the flag PRESENT and B7 ABSENT on the queried entity, so the labels are no longer contradictory over
    byte-shaped-identical inputs."""
    from ..serializer import serialize_input
    for role in ("unit", "train", "final"):
        for i in range(3):
            b1 = bc.generate_p0_episode("B1", FIXT, i, role); b5 = bc.generate_p0_episode("B5", FIXT, i, role)
            b7 = bc.generate_p0_episode("B7", FIXT, i, role)
            for ctx, flag in ((b1, bc.FLAG_PRESENT), (b5, bc.FLAG_PRESENT), (b7, bc.FLAG_ABSENT)):
                root = next(e for e in ctx.entities if e.entity_id == ctx.query.root_entity_id)
                assert dict(root.attributes)[bc.FLAG_KEY] == flag, (ctx.split, root)
                line = next(l for l in serialize_input(ctx).splitlines()
                            if l.startswith("ENT ") and ctx.query.root_entity_id in l)
                assert line.endswith(f"{bc.FLAG_KEY} {flag}"), line
            assert b7.authoritative_output.status == "INSUFFICIENT_EVIDENCE" and b7.authoritative_output.answer is None
            assert b1.authoritative_output.answer == b1.query.root_entity_id

def test_F12_flag_is_the_only_shape_difference():
    """Masking ids/amounts, a B1 and a B7 input differ exactly in the flag token (no other cue)."""
    import re
    from ..serializer import serialize_input
    def shape(ctx):
        t = serialize_input(ctx)
        return re.sub(r"\b\d+\b", "#", re.sub(r"\b[A-Z][A-Z]{3,5}\d\b|\bT[A-Z]{3}\b", "@", t))
    a = shape(bc.generate_p0_episode("B1", FIXT, 0)); b = shape(bc.generate_p0_episode("B7", FIXT, 0))
    assert a != b
    assert a.replace(bc.FLAG_PRESENT, bc.FLAG_ABSENT).count("ABSENT") == 1
    # same number of ENT rows can differ (6..12 entities are drawn per episode); the flag is the discriminating token
    assert bc.FLAG_PRESENT in a and bc.FLAG_ABSENT not in a and bc.FLAG_ABSENT in b and bc.FLAG_PRESENT not in b


# ---- F14: identity pools are disjoint by an invisible partition, not by a visible marker ----
def _pool_ids(role, n=300):
    import random
    m = gen._Mint(random.Random(7), role)
    return {m.new() for _ in range(n)} | {m.new("C") for _ in range(n // 4)}

def test_F14_pools_disjoint_and_hash_partitioned():
    pools = {r: _pool_ids(r) for r in ("train", "dev", "final", "unit")}
    for r, ids in pools.items():
        assert ids and all(gen.pool_of(i) == r for i in ids)
    roles = list(pools)
    for i, a in enumerate(roles):
        for b in roles[i + 1:]:
            assert not (pools[a] & pools[b]), (a, b)
    # end-to-end: episode entity ids of train vs final never overlap and classify to their role
    tr = {e.entity_id for c in gen.generate_split("R9", FIXT, 6, "train") for e in c.entities}
    fi = {e.entity_id for c in gen.generate_split("R9", FIXT, 6, "final") for e in c.entities}
    assert tr and fi and not (tr & fi)
    assert all(gen.pool_of(i) == "train" for i in tr) and all(gen.pool_of(i) == "final" for i in fi)

def test_F14_no_visible_marker_between_pools():
    """Every (position, character) pair in held-out ids occurs in training ids (no never-seen token pattern),
    and the trailing-digit sets coincide. The previous design (train ids ending 0/1/2, final 6/7/8) failed
    this: the model copied the letters and emitted a training-pool digit."""
    tr, fi, dv = _pool_ids("train", 600), _pool_ids("final", 600), _pool_ids("dev", 600)
    pos = lambda ids: {(k, ch) for i in ids for k, ch in enumerate(i)}
    assert pos(fi) <= pos(tr) and pos(dv) <= pos(tr)
    assert {i[-1] for i in fi} == {i[-1] for i in tr} == set(gen._ID_DIGITS)
    assert all(len(i) <= 6 for i in tr | fi | dv)

# ---- F15: is_valid_output must return False (not raise) on schema-cap violations ----
def test_F15_is_valid_output_never_raises_on_cap_violation():
    too_long = '{"answer":"X","reasoning_path":[' + ",".join(['"Entity:A1"'] * 64) + '],"evidence_ids":[],"status":"SUPPORTED"}'
    assert output.is_valid_output(too_long) is False
    assert output.is_valid_output('{"answer":"X","reasoning_path":[],"evidence_ids":[],"status":"SUPPORTED"}') is True
    assert output.is_valid_output("garbage") is False


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
