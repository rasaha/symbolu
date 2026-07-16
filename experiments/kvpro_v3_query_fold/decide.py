#!/usr/bin/env python3
"""Phase G/I — pre-registered gates + verdict (CPU-pure).

Combines the per-model structural (Phase C/D), attention (Phase F), systems (Phase G),
and — when present — quality (Phase H) results, applies the FROZEN thresholds, and
emits exactly one verdict. BOTH models must pass every gate. Thresholds are frozen
constants (README) — NOT the discredited absolute offline thresholds, and never
weakened after seeing results.

GO requires structure + attention + systems + QUALITY to pass on both models. Without
quality, the most a candidate reaches is INCONCLUSIVE (quality pending). If the
structural decomposition is weak on either model, the verdict is NO_GO_STRUCTURE and
the later phases are irrelevant.

Results dir convention (per model tag, e.g. qwen / llama):
  <tag>_scale_structure.json  <tag>_xmin_structure.json  <tag>_attention.json
  <tag>_quality.json (optional)
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Optional

try:
    from . import accounting
except ImportError:  # pragma: no cover
    import accounting  # type: ignore

# ---- FROZEN thresholds (pre-registered; see README) ----
STRUCT = {"rel_frob_worst_max": 0.10, "var_explained_median_min": 0.95, "channel_bias_worst_max": 0.05}
ATTN = {"attn_out_cos_delta_min": -0.005, "softmax_kl_ratio_max": 1.5, "topk_overlap_delta_min": -0.02}
SYS = {"metadata_bytes_saved_pct_min": 25.0, "modeled_kpath_reduction_pct_min": 12.0}
# quality gate: baseline-relative vs current affine (per driver's own summary schema).
QUALITY = {"needle_min_frac_of_affine": 1.0, "mmlu_max_drop_pts": 1.0}

# candidate -> required structural decompositions (model name in the structure JSON).
CAND_REQ: Dict[str, Dict[str, str]] = {
    "QF1": {"scale": "rank1_mult"},
    "QF2": {"scale": "rank1_mult", "xmin": "additive"},
    "QF3": {"scale": "svd_R2"},
}
PREFERRED_ORDER = ["QF1", "QF2", "QF3"]     # cheapest-fold first
NOT_RUN = "NOT_RUN"


def _load(path: Optional[str]):
    if not path or not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def _struct_pass(models_json: dict, model_key: str) -> Optional[bool]:
    """One decomposition (e.g. rank1_mult) against the frozen structural thresholds."""
    if models_json is None:
        return None
    m = (models_json.get("models") or {}).get(model_key)
    if m is None:
        return None
    return bool(m["rel_frob_worst"] <= STRUCT["rel_frob_worst_max"]
                and m["var_explained_median"] >= STRUCT["var_explained_median_min"]
                and m["max_rel_channel_bias_worst"] <= STRUCT["channel_bias_worst_max"])


def gate_structural(scale_json: dict, xmin_json: dict) -> Dict[str, object]:
    """Per candidate: does its required decomposition clear the structural gate?"""
    out = {}
    for cand, req in CAND_REQ.items():
        checks, ok, missing = {}, True, False
        s = _struct_pass(scale_json, req["scale"])
        checks[f"scale:{req['scale']}"] = NOT_RUN if s is None else s
        if s is None:
            missing = True
        else:
            ok = ok and s
        if "xmin" in req:
            x = _struct_pass(xmin_json, req["xmin"])
            checks[f"xmin:{req['xmin']}"] = NOT_RUN if x is None else x
            if x is None:
                missing = True
            else:
                ok = ok and x
        out[cand] = {"pass": (None if missing else ok), "checks": checks}
    return out


def gate_attention(attn_json: dict) -> Dict[str, object]:
    if attn_json is None:
        return {c: {"pass": None} for c in CAND_REQ}
    rel = attn_json.get("relative_to_affine", {})
    out = {}
    for cand in CAND_REQ:
        r = rel.get(cand)
        if r is None:
            out[cand] = {"pass": None}
            continue
        checks = {
            "attn_out_cos_delta": (r["attn_out_cos_minus_affine"] >= ATTN["attn_out_cos_delta_min"]),
            "softmax_kl_ratio": (r["softmax_kl_ratio_to_affine"] <= ATTN["softmax_kl_ratio_max"]),
            "topk_overlap_delta": (r["topk_overlap_minus_affine"] >= ATTN["topk_overlap_delta_min"]),
        }
        out[cand] = {"pass": all(checks.values()), "checks": checks, "values": r}
    return out


def gate_systems() -> Dict[str, object]:
    out = {}
    for cand in CAND_REQ:
        sv = accounting.systems_value(cand)
        out[cand] = {
            "pass": bool(sv["metadata_bytes_saved_pct"] >= SYS["metadata_bytes_saved_pct_min"]
                         and sv["modeled_kpath_reduction_pct"] >= SYS["modeled_kpath_reduction_pct_min"]
                         and sv["per_element_reconstruct_removed"]),
            "metadata_bytes_saved_pct": sv["metadata_bytes_saved_pct"],
            "modeled_kpath_reduction_pct": sv["modeled_kpath_reduction_pct"],
        }
    return out


def gate_quality(quality_json: dict) -> Dict[str, object]:
    """Baseline-relative quality (needle keeps ≥ affine's; MMLU within margin). The
    driver's summary is expected as {candidate: {needle_frac_of_affine, mmlu_drop_pts}}."""
    if quality_json is None:
        return {c: {"pass": None} for c in CAND_REQ}
    out = {}
    per = quality_json.get("per_candidate", {})
    for cand in CAND_REQ:
        q = per.get(cand)
        if q is None:
            out[cand] = {"pass": None}
            continue
        ok = (q.get("needle_frac_of_affine", 0) >= QUALITY["needle_min_frac_of_affine"]
              and q.get("mmlu_drop_pts", 99) <= QUALITY["mmlu_max_drop_pts"])
        out[cand] = {"pass": bool(ok), "values": q}
    return out


def _both(g_qwen: dict, g_llama: dict, cand: str):
    """AND the per-model gate for one candidate. None (NOT_RUN) is contagious."""
    a = g_qwen.get(cand, {}).get("pass")
    b = g_llama.get(cand, {}).get("pass")
    if a is None or b is None:
        return None
    return bool(a and b)


def decide(results_dir: str, models: List[str], require_quality: bool = True) -> dict:
    per_model = {}
    for tag in models:
        p = lambda name: os.path.join(results_dir, f"{tag}_{name}.json")
        per_model[tag] = {
            "structural": gate_structural(_load(p("scale_structure")), _load(p("xmin_structure"))),
            "attention": gate_attention(_load(p("attention"))),
            "quality": gate_quality(_load(p("quality"))),
        }
    systems = gate_systems()

    # Combine across models per phase.
    def combine(phase):
        return {c: _both(per_model[models[0]][phase], per_model[models[1]][phase], c)
                for c in CAND_REQ} if len(models) == 2 else \
               {c: per_model[models[0]][phase].get(c, {}).get("pass") for c in CAND_REQ}

    struct = combine("structural")
    attn = combine("attention")
    qual = combine("quality")

    detail = {"per_model": per_model, "systems": systems,
              "combined": {"structural": struct, "attention": attn, "quality": qual}}

    # ---- verdict precedence ----
    # 1. structure availability
    if all(v is None for v in struct.values()):
        return _verdict("INCONCLUSIVE", "no structural results found (Phase C/D NOT_RUN)", detail)
    struct_pass = [c for c, v in struct.items() if v is True]
    if not struct_pass:
        if any(v is False for v in struct.values()):
            return _verdict("NO_GO_STRUCTURE",
                            "no candidate's required decomposition cleared the structural gate on both models",
                            detail)
        return _verdict("INCONCLUSIVE", "structural results incomplete (some NOT_RUN)", detail)

    # 2. attention
    if all(attn[c] is None for c in struct_pass):
        return _verdict("INCONCLUSIVE", "structure passed; attention (Phase F) NOT_RUN", detail)
    attn_pass = [c for c in struct_pass if attn[c] is True]
    if not attn_pass:
        if any(attn[c] is False for c in struct_pass):
            return _verdict("NO_GO_ATTENTION_ERROR",
                            "structure-surviving candidates exceed the baseline-relative attention gate",
                            detail)
        return _verdict("INCONCLUSIVE", "attention results incomplete (some NOT_RUN)", detail)

    # 3. systems
    sys_pass = [c for c in attn_pass if systems[c]["pass"]]
    if not sys_pass:
        return _verdict("NO_GO_SYSTEMS_VALUE",
                        "attention-surviving candidates do not clear the modeled systems-value gate",
                        detail)

    # 4. quality (required for GO)
    if require_quality:
        if all(qual[c] is None for c in sys_pass):
            return _verdict("INCONCLUSIVE",
                            "structure+attention+systems PASS; quality (Phase H) NOT_RUN — run it before GO",
                            detail, survivors=sys_pass)
        qual_pass = [c for c in sys_pass if qual[c] is True]
        if not qual_pass:
            if any(qual[c] is False for c in sys_pass):
                return _verdict("NO_GO_QUALITY",
                                "a surviving candidate failed the quality gate on at least one model", detail)
            return _verdict("INCONCLUSIVE", "quality results incomplete (some NOT_RUN)", detail)
        best = next((c for c in PREFERRED_ORDER if c in qual_pass), qual_pass[0])
        v = "GO_QUERY_FOLD_KERNEL_PROTOTYPE" if best in ("QF1", "QF2") else "GO_WITH_MODIFICATION"
        return _verdict(v, f"{best} passes structure+attention+systems+quality on both models "
                        "(prototype kernel only — not a throughput claim)", detail, survivors=qual_pass, best=best)
    # structure-only / no-quality run
    return _verdict("INCONCLUSIVE",
                    f"structure+attention+systems PASS for {sys_pass}; quality not required this run",
                    detail, survivors=sys_pass)


def _verdict(v, reason, detail, survivors=None, best=None):
    return {"verdict": v, "reason": reason, "survivors": survivors or [], "best_candidate": best,
            "frozen_thresholds": {"STRUCT": STRUCT, "ATTN": ATTN, "SYS": SYS, "QUALITY": QUALITY},
            "detail": detail}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 query-fold verdict")
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--models", default="qwen,llama", help="model tags (both must pass)")
    ap.add_argument("--structure-only", action="store_true", help="no quality required")
    ap.add_argument("--out-json")
    a = ap.parse_args(argv)
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    rep = decide(a.results_dir, models, require_quality=not a.structure_only)
    print("=" * 66)
    print(f"VERDICT: {rep['verdict']}")
    print(f"  {rep['reason']}")
    if rep["survivors"]:
        print(f"  survivors: {rep['survivors']}  best: {rep['best_candidate']}")
    print("=" * 66)
    if a.out_json:
        with open(a.out_json, "w") as fh:
            json.dump(rep, fh, indent=2)
        print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
