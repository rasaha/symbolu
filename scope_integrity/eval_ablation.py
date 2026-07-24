"""Ablation (M5). Remove each propagation element / capability from the winning gated extension (H)
and measure the effect on BOTH corpora (general = deployment reality, scope = concentrated). Identify
the minimum load-bearing rule set. Deterministic. Writes eval_results/ablation.json.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from claim_integrity import dataset as cdata, downstream
from . import dataset as sdata, variants
from .variants import SCOPE_ELEMENTS


def _score(exs, fn):
    d = downstream.score_method(exs, fn)
    return {"unsafe": d["unsafe_delivery_rate"], "false_rej": d["false_rejection_rate"],
            "evq": d["evidence_query_altered_rate"]}


def run() -> dict:
    gen = [asdict(e) for e in cdata.all_examples()]
    sc = [asdict(e) for e in sdata.all_examples()]

    def H(enabled=SCOPE_ELEMENTS, resolve_refs=True, gated=True):
        return lambda e: variants.variant_h_integrated(e, enabled=enabled,
                                                        resolve_refs=resolve_refs, gated=gated)

    configs = {"FULL": H()}
    for el in SCOPE_ELEMENTS:
        configs[f"-{el}"] = H(enabled=SCOPE_ELEMENTS - {el})
    configs["-reference_resolution"] = H(resolve_refs=False)
    configs["-gating (ungated)"] = H(gated=False)

    out = {"scope_elements": sorted(SCOPE_ELEMENTS), "general": {}, "scope": {}}
    for name, fn in configs.items():
        out["general"][name] = _score(gen, fn)
        out["scope"][name] = _score(sc, fn)
    return out


def main() -> None:
    r = run()
    o = os.path.join(os.path.dirname(__file__), "eval_results", "ablation.json")
    os.makedirs(os.path.dirname(o), exist_ok=True)
    with open(o, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print("Ablation - remove one capability from the gated extension (H).")
    print("general corpus is the deployment reality (baseline current=0.068 unsafe).\n")
    print(f"  {'config':26} {'gen_unsafe':>10} {'gen_evq':>8} {'sc_unsafe':>10} {'sc_evq':>7}")
    for name in r["general"]:
        g, s = r["general"][name], r["scope"][name]
        print(f"  {name:26} {g['unsafe']:>10.4f} {g['evq']:>8.4f} {s['unsafe']:>10.4f} {s['evq']:>7.4f}")
    print(f"\nwrote {o}")


if __name__ == "__main__":
    main()
