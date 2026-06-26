"""Build a small char-level corpus from in-repo English prose (no downloads).

Concatenates a curated set of Markdown files into one corpus.txt. This keeps the
experiment offline and reproducible. Pass --inputs to override.

    python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt
"""
from __future__ import annotations

import argparse
import glob
import os

DEFAULT_INPUTS = [
    "README.md",
    "HYBRID_LLM_VC_BRIEF.md",
    "AGENTIC_FRAMEWORK_VC_BRIEF.md",
    "docs/SYMBOL_U_TECHNICAL_RESEARCH_SPECIFICATION.md",
    "symbolu_neural/README.md",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="*", default=None,
                    help="files or globs; default = curated repo md set")
    ap.add_argument("--out", default="data/clean_lm/corpus.txt")
    ap.add_argument("--max-chars", type=int, default=1_200_000)
    args = ap.parse_args()

    patterns = args.inputs or DEFAULT_INPUTS
    files: list[str] = []
    for p in patterns:
        files.extend(sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p])
    parts, total = [], 0
    for fp in files:
        if not os.path.exists(fp):
            print(f"  skip (missing): {fp}"); continue
        with open(fp, encoding="utf-8", errors="ignore") as f:
            t = f.read()
        parts.append(t); total += len(t)
        print(f"  + {fp} ({len(t)} chars)")
        if total >= args.max_chars:
            break
    corpus = ("\n\n".join(parts))[: args.max_chars]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(corpus)
    print(f"wrote {len(corpus)} chars, {len(set(corpus))} unique -> {args.out}")


if __name__ == "__main__":
    main()
