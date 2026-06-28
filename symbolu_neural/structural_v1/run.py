"""Stage A entrypoint: run the gate, print + write the deterministic report.

Usage:
    python -m symbolu_neural.structural_v1.run [output_path.md]

No LLM, no network, no policy. Fixed seeds; fully deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .gate import run_stage_a
from .report import render_report


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (
        Path(__file__).resolve().parent / "STAGE_A_STRUCTURAL_REPORT.md")
    result = run_stage_a()
    md = render_report(result)
    out.write_text(md)
    print(md)
    print(f"\n[written] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
