"""Run the 25 adversarial cases (Phase 17) through every method; report which silently alter meaning."""
from __future__ import annotations

import json
import os
from collections import Counter

from . import adversarial, baselines, validation
from .taxonomy import Disposition


def run() -> dict:
    cases = adversarial.as_examples()
    rows = []
    for name, fn in baselines.BASELINES.items():
        silent_drift = 0
        by_dim = []
        for e in cases:
            produced = fn(e)
            aud = validation.audit(e, produced)
            disp = aud["example_disposition"]
            if disp not in (Disposition.VALID.value, Disposition.VALID_WITH_ALTERNATIVES.value):
                silent_drift += 1
                by_dim.append(e["attack_dimension"])
        rows.append({"method": name, "silent_drift": silent_drift, "n": len(cases),
                     "drift_rate": round(silent_drift / len(cases), 4),
                     "dims_hit": dict(Counter(by_dim))})
    return {"n_cases": len(cases), "results": rows}


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "adversarial.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print(f"adversarial cases: {r['n_cases']}")
    print(f"{'method':24} {'silent_drift':>12} {'rate':>6}")
    for row in sorted(r["results"], key=lambda x: x["drift_rate"]):
        print(f"{row['method']:24} {row['silent_drift']:>12} {row['drift_rate']:>6.2f}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
