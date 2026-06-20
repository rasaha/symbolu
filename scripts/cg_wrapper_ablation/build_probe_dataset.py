#!/usr/bin/env python3
"""build_probe_dataset.py — turn a prompt POOL into a LABELED probe dataset by generate+score.

Each pool row has a prompt + an objective scorer spec. This runs the model, generates an answer,
scores it (exact-match / constraint / json), and emits a probe JSONL row with label = 1 if the
generation was correct/valid else 0. That labeled JSONL then feeds extract_bhava_probe_features.py.

The label is a generation-quality outcome (the model's OWN output scored objectively) — so the
probe asks: does the model's internal state while reading the prompt predict whether it will
succeed? Labels are generation-quality only; the pool carries no governance labels.

Requires torch + a checkpoint; skips cleanly (exit 0) if absent. GPU portion.

Env: MODEL_ID, CG_CHECKPOINT, DEVICE, DTYPE, MAX_NEW_TOKENS.
Usage:
  CG_CHECKPOINT=/path/best_model.pt python scripts/cg_wrapper_ablation/build_probe_dataset.py \
     --pool scripts/cg_wrapper_ablation/probe_pool/pool.jsonl \
     --out scripts/cg_wrapper_ablation/probe_data/probe_real.jsonl
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from cg_ablation import metrics as M  # noqa: E402


def score_generation(scorer: dict, text: str) -> int:
    """Objective 0/1 label from a scorer spec + a generation."""
    kind = scorer.get("kind")
    if kind == "exact_match":
        return int(M.exact_match(text, int(scorer["answer"])))
    if kind == "constraint":
        return int(all(M.constraint_satisfied(text, c) for c in scorer["constraints"]))
    if kind == "json":
        return int(M.json_has_keys(text, scorer["required_keys"]))
    return 0


def _read_pool(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=str(Path(__file__).resolve().parent / "probe_pool" / "pool.jsonl"))
    ap.add_argument("--out", required=True, help="output labeled probe JSONL")
    ap.add_argument("--max-examples", type=int, default=0)
    args = ap.parse_args()

    pool = _read_pool(Path(args.pool))
    if args.max_examples:
        pool = pool[: args.max_examples]

    try:
        import torch  # noqa: F401
    except ImportError:
        print("[skip] torch unavailable — generation is GPU-only. Nothing written.")
        return 0
    from cg_ablation.runtime import parse_env, build_wrapper, generate
    from cg_ablation.arms import ARMS_BY_NAME

    cfg = parse_env()
    if not cfg.checkpoint or not Path(cfg.checkpoint).exists():
        print(f"[skip] CG_CHECKPOINT not set or missing ({cfg.checkpoint}). Nothing written.")
        return 0

    wrapper, tok = build_wrapper(cfg)
    base_arm = ARMS_BY_NAME["A_base"]   # label = base model's own success (architecture-neutral)

    out_rows = []
    pos = Counter(); tot = Counter()
    for i, r in enumerate(pool):
        g = generate(wrapper, tok, r["prompt"], base_arm,
                     max_new_tokens=cfg.max_new_tokens, temperature=0.0, seed=0)
        label = score_generation(r["scorer"], g["text"])
        lt = r["label_type"]
        tot[lt] += 1; pos[lt] += label
        out_rows.append({
            "id": r["id"], "prompt": r["prompt"], "expected": str(r["scorer"]),
            "label": label, "label_type": lt,
            "metadata": {"generation": g["text"][:200]},
        })
        if (i + 1) % 25 == 0:
            print(f"  scored {i+1}/{len(pool)}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in out_rows:
            f.write(json.dumps(row) + "\n")

    print(f"== wrote {len(out_rows)} labeled rows to {out_path} ==")
    print("class balance per label_type (pos/total):")
    for lt in sorted(tot):
        p, t = pos[lt], tot[lt]
        flag = "OK" if (p >= 8 and (t - p) >= 8) else "<8 per class -> INSUFFICIENT for probe"
        print(f"  {lt:<24} {p}/{t}  (neg={t-p})  {flag}")
    print("Next: extract_bhava_probe_features.py --data", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
