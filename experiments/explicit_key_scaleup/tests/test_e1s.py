"""E1-S torch-free tests. Fixture seeds 886000-886004 only; no reserved seed is consumed; stdlib runner."""
from __future__ import annotations

import hashlib
import json
import pathlib

from .. import config as C
from .. import e1_import as EI
from .. import gates as G
from .. import keyspace as KS
from .. import leakage as L
from .. import manifest as MAN
from .. import shortcuts as SC
from ..execution import ExecutionNotAuthorized, _evaluate_authorization, guard_seed, load_signed_record

FIXT = 886000
BENCH = pathlib.Path(__file__).resolve().parents[3] / "docs/research/hybrid_llm/benchmarks"


# ---- (i) E1 imported unchanged ----
def test_e1_sources_byte_identical_and_loaded_from_e1_dir():
    EI.assert_e1_unchanged()
    for n, want in EI.E1_SOURCE_SHA256.items():
        assert hashlib.sha256((EI.E1_DIR / n).read_bytes()).hexdigest() == want, n
    t = EI.e1_task()
    assert pathlib.Path(t.__file__).resolve().parent == EI.E1_DIR
    assert (t.PAD, t.SEP) == (KS.PAD, KS.SEP)          # E1._masked_mean masks on task.PAD; must coincide
    pkg = pathlib.Path(__file__).resolve().parents[1]
    assert not any("class E1" in p.read_text() for p in pkg.glob("*.py")), "E1 must not be copied"

def test_e1_drift_is_refused(tmp=None):
    saved = dict(EI.E1_SOURCE_SHA256)
    try:
        EI.E1_SOURCE_SHA256["models.py"] = "0" * 64
        try:
            EI.assert_e1_unchanged(); assert False
        except EI.ExplicitKeyProtocolError:
            pass
    finally:
        EI.E1_SOURCE_SHA256.update(saved)


# ---- (ii) key space / generator rules ----
def test_vocab_geometry_and_reserved_id_class():
    assert KS.VOCAB == 226 and KS.KLEN == 6 and KS.QLEN == 9
    classes = [KS.token_class(t) for t in range(KS.VOCAB)]
    assert classes.count("id") == KS.ID_PRIMS and classes.count("value") == KS.N_VALUES
    ids = {t for t in range(KS.VOCAB) if KS.token_class(t) == "id"}
    assert all(KS.token_class(t) != "id" for t in range(KS.VOCAB) if t not in ids)   # F16: exclusive class

