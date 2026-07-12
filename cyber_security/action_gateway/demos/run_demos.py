"""Run all nine end-to-end enforcement demonstrations and print a report.

    python3 demos/run_demos.py

Exit code is non-zero if any demonstration did not enforce as expected.
"""

from __future__ import annotations

import sys

from scenarios import run_all


def main() -> int:
    results = run_all()
    width = max(len(r["scenario"]) for r in results)
    print("=" * (width + 44))
    print("Action Gateway — end-to-end enforcement demonstrations")
    print("=" * (width + 44))
    all_ok = True
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        all_ok = all_ok and r["passed"]
        print(f"[{flag}] {r['scenario']:<{width}}  {r['actual']}")
        print(f"       expected: {r['expected']}")
        print(f"       note    : {r['detail']}  (audit: {r['audit_len']} recs, "
              f"intact={r['audit_intact']})")
    print("=" * (width + 44))
    print(f"{sum(r['passed'] for r in results)}/{len(results)} demonstrations enforced as expected")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
