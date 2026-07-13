"""Mechanical verdict with a hard data-origin lock.

Synthetic/mock corpora may ONLY emit a no-scientific-verdict result. The scientific
verdict logic below is implemented and unit-tested so that, given real
provenance-documented context, it would fire — but it is gated behind
``origin.run_is_scientific`` and never emitted for the authored fixtures shipped
here. Thresholds are the preregistered constants (see PREREGISTRATION.md); they are
NOT tuned against results.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import origin

# ---- preregistered thresholds (mirror PREREGISTRATION.md; frozen) ----
MIN_P0_RECALL = 1.0                 # never drop a truly critical unit
MIN_DEPLOYABLE_CEILING = 0.25       # need >=25% token removal to be worthwhile
MAX_EXTRACTOR_INSTABILITY = 0.10
MAX_INTERACTION_MISS = 0.05
MIN_ORACLE_CEILING_NOT_DENSE = 0.40  # >60% truly critical => intrinsically dense
# economic min lives in economics.EconomicAssumptions.min_net_savings_ratio

# ---- scientific verdicts ----
ABLATION_OPPORTUNITY_SUPPORTED = "ABLATION_OPPORTUNITY_SUPPORTED"
DETECTOR_PRECISION_BOTTLENECK = "DETECTOR_PRECISION_BOTTLENECK"
CONTEXT_INTRINSICALLY_DENSE = "CONTEXT_INTRINSICALLY_DENSE"
EXTRACTOR_NOT_RELIABLE = "EXTRACTOR_NOT_RELIABLE"
SINGLE_ABLATION_INADEQUATE = "SINGLE_ABLATION_INADEQUATE"
ECONOMICS_NOT_SUPPORTED = "ECONOMICS_NOT_SUPPORTED"
NOT_ELIGIBLE = "NOT_ELIGIBLE"


@dataclass
class Verdict:
    verdict: str
    scientific: bool
    pipeline_path_verified: bool
    indicative_scientific_verdict: str   # what it WOULD be (non-authoritative on synthetic)
    rationale: str


def _scientific_verdict(agg, econ) -> tuple:
    """Return (verdict, rationale) from metrics + economics. Precedence-ordered."""
    if agg.n_contexts == 0 or agg.total_units == 0:
        return NOT_ELIGIBLE, "no usable contexts/units"
    if agg.extractor_instability_rate > MAX_EXTRACTOR_INSTABILITY:
        return (EXTRACTOR_NOT_RELIABLE,
                f"extractor instability {agg.extractor_instability_rate:.2f} > {MAX_EXTRACTOR_INSTABILITY}")
    if agg.interaction_miss_rate > MAX_INTERACTION_MISS:
        return (SINGLE_ABLATION_INADEQUATE,
                f"interaction miss {agg.interaction_miss_rate:.2f} > {MAX_INTERACTION_MISS}")
    if agg.oracle_ceiling < MIN_ORACLE_CEILING_NOT_DENSE:
        return (CONTEXT_INTRINSICALLY_DENSE,
                f"true critical fraction {agg.f_critical_union:.2f} too high "
                f"(oracle ceiling {agg.oracle_ceiling:.2f} < {MIN_ORACLE_CEILING_NOT_DENSE})")
    if agg.recall_p0 < MIN_P0_RECALL or agg.deployable_ceiling < MIN_DEPLOYABLE_CEILING:
        return (DETECTOR_PRECISION_BOTTLENECK,
                f"recall {agg.recall_p0:.2f} (need {MIN_P0_RECALL}) / deployable ceiling "
                f"{agg.deployable_ceiling:.2f} (need {MIN_DEPLOYABLE_CEILING}); detection must improve")
    if not econ.clears_threshold:
        return (ECONOMICS_NOT_SUPPORTED,
                f"cache-adjusted savings {econ.cache_adjusted_savings_ratio:.2f} < "
                f"{econ.assumptions.min_net_savings_ratio}")
    return (ABLATION_OPPORTUNITY_SUPPORTED,
            "critical fraction small, recall met, ceiling and economics clear thresholds")


def decide(agg, econ, origins) -> Verdict:
    origins = list(origins)
    indicative, rationale = _scientific_verdict(agg, econ)
    if origin.run_is_scientific(origins):
        return Verdict(verdict=indicative, scientific=True, pipeline_path_verified=True,
                       indicative_scientific_verdict=indicative, rationale=rationale)
    locked = origin.locked_verdict(origins)
    return Verdict(
        verdict=locked, scientific=False, pipeline_path_verified=True,
        indicative_scientific_verdict=indicative,
        rationale=("synthetic/mock corpus: scientific verdict locked. "
                   f"Indicative-only (NON-AUTHORITATIVE): {indicative} — {rationale}"))
