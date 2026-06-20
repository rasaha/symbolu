#!/usr/bin/env python3
"""train_bhava_probe.py — train/evaluate lightweight probes over the extracted features.

Evaluates each feature set (bhava_only, cg_state_32d, delta_bhava_only, hidden_only,
hidden_plus_bhava, hidden_plus_cg_state) with k-fold OOF logistic regression, computes the paired
hidden_plus_bhava-vs-hidden_only comparison, and writes results.json for the report generator.

numpy-only (CPU). Reads runs/bhava_probe/<ts>/{features.npz,labels.json}.

Usage:
  python scripts/cg_wrapper_ablation/train_bhava_probe.py runs/bhava_probe/<ts> [--model logreg]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cg_ablation import probe_features as PF      # noqa: E402
from cg_ablation import probe_train as PT          # noqa: E402
from cg_ablation.probe_decide import decide, MIN_PER_CLASS  # noqa: E402


def run(run_dir: Path, model: str = "logreg", k: int = 5, l2: float = 1.0, seed: int = 0) -> dict:
    import numpy as np

    npz = np.load(run_dir / "features.npz")
    arrays = {key: npz[key] for key in npz.files}
    labels = json.loads((run_dir / "labels.json").read_text())

    # group example indices by label_type
    by_type = defaultdict(list)
    for i, lab in enumerate(labels):
        by_type[lab["label_type"]].append(i)

    sets = PF.available_sets_arrays(arrays)
    report = {"model": model, "k": k, "l2": l2, "sets_available": sets, "by_label_type": {}}

    for ltype, idxs in by_type.items():
        idxs = np.asarray(idxs)
        y = np.asarray([labels[i]["label"] for i in idxs], dtype=int)
        n = len(y)
        per_class_ok = (int((y == 1).sum()) >= MIN_PER_CLASS and int((y == 0).sum()) >= MIN_PER_CLASS)

        results = {}
        for s in sets:
            X = PF.build_matrix_from_arrays(arrays, s)[idxs]
            results[s] = PT.evaluate_feature_set(X, y, model=model, k=k, l2=l2, seed=seed)

        # paired comparisons (cand vs ref), same folds/seed -> aligned per-example correctness
        paired = {}
        if "hidden_only" in results and "hidden_plus_bhava" in results:
            paired["hidden_plus_bhava_vs_hidden"] = PT.paired_vs_reference(
                y, results["hidden_only"]["oof_correct"],
                results["hidden_plus_bhava"]["oof_correct"])
        if "hidden_only" in results and "hidden_plus_cg_state" in results:
            paired["hidden_plus_cg_state_vs_hidden"] = PT.paired_vs_reference(
                y, results["hidden_only"]["oof_correct"],
                results["hidden_plus_cg_state"]["oof_correct"])
        if "delta_bhava_only" in results and "bhava_only" in results:
            paired["bhava_vs_delta_bhava"] = PT.paired_vs_reference(
                y, results["delta_bhava_only"]["oof_correct"],
                results["bhava_only"]["oof_correct"])

        verdict = decide(results, paired, n=n, min_per_class=MIN_PER_CLASS)
        if not per_class_ok:
            verdict = {"decision": "INSUFFICIENT_DATA",
                       "reasons": [f"per-class count < {MIN_PER_CLASS} "
                                   f"(pos={int((y==1).sum())}, neg={int((y==0).sum())})"],
                       "answers": verdict.get("answers", {})}

        # strip per-example arrays from the saved metrics (keep summary numbers)
        slim = {s: {kk: vv for kk, vv in r.items() if kk != "oof_correct"}
                for s, r in results.items()}
        report["by_label_type"][ltype] = {
            "n": n, "pos": int((y == 1).sum()), "neg": int((y == 0).sum()),
            "results": slim, "paired": paired, "verdict": verdict,
        }

    (run_dir / "results.json").write_text(json.dumps(report, indent=2))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--model", default="logreg", choices=["logreg", "ridge"])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    if not (run_dir / "features.npz").exists():
        print(f"no features.npz in {run_dir} — run extract_bhava_probe_features.py first")
        return 2
    rep = run(run_dir, model=args.model, k=args.k, l2=args.l2, seed=args.seed)
    for lt, blk in rep["by_label_type"].items():
        print(f"  [{lt}] n={blk['n']} -> {blk['verdict']['decision']}")
    print(f"results written to {run_dir/'results.json'}")
    print("Next: python scripts/cg_wrapper_ablation/bhava_probe_report.py", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
