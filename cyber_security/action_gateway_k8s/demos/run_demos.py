"""Run all eighteen Kubernetes enforcement demonstrations against a real cluster.

    python3 demos/run_demos.py

If no control plane is reachable, every scenario is reported SKIPPED (exit 0);
run ``scripts/cluster_up.sh`` first. Exit is non-zero only if a scenario that
ran did not enforce as expected.
"""

from __future__ import annotations

from scenarios import run_all


def main() -> int:
    results = run_all()
    if all(r.get("skipped") for r in results):
        print("SKIPPED: no reachable Kubernetes control plane "
              "(run scripts/cluster_up.sh). Interfaces built; bypass resistance NOT proven.")
        return 0
    width = max(len(r["scenario"]) for r in results)
    bar = "=" * (width + 46)
    print(bar)
    print("Action Gateway K8s — real-cluster enforcement demonstrations")
    print(bar)
    ran = [r for r in results if not r.get("skipped")]
    for r in ran:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"[{flag}] {r['scenario']:<{width}}  {r.get('actual')}")
        print(f"       expected: {r.get('expected')}")
        if r.get("detail"):
            print(f"       note    : {r['detail']}  (audit intact={r.get('audit_intact')})")
    print(bar)
    print(f"{sum(bool(r['passed']) for r in ran)}/{len(ran)} demonstrations enforced as expected")
    return 0 if all(r["passed"] for r in ran) else 1


if __name__ == "__main__":
    raise SystemExit(main())
