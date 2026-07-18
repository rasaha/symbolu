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

# ---- naturalistic-corpus verdicts (distinct from synthetic lock) ----
PUBLIC_CORPUS_OPPORTUNITY_SUPPORTED = "PUBLIC_CORPUS_OPPORTUNITY_SUPPORTED"
AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED = "AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED"
MIXED_BY_DOMAIN = "MIXED_BY_DOMAIN"
# NOTE: REAL_CUSTOMER_VALIDATED is intentionally NOT defined and must never be emitted.
_SUPPORTED_BY_PARTITION = {
    origin.PUBLIC_NATURALISTIC: PUBLIC_CORPUS_OPPORTUNITY_SUPPORTED,
    origin.AUTHORED_REALISTIC: AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED,
}


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


# never-emit guard: no code path may produce this label
REAL_CUSTOMER_VALIDATED_FORBIDDEN = "REAL_CUSTOMER_VALIDATED"


def _domain_supported(per_domain, econ) -> dict:
    """Per-domain base verdict (supported vs a specific failure)."""
    out = {}
    for dom, dagg in per_domain.items():
        v, _ = _scientific_verdict(dagg, econ)
        out[dom] = v
    return out


def decide_naturalistic(agg, econ, per_domain, partition_label) -> Verdict:
    """Corpus-level verdict for a naturalistic partition.

    Emits PUBLIC_/AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED when the corpus clears all
    gates, a specific failure label when it doesn't, or MIXED_BY_DOMAIN when domains
    disagree (some supportable, some dense/bottlenecked). NEVER emits
    REAL_CUSTOMER_VALIDATED — naturalistic data is not customer operational data.
    """
    base, rationale = _scientific_verdict(agg, econ)
    dom_v = _domain_supported(per_domain, econ)
    supportable = {d for d, v in dom_v.items() if v == ABLATION_OPPORTUNITY_SUPPORTED}
    failing = {d for d, v in dom_v.items() if v != ABLATION_OPPORTUNITY_SUPPORTED}

    # Domain heterogeneity is reported, not averaged away: if some domains are
    # supportable while others are not, that IS the finding — even when the
    # aggregate happens to pass or fail a single gate.
    if supportable and failing:
        verdict = MIXED_BY_DOMAIN
        rationale = (f"domains supportable: {sorted(supportable)}; "
                     f"not supportable: {sorted(failing)}. Aggregate: {base} — {rationale}")
    elif base == ABLATION_OPPORTUNITY_SUPPORTED:
        verdict = _SUPPORTED_BY_PARTITION.get(partition_label, base)
    else:
        verdict = base   # a specific corpus-wide failure label

    return Verdict(
        verdict=verdict, scientific=False, pipeline_path_verified=True,
        indicative_scientific_verdict=base,
        rationale=(f"[{partition_label}] naturalistic (NOT customer data; cannot emit "
                   f"REAL_CUSTOMER_VALIDATED). {rationale}"))
