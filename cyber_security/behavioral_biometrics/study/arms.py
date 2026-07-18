"""Frozen fair comparison arms + their feature builders.

Equalization: every arm is scored by the SAME identity runner, on the SAME
participants/trials/splits, with the SAME preprocessing and prototype model family.
An arm is never credited for simply receiving more modalities or more parameters — the
coupling arms add only the coupling statistic slots, and the BCVF/fusion arms are
capacity-matched by construction (see bcvf.py / fusion.py).
"""

from __future__ import annotations

from typing import Callable, Dict, List

from cyber_security.behavioral_biometrics import baselines

_STATS = ("xcorr_max_abs", "xcorr_zero", "correlogram_peak", "cca_mean_corr")

# Simple feature-builder arms (scored directly by the identity runner).
SIMPLE_ARMS = ("K", "P", "T", "M", "MM", "MM_SHUFFLED", "MM_COUPLING",
               "MM_COUPLING_CONTEXT")
# Arms produced by dedicated machinery (bcvf.py / fusion.py) and the final selection.
SPECIAL_ARMS = ("MM_BCVF", "MM_BCVF_NO_DISAGREEMENT", "FULL")
ALL_ARMS = SIMPLE_ARMS + SPECIAL_ARMS

_MODALITY_PREFIX = {"K": "kbd", "P": "ptr", "T": "touch", "M": "motion"}


def _coupling(record: Dict, variant: str) -> Dict[str, float]:
    c = record.get("coupling", {})
    if not c.get("coupling_available"):
        return {}
    out = {}
    for st in _STATS:
        if variant == "real":
            out[f"cpl.{st}"] = c.get(st, 0.0)
        elif variant == "shuf":
            out[f"cpl.{st}"] = c.get(f"{st}__shuf", 0.0)
        elif variant == "context":   # context-conditioned = real residualized vs context-matched
            out[f"cpl.{st}"] = c.get(st, 0.0) - c.get(f"{st}__ctxm", 0.0)
    return out


def builder_for(arm: str) -> Callable[[Dict], Dict[str, float]]:
    if arm in _MODALITY_PREFIX:
        return lambda r, a=arm: baselines.build_modality(r, _MODALITY_PREFIX[a])
    if arm == "MM":
        return baselines.build_marginal
    if arm == "MM_SHUFFLED":
        return lambda r: {**baselines.build_marginal(r), **_coupling(r, "shuf")}
    if arm == "MM_COUPLING":
        return lambda r: {**baselines.build_marginal(r), **_coupling(r, "real")}
    if arm == "MM_COUPLING_CONTEXT":
        return lambda r: {**baselines.build_marginal(r), **_coupling(r, "context")}
    raise ValueError(f"{arm} is not a simple feature-builder arm")


def available_modalities(records: List[Dict]) -> List[str]:
    """Which single-modality arms are populated in this cohort (fair availability)."""
    present = set()
    for r in records:
        for k in r.get("marginal", {}):
            if "." in k:
                present.add(k.split(".", 1)[0])
    return [a for a, pref in _MODALITY_PREFIX.items() if pref in present]
