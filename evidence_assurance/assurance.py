"""Reference EvidenceAssurance component (Phase 13). Composes the layers — provenance, independence,
alignment, counterevidence, freshness, authority — into ONE evidence-state disposition (one of the
eleven in taxonomy.EvidenceState). This is the component the AssertionGate adapter (Phase 14) consumes.

It sees OBSERVED metadata and the layer verdicts only — never the TRUE latent state (anti-circularity;
see GROUND_TRUTH_PROTOCOL.md). Where a check assumes a property is observable (scope inflation), that
assumption is made explicit and is stress-tested under missing metadata in Phase 16.

Design intent vs the Phase-12 baselines:
  * The naive composite blocked overstated-but-supported cases (VERIFIED_WITH_LIMITATIONS) as if they
    were misaligned. Here, a passage that supports the claim but at a *narrower scope* → QUALIFY
    (VERIFIED_WITH_LIMITATIONS), not REJECT — recovering false-block without conceding safety.
  * A single-underlying-source claim (DUPLICATE / all-derive-from-one) → DEPENDENT, which is NOT
    delivered as positively supported. This is what closes correlated-failure escape: an aligned-but-
    wrong claim resting on one source is refused, exactly like a clean dependent claim — because from
    observed metadata they are the same until counterevidence surfaces the contradiction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import provenance, independence, alignment, counterevidence
from .taxonomy import EvidenceState as ES, DELIVERY_EFFECT


@dataclass
class AssuranceResult:
    state: str                       # EvidenceState value
    delivery_effect: str             # AssertionGate delivery implied (pre risk-escalation; adapter finalizes)
    reason_codes: List[str] = field(default_factory=list)
    layers: Dict[str, Any] = field(default_factory=dict)


def _authority_ok(case: Dict[str, Any]) -> bool:
    """Authority is disqualifying only for high/critical-risk decisions (matches the corpus gate)."""
    classes = case.get("observed_authority_classes", []) or []
    dominant_low = bool(classes) and classes[0] == "low"
    high_risk = case.get("risk_class") in ("high", "critical")
    return not (dominant_low and high_risk)


def _fresh_ok(case: Dict[str, Any]) -> bool:
    years = case.get("observed_publication_years", []) or []
    return not (years and max(years) < 2018)


LAYERS = ("alignment", "counterevidence", "provenance", "authority", "freshness", "independence")
ALL_LAYERS = frozenset(LAYERS)


def assess(case: Dict[str, Any], enabled: frozenset = ALL_LAYERS) -> AssuranceResult:
    """Compose the layers into one disposition. `enabled` selects which layers are active — the full
    set by default; the ablation study (Phase 18) removes one layer at a time to measure its weight."""
    prov = provenance.analyze(case)
    iv = independence.assess(case)
    al = alignment.assess(case)
    cv = counterevidence.search(case)
    codes: List[str] = []
    layers = {
        "provenance_confidence": prov.provenance_confidence,
        "effective_independent": iv.effective_independent,
        "independence_verdict": iv.verdict,
        "aligned": al.aligned,
        "passage_supports_claim": al.passage_supports_claim,
        "scope_ok": al.scope_ok,
        "counter_found": cv.found,
        "counter_false_conflict": cv.false_conflict,
        "authority_ok": _authority_ok(case),
        "fresh_ok": _fresh_ok(case),
    }

    def result(state: ES) -> AssuranceResult:
        return AssuranceResult(state=state.value, delivery_effect=DELIVERY_EFFECT[state],
                               reason_codes=codes, layers=layers)

    # --- disposition precedence (most severe / safety-critical first) ---------------------------

    # 1. Wrong passage / population / jurisdiction — the cited evidence does not support THIS claim.
    #    (Scope inflation alone is handled later as a limitation, not a misalignment. Old publication
    #    years are staleness, handled at step 5 — not counted here as temporal misalignment, which
    #    would double-count the same year signal and swallow every STALE case.)
    if "alignment" in enabled and (not al.passage_supports_claim or not al.jurisdiction_ok):
        codes.extend(c for c in al.reason_codes if c != "EA.TEMPORAL_MISMATCH")
        return result(ES.MISALIGNED)

    # 2. Credible counterevidence found (not the irrelevant/false-conflict noise) → conflicted.
    if "counterevidence" in enabled and cv.found:
        codes.append("EA.COUNTEREVIDENCE_FOUND")
        return result(ES.CONFLICTED)

    # 3. Provenance cannot be trusted (fabricated diversity / missing provenance) → cannot decide.
    #    Independence returns UNKNOWN exactly here; never certify from untrusted metadata.
    if "provenance" in enabled and (iv.verdict == "UNKNOWN" or prov.missing_provenance):
        codes.append("EA.PROVENANCE_UNTRUSTED")
        return result(ES.INDETERMINATE)

    # 4. Source not authoritative for a high-risk decision.
    if "authority" in enabled and not _authority_ok(case):
        codes.append("EA.AUTHORITY_MISMATCH")
        return result(ES.AUTHORITY_MISMATCH)

    # 5. Evidence outdated / superseded.
    if "freshness" in enabled and (not _fresh_ok(case) or prov.superseded_or_stale):
        codes.append("EA.STALE")
        return result(ES.STALE)

    # 6. Apparent corroboration is not independent — one underlying source. This is the correlated-
    #    failure gate: an aligned-but-wrong claim on a single source lands here too, and DEPENDENT is
    #    NOT delivered as positively supported, so it does not escape. (Clean-dependent-correct lands
    #    here as well — and its gold IS DEPENDENT, so that is correct, not a false block.)
    if "independence" in enabled and iv.verdict == "DUPLICATE":
        codes.append("EA.DEPENDENT_SINGLE_SOURCE")
        return result(ES.DEPENDENT)

    # 7. Not a duplicate, but too little genuine independent support to certify.
    if "independence" in enabled and iv.effective_independent <= 1.0:
        codes.append("EA.INSUFFICIENT_INDEPENDENCE")
        return result(ES.INSUFFICIENT)

    # 8. Supported, but the claim is broader than the evidence — deliver qualified, do not refuse.
    if not al.scope_ok:
        codes.append("EA.SCOPE_LIMITED")
        return result(ES.VERIFIED_WITH_LIMITATIONS)

    # 9. Aligned, independent, authoritative, fresh, not contradicted → verified.
    return result(ES.VERIFIED)
