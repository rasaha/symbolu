#!/usr/bin/env python3
"""Combined 0-7 descriptive comparison (supplementary only; verdict is classify.py on 3-7)."""
import argparse, json, pathlib
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", required=True, help="five_seed_results.json (seeds 3-7)")
    ap.add_argument("--prior", default=str(pathlib.Path(__file__).resolve().parents[2] /
                    "artifacts" / "slots_only_results_sarm_1200_run1.json"), help="seeds 0-2")
    args = ap.parse_args()
    h = json.loads(pathlib.Path(args.holdout).read_text())
    p = json.loads(pathlib.Path(args.prior).read_text()) if pathlib.Path(args.prior).exists() else None
    def s96(res):
        return {r["seed"]: r["needle_by_dist"]["96"] for r in res["arms"]["S"]}
    out = {"holdout_3_7_S_needle_d96": s96(h)}
    if p:
        out["prior_0_2_S_needle_d96"] = s96(p)
        out["combined_0_7"] = {**s96(p), **s96(h)}
    print(json.dumps(out, indent=2))
if __name__ == "__main__":
    main()
