"""B1.6-v2 sequential single-GPU panel generation helper (gated; mock-tested).

Runs ONE generator at a time (so a single GPU only needs one model server live at a time), writes a partial
package per generator, then merges + re-blinds both partials into the same 100-output panel package the judging
harness expects. Identical re-blind to the simultaneous panel (same seed => same final ids).

Subcommands:
  part  --panel <json> --generator-index N [--mock] [--decl <path>] --out <dir>   # one generator
  merge --parts <dirA> <dirB> [...] --out <dir>                                    # merge + re-blind

Real `part` builds a per-generator adapter from the panel manifest (openai_compat_local endpoint or
transformers), still gated by the evidence-freeze declaration. `merge` is pure data (no model). No real
generation is performed by this module beyond what an operator-provided model server returns; no judging.
B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import json
import pathlib

import b1_6_model_panel as P
import b1_6_llm_adapter as A
import run_b1_6_pilot_generation as drv


def _adapter_factory_from_panel(panel):
    backend = panel.get("backend", "openai_compat_local")
    t = panel.get("temperature", 0.7)
    mx = panel.get("max_tokens", 320)
    sd = panel.get("seed", 1101)

    def factory(gen):
        return A.build_adapter(A.GenerationSettings(
            model_id=gen["id"], backend=backend, base_url=gen.get("endpoint"),
            revision=gen.get("revision") if backend == "transformers" else None,
            temperature=t, max_tokens=mx, seed=sd))
    return factory


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.6-v2 sequential single-GPU panel generation (gated).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("part", help="run one generator part")
    pp.add_argument("--panel", required=True, help="path to the v2 model-panel manifest JSON")
    pp.add_argument("--generator-index", type=int, required=True, help="0=first generator, 1=second, ...")
    pp.add_argument("--mock", action="store_true", help="deterministic placeholder text (plumbing only)")
    pp.add_argument("--mode", default=drv.EXPLORATORY_MODE, choices=list(drv.VALID_MODES))
    pp.add_argument("--limit-items", type=int, default=10)
    pp.add_argument("--representation-version", default=drv.DEFAULT_REPRESENTATION,
                    choices=list(drv.REPRESENTATIONS))
    pp.add_argument("--decl", required=True, help="path to the exploratory v2 evidence-freeze declaration")
    pp.add_argument("--out", required=True, help="partial output directory (e.g. .../generation_partial_M1)")

    mp = sub.add_parser("merge", help="merge + re-blind partial parts")
    mp.add_argument("--parts", nargs="+", required=True, help="partial dirs or panel_part.json files")
    mp.add_argument("--out", required=True, help="final merged output directory (.../generation)")
    mp.add_argument("--reblind-seed", type=int, default=20260708)

    args = ap.parse_args(argv)

    if args.cmd == "part":
        panel = json.loads(pathlib.Path(args.panel).read_text())
        factory = None if args.mock else _adapter_factory_from_panel(panel)
        part = P.run_single_generator_panel_part(
            panel, gen_index=args.generator_index, adapter_factory=factory, mock=args.mock,
            mode=args.mode, limit_items=args.limit_items, representation=args.representation_version,
            decl_path=pathlib.Path(args.decl), out_dir=pathlib.Path(args.out), write=True)
        print(json.dumps({"generator_code": part["generator_code"], "generator_id": part["generator_id"],
                          "n_outputs": part["n_outputs"], "representation_version": part["representation_version"],
                          "mode": part["mode"]}, indent=2))
        return

    if args.cmd == "merge":
        res = P.merge_panel_parts([pathlib.Path(p) for p in args.parts],
                                  out_dir=pathlib.Path(args.out), write=True, reblind_seed=args.reblind_seed)
        if res["label"] != "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_READY_MOCK_TESTED":
            raise SystemExit(f"MERGE REFUSED ({res['label']}): {res.get('reasons')}")
        print(json.dumps(res["panel_manifest"], indent=2))


if __name__ == "__main__":
    main()
