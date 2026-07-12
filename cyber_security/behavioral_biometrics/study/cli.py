"""Study CLI. JSON output. Mock/synthetic reports always show the no-claim banner.

    python -m cyber_security.behavioral_biometrics.study.cli <command> [opts]

Commands: generate-mock · validate · split · run-identity · run-coupling · run-bcvf ·
run-fusion · calibrate · run-temporal · run · export-evidence · report · prereg-template
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from cyber_security.behavioral_biometrics import splits
from cyber_security.behavioral_biometrics.study import (
    bcvf,
    confidence,
    effects,
    evidence,
    fusion,
    identity,
    mockdata,
    origin,
    preregistration,
    report,
    runner,
    temporal,
    use_eval,
)

CFG = effects.DEFAULT
_ITERS = 400  # CLI default bootstrap resamples (kept modest for interactivity)


def _out(obj: Any) -> int:
    print(json.dumps(obj, indent=2, default=lambda o: getattr(o, "__dict__", str(o))))
    return 0


def _banner(fixture_or_records) -> Dict[str, Any]:
    records = (fixture_or_records if isinstance(fixture_or_records, list)
               else fixture_or_records.get("records", []))
    lock = origin.claim_lock(records) if records else {"locked": True, "banner": origin.BANNER}
    return {"banner": lock.get("banner")}


def _load(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def _cohort(args) -> List[Dict[str, Any]]:
    if getattr(args, "data", None):
        d = _load(args.data)
        return d["records"] if isinstance(d, dict) and "records" in d else d
    return mockdata.make_cohort(args.regime, seed=args.seed)["records"]


def cmd_generate_mock(args) -> int:
    fx = mockdata.generate(args.regime, seed=args.seed)
    if args.out:
        Path(args.out).write_text(json.dumps(fx, indent=2))
    return _out({"regime": args.regime, "kind": fx["kind"], "origin": fx["origin"],
                 "banner": origin.BANNER, "out": args.out,
                 "n": len(fx.get("records", fx.get("rows", fx.get("stream", []))))})


def cmd_validate(args) -> int:
    recs = _cohort(args)
    return _out({"origin": origin.cohort_origin(recs), "is_real": origin.is_real(recs),
                 "eligibility": runner._eligibility(recs, CFG), "banner": _banner(recs)["banner"]})


def cmd_split(args) -> int:
    recs = _cohort(args)
    plan = splits.session_disjoint(recs, seed=args.seed)
    return _out({"split": plan.name, "leakage_violations": splits.check_leakage(plan, recs),
                 "n_test_rows": len(plan.labeled_test()), "banner": _banner(recs)["banner"]})


def cmd_run_identity(args) -> int:
    recs = _cohort(args)
    plan = splits.session_disjoint(recs, seed=args.seed)
    ab = identity.run_ablation(recs, plan, cfg=CFG)
    return _out({"banner": _banner(recs)["banner"],
                 "arms": {a: (r["metrics"] if r.get("usable") else r) for a, r in ab.items()}})


def cmd_run_coupling(args) -> int:
    recs = _cohort(args)
    return _out({"banner": _banner(recs)["banner"], **use_eval.use_verdict(recs, cfg=CFG, iters=_ITERS)})


def cmd_run_bcvf(args) -> int:
    fx = mockdata.make_bcvf(args.regime, seed=args.seed) if args.regime in mockdata.BCVF_REGIMES \
        else _load(args.data)
    v = bcvf.bcvf_verdict(fx, fx["rows"], iters=_ITERS)
    return _out({"banner": origin.BANNER, **v})


def cmd_run_fusion(args) -> int:
    fx = mockdata.make_fusion(args.regime, seed=args.seed) if args.regime in mockdata.FUSION_REGIMES \
        else _load(args.data)
    v = fusion.fusion_verdict(fx, fx["rows"], iters=_ITERS)
    return _out({"banner": origin.BANNER, **v})


def cmd_calibrate(args) -> int:
    fx = mockdata.make_confidence(args.regime, seed=args.seed) \
        if args.regime in mockdata.CONFIDENCE_REGIMES else _load(args.data)
    v = confidence.confidence_verdict(fx.get("origin", "MOCK_TEST_ONLY"),
                                      fx["rows"]["scores"], fx["rows"]["labels"], method=args.method)
    return _out({"banner": origin.BANNER, **v})


def cmd_run_temporal(args) -> int:
    fx = mockdata.make_temporal(args.regime, seed=args.seed) \
        if args.regime in mockdata.TEMPORAL_REGIMES else _load(args.data)
    return _out({"banner": origin.BANNER, **temporal.temporal_verdict(fx, fx)})


def cmd_run(args) -> int:
    recs = _cohort(args)
    config = preregistration.load(args.config) if args.config else preregistration.default_template()
    tf = mockdata.make_temporal(args.temporal, seed=args.seed) if args.temporal else None
    rep = runner.run_study(recs, cfg=CFG, iters=_ITERS, temporal_fixture=tf, config=config, seed=args.seed)
    if args.output:
        Path(args.output).write_text(json.dumps(rep, indent=2, default=str))
    for line in report.summary_lines(rep):
        print("# " + line, file=sys.stderr)
    return _out(rep)


def cmd_export_evidence(args) -> int:
    recs = _cohort(args)
    plan = splits.session_disjoint(recs, seed=args.seed)
    mm = identity.run_arm(recs, plan, "MM", cfg=CFG)
    prob = float(1.0 / (1.0 + np.exp(-((np.array(mm["scores"]) - np.mean(mm["scores"]))
                                       / (np.std(mm["scores"]) + 1e-9))[0]))) if mm.get("usable") else 0.5
    conf = confidence.build_confidence(identity_probability=prob,
                                       calibration_status=confidence.CONFIDENCE_NOT_ELIGIBLE,
                                       uncertainty=0.4, quality=0.8, evidence_sufficiency=0.6)
    exp = evidence.build(session_id="mock_session", timestamp="2026-01-01T00:00:00",
                         confidence_output=conf, modality_quality={"kbd": 0.9, "ptr": 0.9},
                         data_origin=origin.cohort_origin(recs)).to_dict()
    return _out({"banner": _banner(recs)["banner"], "evidence": exp,
                 "validation_problems": evidence.validate(exp)})


def cmd_report(args) -> int:
    rep = _load(args.input)
    for line in report.summary_lines(rep):
        print(line)
    return _out({"origin_banner": rep.get("origin_banner"),
                 "mechanical_verdicts": rep.get("mechanical_verdicts")})


def cmd_prereg_template(args) -> int:
    t = preregistration.default_template()
    if args.out:
        preregistration.write_template(args.out)
    return _out({"prereg": t, "validation_problems": preregistration.validate(t)})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="study")
    p.add_argument("--seed", type=int, default=7)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, regime_default=None, data=True):
        sp = sub.add_parser(name)
        if regime_default is not None:
            sp.add_argument("--regime", default=regime_default)
        if data:
            sp.add_argument("--data", default=None)
        return sp

    sp = add("generate-mock", "MULTIMODAL_MARGINAL_SIGNAL", data=False); sp.add_argument("--out", default=None)
    add("validate", "MULTIMODAL_MARGINAL_SIGNAL")
    add("split", "MULTIMODAL_MARGINAL_SIGNAL")
    add("run-identity", "MULTIMODAL_MARGINAL_SIGNAL")
    add("run-coupling", "COUPLING_ONLY_SIGNAL")
    add("run-bcvf", "BCVF_HELPFUL")
    add("run-fusion", "FUSION_HELPFUL")
    sp = add("calibrate", "CONFIDENCE_WELL_CALIBRATED"); sp.add_argument("--method", default="platt")
    add("run-temporal", "ABRUPT_TAKEOVER")
    sp = add("run", "MULTIMODAL_MARGINAL_SIGNAL"); sp.add_argument("--config", default=None)
    sp.add_argument("--output", default=None); sp.add_argument("--temporal", default=None)
    add("export-evidence", "MULTIMODAL_MARGINAL_SIGNAL")
    sp = sub.add_parser("report"); sp.add_argument("--input", required=True)
    sp = sub.add_parser("prereg-template"); sp.add_argument("--out", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {"generate-mock": cmd_generate_mock, "validate": cmd_validate, "split": cmd_split,
                "run-identity": cmd_run_identity, "run-coupling": cmd_run_coupling,
                "run-bcvf": cmd_run_bcvf, "run-fusion": cmd_run_fusion, "calibrate": cmd_calibrate,
                "run-temporal": cmd_run_temporal, "run": cmd_run,
                "export-evidence": cmd_export_evidence, "report": cmd_report,
                "prereg-template": cmd_prereg_template}
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
