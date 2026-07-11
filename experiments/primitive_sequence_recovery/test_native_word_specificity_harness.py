"""Tests for the native word-specificity RunPod execution harness. NO real models, NO network, NO evaluator API.

Exercises: preflight (frozen hashes + manifest policy); presentation-order determinism + full coverage; answer-key
non-import in the collector; valid/invalid parsing; retry; resume; atomic writes; duplicate prevention; raw-freeze
determinism; scoring refusal before freeze; scoring on synthetic fake evidence; outcome taxonomy.
"""
import json
import pathlib
import types

import pytest

import native_ws_runlib as R
import native_ws_model as M
import run_native_word_specificity_preflight as PRE
import build_native_word_specificity_presentation_orders as ORD
import run_native_word_specificity_evaluators as RUN
import freeze_native_word_specificity_raw_evidence as FRZ
import score_native_word_specificity as SC

HERE = pathlib.Path(__file__).resolve().parent


def _fake_manifest(tmp, families=("alpha", "beta", "gamma"), backend="fake", bad=False):
    evs = []
    for i, fam in enumerate(families, 1):
        evs.append({"evaluator_id": f"eval_{i}", "model_id": ("..." if bad else f"org/{fam}-model"),
                    "family": fam, "revision": None, "backend": backend, "dtype": "float16",
                    "tensor_parallel_size": 1, "max_model_len": 2048, "trust_remote_code": False,
                    "base_url": None, "max_new_tokens": 24, "seed": 0, "timeout_s": 60})
    p = tmp / "manifest.json"
    p.write_text(json.dumps({"evaluators": evs}), encoding="utf-8")
    return p


def test_preflight_passes_and_catches_bad_manifest(tmp_path):
    good = _fake_manifest(tmp_path)
    rc = PRE.run("42f38d57", "fc15a0d8", str(good), str(tmp_path / "ev"), resume=False)
    assert rc == 0
    # <3 families
    two = _fake_manifest(tmp_path, families=("alpha", "beta"))
    assert PRE.run("42f38d57", "fc15a0d8", str(two), str(tmp_path / "ev2"), resume=False) == 1
    # unresolved model id
    badm = _fake_manifest(tmp_path, bad=True)
    assert PRE.run("42f38d57", "fc15a0d8", str(badm), str(tmp_path / "ev3"), resume=False) == 1
    # authoring-family collision
    coll = _fake_manifest(tmp_path, families=("llama", "gemma", "claude"))
    assert PRE.run("42f38d57", "fc15a0d8", str(coll), str(tmp_path / "ev4"), resume=False) == 1


def test_presentation_order_determinism_and_coverage(tmp_path):
    man = _fake_manifest(tmp_path)
    i1 = ORD.build(str(man), str(R.TRIALS_PATH), str(tmp_path / "o1"), ORD.BASE_SEED)
    i2 = ORD.build(str(man), str(R.TRIALS_PATH), str(tmp_path / "o2"), ORD.BASE_SEED)
    assert i1["orders"]["eval_1"]["sha256"] == i2["orders"]["eval_1"]["sha256"]
    all_ids = {t["trial_id"] for t in R.load_trials()}
    order = json.loads((tmp_path / "o1" / "eval_1_order.json").read_text())["order"]
    assert len(order) == 720 and set(order) == all_ids and len(set(order)) == len(order)
    # different evaluators get different orders (per-evaluator seed)
    o2 = json.loads((tmp_path / "o1" / "eval_2_order.json").read_text())["order"]
    assert order != o2


def test_collector_never_references_answer_key():
    for src in ("run_native_word_specificity_evaluators.py", "native_ws_runlib.py", "native_ws_model.py"):
        assert "answer_key" not in (HERE / src).read_text(encoding="utf-8")


def test_parse_valid_and_invalid():
    assert R.parse_choice('{"choice": "W3"}') == "W3"
    assert R.parse_choice(' {"choice":"W6"} ') == "W6"
    for bad in ('W3', 'the answer is W3', '{"choice": "W7"}', '{"choice": ["W1","W2"]}',
                '{"choice":"W1","x":1}', '', None, 'null', '{}'):
        assert R.parse_choice(bad) is None


def test_retry_and_status_classification():
    proto = R.load_protocol()
    trial = R.load_trials()[0]
    cfg = M.ModelConfig(evaluator_id="e", model_id="fake", family="alpha", backend="fake")
    # flaky: invalid on attempt 0, valid on attempt 1 -> answered in 2 attempts
    ev = M.FakeEvaluator(cfg, mode="flaky")
    rec = R.collect_one(ev, trial, proto, "e", "fake", None, settings=None, timeout_s=5, sleep=lambda s: None)
    assert rec.status == "answered" and rec.attempts == 2
    # always invalid -> status invalid after 2 attempts
    rec2 = R.collect_one(M.FakeEvaluator(cfg, mode="invalid"), trial, proto, "e", "fake", None,
                         settings=None, timeout_s=5, sleep=lambda s: None)
    assert rec2.status == "invalid" and rec2.attempts == 2

    class Raiser:
        def generate(self, prompt, settings=None):
            raise RuntimeError("boom")
    rec3 = R.collect_one(Raiser(), trial, proto, "e", "fake", None, settings=None, timeout_s=5, sleep=lambda s: None)
    assert rec3.status == "missing" and rec3.attempts == 2


