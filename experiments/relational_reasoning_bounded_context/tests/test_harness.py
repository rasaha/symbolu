"""Smoke-harness tests (torch-free). Fixtures 883000-883004 only; no reserved seed, no training.

The torch-free scoring/report path is exercised by feeding GOLD predictions (a perfect-model stand-in) and
deliberately-broken predictions. The torch run path (`run_experiment`, `generate_predictions`,
`train_checkpoint`) is NOT exercised here (no torch); its fail-closed guard IS.
"""
from __future__ import annotations

import tempfile

from .. import dataset as DS
from .. import run as R
from ..execution import ExecutionNotAuthorized
from ..generator import SPLITS
from ..output import serialize_output

FIXT = 883000


def test_dataset_builders():
    ex = DS.build_examples(FIXT, 2, role="unit")
    assert ex and all(set(e) == {"input", "output", "split"} for e in ex)
    p0 = DS.build_p0_examples(FIXT, 2, role="unit")
    assert p0 and all("<OUTPUT>" not in e["input"] for e in ex)   # marker added at train time, not in input


def _cohorts(n=4, role="unit"):
    r = DS.eval_cohorts_r(FIXT, n, role=role)
    p0 = DS.eval_cohorts_p0(FIXT, n, role=role)
    return p0, r


def test_perfect_model_report_is_admissible_and_validated():
    p0c, rc = _cohorts()
    report = R.assemble_report(
        seed=FIXT, role="fixture", checkpoint_digest="mock",
        p0_predictions=DS.gold_predictions(p0c), r_predictions=DS.gold_predictions(rc),
        protocol_valid=True)
    assert report["reasoning_admissible"] is True
    assert report["structured_output_validity"] == 1.0
    assert report["p0"]["gate"]["established"] is True
    assert report["verdict"]["primary_verdict"] == "RELATIONAL_REASONING_VALIDATED"
    # required §8 fields are present
    for k in ("checkpoint_digest", "config_digest", "tokenizer_vocab_digest", "per_split_answer_accuracy",
              "discovery", "r9", "latest_event", "evidence", "abstention", "hallucination",
              "structure_blind_baselines", "shortcut_detected", "gates", "verdict"):
        assert k in report, k
    # preserved invariants co-emitted; forbidden never emitted
    from ..config import FORBIDDEN_VERDICTS, PRESERVED_VERDICTS
    assert set(PRESERVED_VERDICTS) <= set(report["verdict"]["preserved"])
    assert report["verdict"]["primary_verdict"] not in FORBIDDEN_VERDICTS


def test_p0_failure_makes_r_nonadmissible():
    p0c, rc = _cohorts()
    # break P0 predictions -> P0 not established
    broken_p0 = {sub: [(c, '{"answer":"WRONG","reasoning_path":[],"evidence_ids":[],"status":"SUPPORTED"}')
                       for c in ctxs] for sub, ctxs in p0c.items()}
    report = R.assemble_report(seed=FIXT, role="fixture", checkpoint_digest="mock",
                               p0_predictions=broken_p0, r_predictions=DS.gold_predictions(rc))
    assert report["reasoning_admissible"] is False
    assert report["admissibility_stamp"] == "NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION"
    assert report["verdict"]["primary_verdict"] == "RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY"


def test_protocol_invalid_dominates():
    p0c, rc = _cohorts()
    report = R.assemble_report(seed=FIXT, role="fixture", checkpoint_digest="mock",
                               p0_predictions=DS.gold_predictions(p0c),
                               r_predictions=DS.gold_predictions(rc), protocol_valid=False)
    assert report["verdict"]["primary_verdict"] == "PROTOCOL_VIOLATED"


def test_write_report():
    p0c, rc = _cohorts(2)
    report = R.assemble_report(seed=FIXT, role="fixture", checkpoint_digest="mock",
                               p0_predictions=DS.gold_predictions(p0c), r_predictions=DS.gold_predictions(rc))
    with tempfile.TemporaryDirectory() as d:
        path = R.write_report(report, d)
        assert path.endswith("report_fixture_883000.json")


def test_run_experiment_fails_closed_on_reserved_seed():
    # guard raises BEFORE any torch import / cohort materialization
    for s in (8100, 8101, 81600):
        try:
            R.run_experiment(s); assert False, s
        except ExecutionNotAuthorized:
            pass


def test_overfit_diagnostic_fails_closed_on_reserved_seed():
    for s in (8100, 81600):
        try:
            R.overfit_diagnostic(seed=s); assert False, s
        except ExecutionNotAuthorized:
            pass


def test_answer_and_p0_accuracy_helpers():
    ctxs = DS.eval_cohorts_r(FIXT, 3, role="unit")["R1"]
    perfect = [(c, serialize_output(c.authoritative_output)) for c in ctxs]
    assert R.answer_accuracy(perfect) == 1.0
    assert R.answer_accuracy([(c, "garbage") for c in ctxs]) == 0.0


def test_p0_failure_profile_and_predictions_dump(tmp_dir="/tmp/claude-0/-home-user-symbolu/2ec1335e-f6de-58ee-b0b2-cf1663a48120/scratchpad/predtest"):
    import json, pathlib, shutil
    from ..schema_ext import ReasoningOutput
    cohorts = DS.eval_cohorts_p0(FIXT, 2, role="unit")
    gold = DS.gold_predictions(cohorts)
    prof = R.p0_failure_profile(gold["B1"]); assert prof["correct"] == 2 and sum(prof.values()) == 2
    b1 = cohorts["B1"]
    abst = [(c, serialize_output(ReasoningOutput(None, (), (), "INSUFFICIENT_EVIDENCE"))) for c in b1]
    assert R.p0_failure_profile(abst)["abstained"] == 2
    other_id = [(c, serialize_output(ReasoningOutput(
        next(e.entity_id for e in c.entities if e.entity_id != c.query.root_entity_id), (), (), "SUPPORTED")))
        for c in b1]
    assert R.p0_failure_profile(other_id)["in_context_wrong"] == 2
    assert R.p0_failure_profile([(c, "garbage") for c in b1])["invalid"] == 2
    shutil.rmtree(tmp_dir, ignore_errors=True)
    path = R.write_predictions(gold, tmp_dir, role="fixture", seed=FIXT)
    rows = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines()]
    assert len(rows) == 14 and all(r["valid"] and r["gold"] == r["pred"] for r in rows)
    shutil.rmtree(tmp_dir, ignore_errors=True)


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
