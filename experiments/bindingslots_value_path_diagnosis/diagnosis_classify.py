#!/usr/bin/env python3
"""Mechanical per-seed diagnosis rules (§14). Torch-free and pure so it is unit-testable and so the
verdict is a deterministic function of the committed measurements.

Thresholds are FROZEN here and mirrored in preregistration.json; they are set from the read path's
structure and from control runs (clean formers / A+), NOT from the failure exemplars.
"""
from __future__ import annotations

# ---- frozen decision constants (preregistered; not tuned on failure seeds) ----
CHANCE = 1.0 / 48                 # N_VAL classes
DECODABLE_MIN = 0.50             # linear-probe test acc counts as "linearly decodable" (>> chance)
MATERIAL_DROP = 0.20             # postwrite->query decodability loss counted as "material"
RETRIEVAL_PRESENT_MIN = 0.50    # ordinary needle acc on the failed eval examples at/above -> present
RETRIEVAL_FAILS_MAX = 0.10      # ordinary needle acc at/below -> "ordinary retrieval fails"
RECOVER_MIN = 0.50              # oracle needle acc at/above -> "restores/recovers retrieval"
CONFLICT_COS = -0.10            # LM-vs-(persist|teacher) cosine at/below -> materially negative
CONTROL_GAP = 0.15             # failed-seed conflict must exceed clean control by this margin

VALUE_PATH_CATEGORIES = [
    "STORAGE_VALUE_DEGRADED",
    "ADDRESS_DISTRIBUTION_FAILED",
    "READ_AGGREGATION_FAILED",
    "RESIDUAL_OR_DECODER_UTILIZATION_FAILED",
    "VALUE_PATH_NOT_LOCALIZED",
    "NOT_APPLICABLE_RETRIEVAL_PRESENT",
]
QUALITY_CATEGORIES = [
    "QUALITY_GRADIENT_CONFLICT_LOCALIZED",
    "QUALITY_INTERFERENCE_NOT_LOCALIZED",
    "NOT_APPLICABLE_QUALITY_OK",
]


def value_path_diagnosis(m):
    """m: dict with keys
      needle_baseline, oracle_address_needle, oracle_read_query_needle, oracle_postwrite_needle,
      postwrite_decodable, query_decodable
    Returns (category, reasons dict). Applies §14 value-path rules in priority order.
    """
    nb = m["needle_baseline"]
    if nb >= RETRIEVAL_PRESENT_MIN:
        return "NOT_APPLICABLE_RETRIEVAL_PRESENT", {"needle_baseline": nb,
                                                    "reason": "ordinary retrieval present"}
    post_lin_dec = m["postwrite_decodable"] >= DECODABLE_MIN     # A2 linear (STORAGE uses this)
    query_lin_dec = m["query_decodable"] >= DECODABLE_MIN        # A2 linear
    query_lin_lost = (m["postwrite_decodable"] - m["query_decodable"]) >= MATERIAL_DROP
    ordinary_fails = nb <= RETRIEVAL_FAILS_MAX
    addr_rec = m["oracle_address_needle"] >= RECOVER_MIN         # A3
    read_rec = m["oracle_read_query_needle"] >= RECOVER_MIN      # A4a
    post_rec = m["oracle_postwrite_needle"] >= RECOVER_MIN       # A4b
    # AUTHORIZED SPEC-FIDELITY CORRECTION (see code_correction_record.json): the §14 ADDRESS/READ/
    # RESIDUAL rules require the "query-time slot [to] remain decodable". §9 warns a linear-probe
    # failure is NOT proof of information absence, and §11 A4a defines the functional test of whether
    # the still-valid target-slot value is usable. So "recoverable" is operationalized functionally:
    # the query-time slot value is recoverable if reading it directly recovers retrieval (A4a) OR it
    # is linearly decodable (A2). Linear decodability is sufficient but not necessary. STORAGE keeps
    # the explicit "linearly decodable" wording (A2). Frozen thresholds are unchanged.
    query_recoverable = read_rec or query_lin_dec
    reasons = {"needle_baseline": nb, "postwrite_decodable": m["postwrite_decodable"],
               "query_decodable": m["query_decodable"], "postwrite_linearly_decodable": post_lin_dec,
               "query_linearly_decodable": query_lin_dec, "query_recoverable_functional_or_linear":
               query_recoverable, "query_linear_decodability_lost": query_lin_lost,
               "ordinary_retrieval_fails": ordinary_fails, "oracle_address_recovers": addr_rec,
               "oracle_read_query_recovers": read_rec, "oracle_postwrite_recovers": post_rec}

    # STORAGE_VALUE_DEGRADED (§14 says "linearly decodable"): post-write linearly decodable, query
    # linearly loses decodability, restoring the post-write value recovers retrieval.
    if post_lin_dec and query_lin_lost and post_rec:
        return "STORAGE_VALUE_DEGRADED", reasons
    # ADDRESS_DISTRIBUTION_FAILED: query slot remains recoverable, ordinary retrieval fails, oracle
    # one-hot address restores retrieval.
    if query_recoverable and ordinary_fails and addr_rec:
        return "ADDRESS_DISTRIBUTION_FAILED", reasons
    # READ_AGGREGATION_FAILED: query slot recoverable, oracle address does NOT recover, but the
    # direct query-time slot read recovers.
    if query_recoverable and (not addr_rec) and read_rec:
        return "READ_AGGREGATION_FAILED", reasons
    # RESIDUAL_OR_DECODER_UTILIZATION_FAILED: target-slot info recoverable, the oracle memory
    # contribution is delivered to the residual (A4b applied), yet retrieval still does not recover.
    if (post_lin_dec or query_recoverable) and (not post_rec) and (not addr_rec) and (not read_rec):
        return "RESIDUAL_OR_DECODER_UTILIZATION_FAILED", reasons
    return "VALUE_PATH_NOT_LOCALIZED", reasons