def test_pools_disjoint_hash_partitioned_and_markerless():
    p = KS.identity_pools()
    tr, dv, fn = map(set, (p["train"], p["dev"], p["final"]))
    assert not (tr & dv) and not (tr & fn) and not (dv & fn)
    assert len(tr) + len(dv) + len(fn) == KS.ID_PRIMS * (KS.ID_PRIMS - 1)
    assert 0.65 < len(tr) / (len(tr) + len(dv) + len(fn)) < 0.75
    r = L.check_pools_disjoint_and_markerless(); assert r["pass"] and r["markerless"]
    # process-independent: recompute in a subprocess with a different hash salt
    import subprocess, sys, os
    code = "from experiments.explicit_key_scaleup import keyspace as KS; print(len(KS.identity_pools()['final']), KS.identity_pools()['final'][:3])"
    out = subprocess.run([sys.executable, "-c", code], cwd=BENCH.parents[3], env=dict(os.environ, PYTHONHASHSEED="424242"),
                         capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == f"{len(fn)} {p['final'][:3]}", out.stdout + out.stderr

def test_heldout_composition_pairs():
    pr = KS.st_rel_pairs()
    assert len(pr["seen"]) + len(pr["held_out"]) == KS.N_ST * KS.N_REL and 10 <= len(pr["held_out"]) <= 30
    tr = KS.build_train_split(40, 7, 32, 0.3)
    assert L.check_heldout_pairs_absent_from_training(tr)["pass"]
    g8 = KS.build_eval_splits(KS.identity_pools()["dev"], 20, FIXT, 32)["G8_unseen_composition"]
    held = set(pr["held_out"])
    for e in g8:
        kt = e["key_tokens"][e["target_index"]]
        assert ((kt[0] - KS._ST_BASE) // KS.SYN, (kt[4] - KS._REL_BASE) // KS.SYN) in held

def test_episode_structure_at_every_density():
    pool = KS.identity_pools()["final"]
    for K in KS.DENSITIES:
        for prof in KS.PROFILES:
            e = KS.build_episode(FIXT + K, pool, K, profile=prof)
            keys = [tuple(k) for k in e["key_tokens"]]
            assert len(keys) == K == len(set(keys)) and 0 <= e["target_index"] < K
            assert all(len(k) == KS.KLEN for k in keys) and len(e["query_tokens"]) == KS.QLEN
            tgt = keys[e["target_index"]]
            n_sida, n_disa, n_hard = KS.profile_counts(prof, K)
            same_subject = sum(1 for k in keys if k[1:3] == tgt[1:3]) - 1
            assert same_subject >= n_sida, (K, prof, same_subject, n_sida)          # near-miss structure present
        nm = KS.build_episode(FIXT + K + 1, pool, K, no_match=True)
        assert nm["target_index"] == -1 and nm["target_value"] == -1
    assert KS.profile_counts("balanced", 32) == (6, 6, 8) and KS.profile_counts("hard_names", 32) == (4, 4, 18)
    assert KS.profile_counts("same_entity", 32) == (14, 4, 6) and KS.profile_counts("stable", 32) == (2, 2, 2)

def test_render_rules():
    e = KS.build_episode(FIXT, KS.identity_pools()["dev"], 32)
    key = e["key_tokens"][e["target_index"]]; q = [t for t in e["query_tokens"] if t != KS.PAD]
    assert [KS.token_class(t) for t in key] == ["subject_type", "id", "id", "sep", "relation_type", "object_type"]
    assert {t for t in key if KS.token_class(t) == "id"} == {t for t in q if KS.token_class(t) == "id"}   # ids verbatim
    nonid_key = {t for t in key if KS.token_class(t) in ("subject_type", "relation_type", "object_type")}
    assert not (nonid_key & set(q))                                                                       # types paraphrased
    assert KS.value_of_token(KS.v_tok(5)) == 5

def test_leakage_suite_passes_and_catches_a_leak():
    ev = KS.build_eval_splits(KS.identity_pools()["dev"], 30, FIXT, 32); tr = KS.build_train_split(30, 7, 32, 0.3)
    r = L.run_all(ev, tr); assert r["all_pass"], {k: v for k, v in r.items() if isinstance(v, dict) and not v["pass"]}
    bad = [dict(e) for e in ev["G1_unseen_identity"]]
    bad[0]["key_tokens"] = [list(k) for k in bad[0]["key_tokens"]]
    bad[0]["key_tokens"][bad[0]["target_index"]][5] = KS.v_tok(1)           # value token smuggled into a key
    assert not L.check_no_answer_in_key(bad)["pass"]
    leaked = [dict(bad[0])]; leaked[0]["key_tokens"] = [list(k) for k in ev["G1_unseen_identity"][0]["key_tokens"]]
    tr_sid = KS.identity_pools()["train"][0]
    leaked[0]["key_tokens"][leaked[0]["target_index"]][1:3] = [KS.id_tok(tr_sid[0]), KS.id_tok(tr_sid[1])]
    assert not L.check_eval_targets_unseen(leaked)["pass"]

def test_structure_blind_baselines_and_margin_rule():
    g1 = KS.build_eval_splits(KS.identity_pools()["dev"], 120, FIXT, 32)["G1_unseen_identity"]
    r = SC.run_suite(g1, 1.0, C.GATES["structure_blind_margin"])
    assert not r["shortcut_detected"] and all(0.0 <= v < 0.5 for v in r["baselines"].values()), r
    const = SC.baseline_e2e("most_frequent_value", g1)
    assert SC.run_suite(g1, const, C.GATES["structure_blind_margin"])["shortcut_detected"]     # constant emitter
    lex = SC.baseline_e2e("lexical_overlap_key", g1)
    assert SC.run_suite(g1, lex + 0.05, C.GATES["structure_blind_margin"])["shortcut_detected"]


# ---- (iv) gates / verdict ----
def _metrics(addr=0.95, fa=0.1, fr=0.05, e2e=0.9, b0=0.1, g8=None):
    from ..gates import _e1_gates
    prec, rec = _e1_gates().nomatch_precision_recall(fa, fr)
    return {"G1_addr": addr, "G2_addr": addr, "G3_addr": addr, "G4_addr": addr, "G5_addr": addr, "G7_addr": max(addr, 0.95),
            "G8_addr": addr if g8 is None else g8, "G1_e2e": e2e, "G1_false_reject": fr, "answer_availability": 1 - fr,
            "oracle_key_value_accuracy": 1.0, "nomatch_false_accept": fa, "nomatch_recall": rec, "nomatch_precision": prec,
            "nomatch_confident_false_accept": fa / 2, "b0_G1_e2e": b0, "improvement_over_b0": e2e - b0,
            "oracle_to_predicted_gap": 1.0 - e2e}

def _seed(per_density):
    return {"densities": {K: {"metrics": m, "gates": G.eval_gates(m)} for K, m in per_density.items()}}

def test_gates_and_verdict_vocabulary():
    good, bad_g8, bad_nm, bad = _metrics(), _metrics(g8=0.5), _metrics(fa=0.5), _metrics(addr=0.3, e2e=0.3)
    assert G.eval_gates(good)["all_primary_pass"] and not G.eval_gates(bad_g8)["all_primary_pass"]
    common = dict(leakage_ok=True, determinism_ok=True, shortcut_detected=False, anchor_ok=True)
    seeds = [_seed({32: good, 128: good, 512: good}) for _ in range(5)]
    assert G.verdict(seeds, **common)[0] == "EXPLICIT_KEY_SCALEUP_VALIDATED"
    seeds = [_seed({32: good, 128: good, 512: bad}) for _ in range(5)]
    v, pres = G.verdict(seeds, **common); assert v == "EXPLICIT_KEY_SCALEUP_DENSITY_LIMITED" and "DENSITY_CEILING_128" in pres
    seeds = [_seed({32: good, 128: bad, 512: bad}) for _ in range(5)]
    assert G.verdict(seeds, **common)[1][-1] == "DENSITY_CEILING_32"
    seeds = [_seed({32: good, 128: bad, 512: bad_nm}) for _ in range(5)]
    assert G.verdict(seeds, **common)[0] == "EXPLICIT_KEY_SCALEUP_NOMATCH_FAILED"
    seeds = [_seed({32: bad, 128: bad, 512: bad}) for _ in range(5)]
    assert G.verdict(seeds, **common)[0] == "EXPLICIT_KEY_SCALEUP_NOT_VALIDATED"
    seeds = [_seed({32: good, 128: good, 512: good}) for _ in range(3)] + [_seed({32: good, 128: good, 512: bad})] * 2
    assert G.verdict(seeds, **common)[0] == "EXPLICIT_KEY_SCALEUP_DENSITY_LIMITED"   # 3/5 at 512 is not enough
    assert G.verdict(seeds, **{**common, "anchor_ok": False})[0] == "EXPLICIT_KEY_PROTOCOL_VIOLATED"
    assert G.verdict(seeds, **{**common, "shortcut_detected": True})[0] == "SHORTCUT_OR_LEAKAGE_DETECTED"
    assert G.verdict(seeds, **{**common, "determinism_ok": False})[0] == "EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED"
    for v in C.VERDICTS:
        G.assert_verdict_admissible(v, list(G.ALWAYS))
    assert set(G.ALWAYS) == set(C.PRESERVED_VERDICTS) and not (set(C.VERDICTS) & C.FORBIDDEN_VERDICTS)


# ---- (v) digest / record / companion JSON / guard ----
def test_config_digest_binds_everything_and_matches_companion():
    d = MAN.config_digest(); assert d == MAN.config_digest() and len(d) == 64
    pl = MAN.config_payload()
    assert pl["recipe"]["steps"] == 1200 and pl["densities"] == [32, 128, 512] and pl["primary_density"] == 512
    assert pl["e1_source_sha256"] == EI.E1_SOURCE_SHA256 and pl["gates"] == dict(C.GATES)
    doc = json.loads((BENCH / "E1S_PREREGISTRATION.json").read_text())
    assert doc["ratified"] is True and doc["config_digest"] == d and doc["densities"] == [32, 128, 512]
    assert doc["seeds"] == pl["seeds"] and doc["expected_e1_params"] == C.EXPECTED_E1_PARAMS == 22_848

def test_record_unsigned_scoped_and_guard_fails_closed():
    rec = load_signed_record(); assert rec is not None and rec["arm"] == "E1-S"
    for role, entry in rec["roles"].items():
        assert entry["authorized"] is False and entry["token_sha256"] is None
        assert sorted(entry["scope_seeds"]) == sorted(C.DEVELOPMENT_SEEDS if role == "development" else C.FINAL_SEEDS)
    for s in (6100, 6102, 6140, 6144):
        try:
            guard_seed(s, "any"); assert False, s
        except ExecutionNotAuthorized:
            pass
    for s in (500, 3140, 5140, 2028, 28, 99991, 8100, 8200, 883000):       # prior blocks are never consumed
        try:
            guard_seed(s); assert False, s
        except ExecutionNotAuthorized as exc:
            assert "prior block" in str(exc)
    assert guard_seed(FIXT).authorized and guard_seed(123456).role == "non_reserved"

def test_two_key_evaluation_semantics():
    tok = "e1s-test-token"
    entry = {"authorized": True, "scope_seeds": [6100, 6101, 6102], "expires_at": None,
             "token_sha256": hashlib.sha256(tok.encode()).hexdigest(), "protocol_lock_digest": MAN.config_digest()}
    rec = {"roles": {"development": entry}}
    assert _evaluate_authorization("development", 6100, tok, rec).authorized
    for role, seed, t, r in (("development", 6100, "wrong", rec), ("development", 6140, tok, rec), ("final", 6140, tok, rec),
                             ("development", 6100, None, rec), ("development", 6100, tok, None),
                             ("development", 6100, tok, {"roles": {"development": {**entry, "protocol_lock_digest": "x"}}}),
                             ("development", 6100, tok, {"roles": {"development": {**entry, "expires_at": "2000-01-01T00:00:00+00:00"}}})):
        try:
            _evaluate_authorization(role, seed, t, r); assert False, (role, seed)
        except ExecutionNotAuthorized:
            pass

def test_parameter_counts_per_vocab():
    assert C.e1_param_count(226) == 22_848 and C.e1_param_count(250) == 24_384     # E1's own vocab reproduces the survey figure
    assert C.b0_param_count(32, 250) == 32_608                                   # E1's B0 at its own geometry
    assert C.b0_param_count(512) == 61_792


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for t in tests:
        try:
            t(); p += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            f += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main())
