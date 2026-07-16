#!/usr/bin/env python3
"""Phase E — variance decomposition across prompts / seeds (offline-calibratable?).

The decisive question for query-folding: is the metadata's dominant structure driven
by (layer,head,channel) IDENTITY — which can be calibrated offline and reused during
serving — or by the PROMPT / SEED (input), which cannot? Decomposes total metadata
variance into identity vs prompt vs seed vs block components and reports cross-prompt /
cross-seed profile correlation. Scale in log space (multiplicative); xmin linear.
Needs ≥2 captures (prompts×seeds); reports NOT_ENOUGH otherwise.

  python analyze_variance_sources.py --manifest meta.pt --kind scale --out-json scale_var.json
  python analyze_variance_sources.py --synthetic stable --kind scale     # identity-dominant
"""
from __future__ import annotations

import argparse
import json
from statistics import median, mean
from typing import Dict, List

import torch

try:
    from . import explore_common as EC, synthetic
except ImportError:  # pragma: no cover
    import explore_common as EC  # type: ignore
    import synthetic             # type: ignore


def _var(v: List[float]) -> float:
    if len(v) < 2:
        return 0.0
    m = mean(v)
    return sum((x - m) ** 2 for x in v) / len(v)


def run(manifest: dict, kind: str) -> dict:
    positive = (kind == "scale")
    xf = (lambda M: M.clamp_min(1e-8).log()) if positive else (lambda M: M)
    # identity (layer,head) -> list of (prompt_id, seed, M[b,d])
    by_id: Dict[tuple, List[tuple]] = {}
    for meta, M in EC.iter_heads(manifest, kind):
        by_id.setdefault((meta["layer"], meta["head"]), []).append(
            (meta["prompt_id"], meta["seed"], xf(M)))
    n_caps = len(next(iter(by_id.values())))
    if n_caps < 2:
        return {"model": manifest.get("model"), "kind": kind, "label": "NOT_ENOUGH_CAPTURES",
                "n_captures": n_caps, "note": "variance decomposition needs >= 2 prompt/seed captures."}

    id_means, cap_var, block_var, prompt_var, seed_var = [], [], [], [], []
    prof_corr = []                                        # cross-prompt profile correlation per identity
    for key, caps in by_id.items():
        D = caps[0][2].shape[1]
        for d in range(D):
            allv = torch.cat([M[:, d] for _, _, M in caps])
            id_means.append(allv.mean().item())
            capm = [M[:, d].mean().item() for _, _, M in caps]
            cap_var.append(_var(capm))
            block_var.append(mean([M[:, d].var(unbiased=False).item() for _, _, M in caps]))
            # prompt vs seed split
            byp: Dict[int, List[float]] = {}
            for (pid, _s, M) in caps:
                byp.setdefault(pid, []).append(M[:, d].mean().item())
            prompt_means = [mean(v) for v in byp.values()]
            prompt_var.append(_var(prompt_means))
            seed_var.append(mean([_var(v) for v in byp.values()]))
        # cross-prompt profile correlation (per-channel profile per capture, corr across captures)
        profs = [M.mean(0) for _, _, M in caps]           # each (D,)
        cs = []
        for i in range(len(profs)):
            for j in range(i + 1, len(profs)):
                a, b = profs[i] - profs[i].mean(), profs[j] - profs[j].mean()
                den = (a.norm() * b.norm()).item()
                if den > 1e-12:
                    cs.append(((a * b).sum().item()) / den)
        if cs:
            prof_corr.append((mean(cs), key))

    V_id = _var(id_means)
    V_cap = mean(cap_var); V_block = mean(block_var)
    V_prompt = mean(prompt_var); V_seed = mean(seed_var)
    tot = V_id + V_cap + V_block + 1e-30
    frac = lambda x: round(x / tot, 4)
    corr_vals = [c for c, _ in prof_corr]
    corr_loc = [{"layer": k[0], "head": k[1]} for _, k in prof_corr]
    return {
        "model": manifest.get("model"), "kind": kind, "label": "MEASURED",
        "n_captures": n_caps, "n_prompts": manifest.get("n_prompts"),
        "variance_fraction": {"identity": frac(V_id), "prompt": frac(V_prompt), "seed": frac(V_seed),
                              "prompt_plus_seed": frac(V_cap), "block": frac(V_block)},
        "cross_prompt_profile_corr": EC.agg_worst(corr_vals, corr_loc, worst="min"),
        # calibratable iff the per-channel PROFILE is input-stable (high cross-prompt corr) AND
        # prompt/seed is not a dominant variance source. Block variance is fine (β_b is a
        # per-sequence serving-time scalar, not something to calibrate offline).
        "offline_calibratable_hint": bool(
            (median(corr_vals) if corr_vals else 0.0) >= 0.8 and frac(V_cap) <= 0.35),
        "note": ("identity fraction high + prompt/seed fraction low + high cross-prompt profile corr => "
                 "the structure is input-STABLE and offline-calibratable (query-fold viable). If prompt/"
                 "seed dominates, folding an offline transform into Q is unlikely to generalize."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 metadata variance sources")
    ap.add_argument("--manifest"); ap.add_argument("--kind", choices=["scale", "xmin"], required=True)
    ap.add_argument("--out-json")
    ap.add_argument("--synthetic", choices=["low_rank", "clustered", "piecewise", "random", "stable"])
    a = ap.parse_args(argv)
    man = (synthetic.explore_manifest_synthetic(structure=a.synthetic) if a.synthetic
           else EC.load_explore(a.manifest))
    rep = run(man, a.kind)
    if rep.get("label") == "NOT_ENOUGH_CAPTURES":
        print(f"[{a.kind}] NOT_ENOUGH_CAPTURES (n={rep['n_captures']})")
    else:
        vf = rep["variance_fraction"]
        print(f"[{a.kind}] var: identity={vf['identity']} prompt={vf['prompt']} seed={vf['seed']} "
              f"block={vf['block']} | cross-prompt corr med={rep['cross_prompt_profile_corr']['median']} "
              f"worst={rep['cross_prompt_profile_corr']['worst']} | offline_calibratable={rep['offline_calibratable_hint']}")
    if a.out_json:
        json.dump(rep, open(a.out_json, "w"), indent=2); print(f"  -> {a.out_json}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