def quality_diagnosis(m):
    """m: dict with keys
      quality_failed (bool),
      failed_alignment_by_group: {group: cosine or None} (lm vs persist|teacher on THIS seed),
      control_alignment_by_group: {group: cosine or None} (same loss on the clean control seed)
    Returns (category, reasons).
    """
    if not m.get("quality_failed", False):
        return "NOT_APPLICABLE_QUALITY_OK", {"quality_failed": False}
    fa = m.get("failed_alignment_by_group") or {}
    ca = m.get("control_alignment_by_group") or {}
    conflicted = []
    for g, cos in fa.items():
        if cos is None:
            continue
        cc = ca.get(g)
        materially_negative = cos <= CONFLICT_COS
        weaker_in_control = (cc is None) or ((cc - cos) >= CONTROL_GAP)
        if materially_negative and weaker_in_control:
            conflicted.append({"group": g, "failed_cos": cos, "control_cos": cc})
    reasons = {"quality_failed": True, "conflicted_groups": conflicted,
               "n_conflicted": len(conflicted)}
    if conflicted:
        return "QUALITY_GRADIENT_CONFLICT_LOCALIZED", reasons
    return "QUALITY_INTERFERENCE_NOT_LOCALIZED", reasons


def seed_diagnosis(arm, seed, measurements):
    """Combine the value-path and quality sub-diagnoses for one seed. Each is independent; a seed
    may be NOT_APPLICABLE on one axis and localized on the other. Collapsed-baseline causal
    ablations are flagged non-informative (§15)."""
    vp_cat, vp_reasons = value_path_diagnosis(measurements)
    q_cat, q_reasons = quality_diagnosis(measurements)
    baseline_collapsed = measurements["needle_baseline"] <= RETRIEVAL_FAILS_MAX
    return {
        "arm": arm, "seed": seed,
        "value_path_diagnosis": vp_cat, "value_path_reasons": vp_reasons,
        "quality_diagnosis": q_cat, "quality_reasons": q_reasons,
        "baseline_collapsed_ablations_non_informative": baseline_collapsed,
    }


def aggregate_verdict(per_seed):
    """§18 primary verdict from the per-seed diagnoses (excluding integrity/repro failures, which
    the orchestrator sets earlier). A family is 'localized' if >=1 seed yields a unique boundary."""
    vp_localized = any(
        d["value_path_diagnosis"] in VALUE_PATH_CATEGORIES[:4] for d in per_seed)
    q_localized = any(
        d["quality_diagnosis"] == "QUALITY_GRADIENT_CONFLICT_LOCALIZED" for d in per_seed)
    if vp_localized and q_localized:
        return "BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED"
    if vp_localized:
        return "BINDINGSLOTS_VALUE_PATH_FAILURE_LOCALIZED"
    if q_localized:
        return "BINDINGSLOTS_QUALITY_INTERFERENCE_LOCALIZED"
    return "BINDINGSLOTS_DIAGNOSTIC_RESULTS_INCONCLUSIVE"


FROZEN_CONSTANTS = {
    "CHANCE": CHANCE, "DECODABLE_MIN": DECODABLE_MIN, "MATERIAL_DROP": MATERIAL_DROP,
    "RETRIEVAL_PRESENT_MIN": RETRIEVAL_PRESENT_MIN, "RETRIEVAL_FAILS_MAX": RETRIEVAL_FAILS_MAX,
    "RECOVER_MIN": RECOVER_MIN, "CONFLICT_COS": CONFLICT_COS, "CONTROL_GAP": CONTROL_GAP,
}
