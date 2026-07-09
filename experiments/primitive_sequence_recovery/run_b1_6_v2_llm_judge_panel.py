"""B1.6-v2 LLM-as-judge panel runner (sequential single-GPU; gated inputs; mock-tested).

Subcommands:
  judge --panel <judge_panel.json> --judge-index N --judge-visible <panel_judge_visible_outputs.jsonl>
        [--mock] [--limit-outputs K] --out <partial_dir>            # run ONE judge over the blind package
  merge --parts <dirA> <dirB> <dirC> --out <ratings_dir>            # merge 3 judge parts -> scorer ratings

Judges read ONLY the blind judge-visible file (never hidden metadata). Real judges use an operator-supplied
OpenAI-compatible local endpoint (one judge server at a time for single-GPU). No ratings freeze, no unblinding,
no interpretation here. B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import json
import pathlib

import b1_6_llm_judge_panel as JP
import b1_6_llm_adapter as A


def _adapter_for(judge, panel):
    backend = panel.get("backend", "openai_compat_local")
    return A.build_adapter(A.GenerationSettings(
        model_id=judge["id"], backend=backend, base_url=judge.get("endpoint"),
        revision=judge.get("revision") if backend == "transformers" else None,
        temperature=0.0, max_tokens=320))


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.6-v2 LLM judge panel (sequential; gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    jp = sub.add_parser("judge", help="run one judge over the blind package")
    jp.add_argument("--panel", required=True, help="judge panel manifest JSON (judge_models[])")
    jp.add_argument("--judge-index", type=int, required=True)
    jp.add_argument("--judge-visible", required=True, help="panel_judge_visible_outputs.jsonl")
    jp.add_argument("--mock", action="store_true")
    jp.add_argument("--limit-outputs", type=int, default=None)
    jp.add_argument("--out", required=True)

    mp = sub.add_parser("merge", help="merge judge parts into scorer-ready ratings")
    mp.add_argument("--parts", nargs="+", required=True, help="judge part json files or dirs")
    mp.add_argument("--out", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "judge":
        panel = json.loads(pathlib.Path(args.panel).read_text())
        judges = panel["judge_models"]
        generators = panel.get("generator_models", [])
        conflicts = JP.detect_judge_generator_conflicts(judges, generators)
        same_model = [c for c in conflicts if c["type"] == "SAME_MODEL"]
        if same_model:
            raise SystemExit(f"REFUSED: judge is also a generator (no same-model judging): {same_model}")
        judge = judges[args.judge_index]
        adapter = None if args.mock else _adapter_for(judge, panel)
        part = JP.run_single_judge(judge, pathlib.Path(args.judge_visible), adapter=adapter,
                                   limit_outputs=args.limit_outputs, out_dir=pathlib.Path(args.out), write=True)
        print(json.dumps({"judge_id": part["judge_id"], "n_ratings": part["n_ratings"],
                          "n_errors": part["n_errors"], "conflicts": conflicts}, indent=2))
        return

    if args.cmd == "merge":
        parts = []
        for p in args.parts:
            pp = pathlib.Path(p)
            if pp.is_dir():
                pp = next(pp.glob("judge_part_*.json"))
            parts.append(JP.load_part(pp))
        res = JP.merge_judge_parts(parts, out_dir=pathlib.Path(args.out), write=True)
        if res["label"] != "B1_6_V2_LLM_JUDGE_PANEL_READY_MOCK_TESTED":
            raise SystemExit(f"MERGE REFUSED ({res['label']}): {res.get('reasons')}")
        print(json.dumps(res["manifest"], indent=2))


if __name__ == "__main__":
    main()
