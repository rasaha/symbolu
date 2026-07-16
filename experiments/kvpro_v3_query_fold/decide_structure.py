#!/usr/bin/env python3
"""Phase G/H — natural-structure verdict + stop rules + recommendation (CPU-pure).

Ingests the Phase-F method comparison + Phase-E variance for SCALE (primary; xmin
secondary) per model, applies the FROZEN stop rules, and emits a natural-structure
verdict and a single recommendation. Decision is based on OBSERVED data, not on which
representation is easiest to implement. Both Qwen and Llama must show COMPATIBLE
exploitable structure. A representation that saves bytes but does not reduce per-element
hot-path work is NOT sufficient.

Results dir convention (per model tag): <tag>_scale_methods.json, <tag>_scale_variance.json,
<tag>_scale_temporal.json (optional, for the structure label), <tag>_scale_entropy.json (opt).
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Optional

# ---- FROZEN thresholds / stop rules ----
RELFROB_MAX = 0.10          # a method must reconstruct within 10% worst-case layer/head
BYTES_MIN = 40.0            # meaningful metadata reduction
HOTPATH_MIN_PCT = 10.0      # modeled hot-path work reduction floor (work-reducing methods only)

RANK = {"rank1_multiplicative", "rank1_log_additive", "svd_R2", "svd_R4"}
TEMPLATE = {"per_head_template", "per_layer_template"}
COMPRESSION = {"piecewise_const", "kmeans_vq", "channel_baseline_sparse", "codebook", "delta_prev"}
NOT_RUN = "NOT_RUN"


def _load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def _best(methods_json, work_reducing: bool):
    if methods_json is None:
        return None
    cand = []
    for n, m in methods_json["methods"].items():
        if bool(m.get("reduces_per_element_work")) != work_reducing:
            continue
        if m["rel_frob_worst"] <= RELFROB_MAX and (not work_reducing or (m.get("metadata_bytes_saved_pct") or 0) >= BYTES_MIN):
            cand.append((n, m))
    return min(cand, key=lambda nm: nm[1]["rel_frob_worst"]) if cand else None


def _cat(name):
    return "rank" if name in RANK else "template" if name in TEMPLATE else "compression"


def _per_model(results_dir, tag):
    p = lambda s: os.path.join(results_dir, f"{tag}_scale_{s}.json")
    methods, variance = _load(p("methods")), _load(p("variance"))
    temporal, entropy = _load(p("temporal")), _load(p("entropy"))
    work = _best(methods, True)
    comp = _best(methods, False)
    calib = None if variance is None else (variance.get("offline_calibratable_hint")
                                           if variance.get("label") != "NOT_ENOUGH_CAPTURES" else None)
    return {"has_methods": methods is not None, "work": work, "comp": comp, "calibratable": calib,
            "temporal_class": (temporal or {}).get("classification"),
            "entropy_bits": ((entropy or {}).get("global") or {}).get("entropy_bits")}


def decide(results_dir: str, models: List[str]) -> dict:
    pm = {t: _per_model(results_dir, t) for t in models}
    detail = {t: {"work": (pm[t]["work"][0] if pm[t]["work"] else None),
                  "work_cat": (_cat(pm[t]["work"][0]) if pm[t]["work"] else None),
                  "comp": (pm[t]["comp"][0] if pm[t]["comp"] else None),
                  "calibratable": pm[t]["calibratable"],
                  "temporal_class": pm[t]["temporal_class"],
                  "entropy_bits": pm[t]["entropy_bits"]} for t in models}

    if any(not pm[t]["has_methods"] for t in models):
        return _mk("INCONCLUSIVE", "INCONCLUSIVE",
                   "method comparison missing for a model (Phase F NOT_RUN)", detail)

    work_all = all(pm[t]["work"] for t in models)
    cats = {_cat(pm[t]["work"][0]) for t in models if pm[t]["work"]}
    calib_all = all(pm[t]["calibratable"] for t in models)
    calib_known = all(pm[t]["calibratable"] is not None for t in models)

    # STOP RULE: a work-reducing method exists but is prompt-dependent (not calibratable).
    if work_all and calib_known and not calib_all:
        return _mk("STRUCTURE_WEAK", "CLOSE_QUERY_FOLD_NO_STRUCTURE",
                   "a work-reducing representation reconstructs, but it is prompt-dependent "
                   "(not offline-calibratable on both models) — stop.", detail)

    if work_all and (calib_all or not calib_known):
        cal_note = "" if calib_all else " (variance decomposition NOT_RUN — confirm calibratability)"
        if cats == {"rank"}:
            return _mk("STRUCTURE_LOW_RANK", "ADVANCE_EXISTING_QUERY_FOLD",
                       "a rank method reconstructs within tolerance and reduces per-element work on both "
                       "models; the existing QF1/QF2/QF3 candidates target exactly this." + cal_note, detail)
        if cats == {"template"}:
            return _mk("STRUCTURE_CLUSTERED", "ADVANCE_NON_RANK_STRUCTURE",
                       "a shared-template representation (template ID + per-block scalar) is the accurate "
                       "work-reducing structure on both models — a non-rank fold." + cal_note, detail)
        return _mk("STRUCTURE_MIXED", "REVISE_QUERY_FOLD_CANDIDATES",
                   "work-reducing structure exists on both models but the best method differs by model "
                   f"({cats}); revise the candidate set to the shared structure." + cal_note, detail)

    # No work-reducing method passes on both -> is there only byte-compression?
    comp_all = all(pm[t]["comp"] for t in models)
    if comp_all:
        tclasses = {pm[t]["temporal_class"] for t in models}
        label = ("STRUCTURE_TEMPORALLY_STABLE" if tclasses <= {"piecewise_constant_or_slow", "slowly_drifting"}
                 else "STRUCTURE_LOW_ENTROPY")
        return _mk(label, "CLOSE_QUERY_FOLD_NO_STRUCTURE",
                   "only byte-COMPRESSION methods reconstruct accurately (they do NOT reduce per-element "
                   "hot-path work). That is a storage finding, not a query-fold win — stop the query-fold "
                   "line. (A KV-metadata compression track could reuse this.)", detail)

    return _mk("STRUCTURE_WEAK", "CLOSE_QUERY_FOLD_NO_STRUCTURE",
               "no tested representation reconstructs within tolerance on both models while reducing "
               "metadata/work meaningfully — the metadata is effectively unstructured for folding.", detail)


def _mk(structure, rec, reason, detail):
    return {"natural_structure": structure, "recommendation": rec, "reason": reason,
            "frozen": {"rel_frob_max": RELFROB_MAX, "bytes_min": BYTES_MIN, "hotpath_min_pct": HOTPATH_MIN_PCT},
            "per_model": detail}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 natural-structure verdict")
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--models", default="qwen,llama")
    ap.add_argument("--out-json")
    a = ap.parse_args(argv)
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    rep = decide(a.results_dir, models)
    print("=" * 68)
    print(f"NATURAL STRUCTURE: {rep['natural_structure']}")
    print(f"RECOMMENDATION   : {rep['recommendation']}")
    print(f"  {rep['reason']}")
    print("=" * 68)
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