def _args(**kw):
    base = dict(manifest=None, evaluator_id="eval_1", trials=str(R.TRIALS_PATH), presentation_order=None,
                output_dir=None, resume=False, dry_run=False, dry_run_n=5, fake_mode="valid")
    base.update(kw); return types.SimpleNamespace(**base)


def test_collect_resume_and_duplicate_prevention(tmp_path):
    man = _fake_manifest(tmp_path)
    outdir = tmp_path / "ev" / "eval_1"
    # first pass: collect all
    RUN.run(_args(manifest=str(man), output_dir=str(outdir)))
    n1 = len(R.read_completed_trial_ids(outdir / "responses.jsonl"))
    assert n1 == 720
    # resume: nothing new, no duplicates
    RUN.run(_args(manifest=str(man), output_dir=str(outdir), resume=True))
    lines = (outdir / "responses.jsonl").read_text().strip().splitlines()
    ids = [json.loads(l)["trial_id"] for l in lines]
    assert len(ids) == len(set(ids)) == 720
    # refuse overwrite without resume
    with pytest.raises(SystemExit):
        RUN.run(_args(manifest=str(man), output_dir=str(outdir), resume=False))


def test_atomic_write_and_torn_line(tmp_path):
    p = tmp_path / "r.jsonl"
    R.append_jsonl_atomic(p, {"trial_id": "t1", "x": 1})
    R.append_jsonl_atomic(p, {"trial_id": "t2", "x": 2})
    with open(p, "a") as fh:
        fh.write('{"trial_id": "t3", "x":')          # torn/partial final line
    assert R.read_completed_trial_ids(p) == {"t1", "t2"}


def test_dry_run_is_non_evidence(tmp_path):
    man = _fake_manifest(tmp_path)
    official = tmp_path / "ev" / "eval_1"
    RUN.run(_args(manifest=str(man), output_dir=str(official), dry_run=True, dry_run_n=3))
    assert not official.exists()                      # nothing written to the official dir
    dr = pathlib.Path(str(official) + "__DRYRUN_NONEVIDENCE")
    assert dr.exists() and (dr / "NONEVIDENCE_DO_NOT_SCORE.txt").exists()


def _full_evidence(tmp_path):
    man = _fake_manifest(tmp_path)
    root = tmp_path / "ev"
    for eid in ("eval_1", "eval_2", "eval_3"):
        RUN.run(_args(manifest=str(man), evaluator_id=eid, output_dir=str(root / eid)))
    return man, root


def test_raw_freeze_determinism_and_order_independence(tmp_path):
    man, root = _full_evidence(tmp_path)
    FRZ.freeze(str(root), str(man), allow_incomplete=False, reason=None)
    d1 = json.loads((root / "raw_evidence_freeze.json").read_text())
    # shuffle one evaluator's response lines -> canonical hash unchanged (sorted by trial_id)
    rp = root / "eval_1" / "responses.jsonl"
    lines = rp.read_text().strip().splitlines()
    rp.write_text("\n".join(reversed(lines)) + "\n")
    FRZ.freeze(str(root), str(man), allow_incomplete=False, reason=None)
    d2 = json.loads((root / "raw_evidence_freeze.json").read_text())
    assert d1["combined_sha256"] == d2["combined_sha256"]
    assert d1["frozen"] is True and d1["family_policy_met_ge3_distinct"] is True


def test_scoring_refuses_before_freeze(tmp_path):
    _man, root = _full_evidence(tmp_path)
    with pytest.raises(SystemExit):
        SC.score(str(root), str(tmp_path / "a.json"))     # no freeze declaration yet


def test_scoring_on_synthetic_evidence_and_taxonomy(tmp_path, monkeypatch):
    man, root = _full_evidence(tmp_path)
    FRZ.freeze(str(root), str(man), allow_incomplete=False, reason=None)
    monkeypatch.setattr(SC, "BOOT", 200)
    monkeypatch.setattr(SC, "PERM", 200)
    out = tmp_path / "analysis.json"
    assert SC.score(str(root), str(out)) == 0
    res = json.loads(out.read_text())
    assert res["freeze_verified"] and res["n_presentations"] == 720 * 3
    assert set(res["primary"]) == {"set_A", "set_B", "overall"}
    assert res["primary"]["set_A"]["bca"] is not None and res["primary"]["set_A"]["permutation"] is not None
    valid_tax = json.loads((HERE / "native_word_specificity_prereg" / "outcome_taxonomy.json").read_text())
    assert res["outcome_taxonomy"] in valid_tax
    assert set(res["flagged_word_sensitivity"]["flagged_words"]) == {"bhaya", "duḥkha", "sukha", "deha"}


def test_no_toplevel_heavy_imports():
    for src in ("native_ws_model.py", "native_ws_runlib.py", "run_native_word_specificity_evaluators.py"):
        head = "\n".join((HERE / src).read_text().splitlines()[:40])
        assert "\nimport torch" not in head and "\nimport transformers" not in head
