#!/usr/bin/env python3
"""Torch-free tests for the mechanical diagnosis rules (§14) + verdict aggregation. Standalone/pytest."""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import diagnosis_classify as DC  # noqa: E402


def _m(**kw):
    base = dict(needle_baseline=0.0, oracle_address_needle=0.0, oracle_read_query_needle=0.0,
               oracle_postwrite_needle=0.0, postwrite_decodable=0.9, query_decodable=0.9,
               quality_failed=False, failed_alignment_by_group={}, control_alignment_by_group={})
    base.update(kw)
    return base


# ---------- value-path rules ----------
def test_storage_value_degraded():
    c, _ = DC.value_path_diagnosis(_m(postwrite_decodable=0.9, query_decodable=0.2,
                                      oracle_postwrite_needle=0.9))
    assert c == "STORAGE_VALUE_DEGRADED"


def test_address_distribution_failed():
    c, _ = DC.value_path_diagnosis(_m(query_decodable=0.9, postwrite_decodable=0.9,
                                      oracle_address_needle=0.9))
    assert c == "ADDRESS_DISTRIBUTION_FAILED"


def test_read_aggregation_failed():
    c, _ = DC.value_path_diagnosis(_m(query_decodable=0.9, postwrite_decodable=0.9,
                                      oracle_address_needle=0.0, oracle_read_query_needle=0.9))
    assert c == "READ_AGGREGATION_FAILED"


def test_residual_or_decoder_utilization_failed():
    c, _ = DC.value_path_diagnosis(_m(query_decodable=0.9, postwrite_decodable=0.9,
                                      oracle_address_needle=0.0, oracle_read_query_needle=0.0,
                                      oracle_postwrite_needle=0.0))
    assert c == "RESIDUAL_OR_DECODER_UTILIZATION_FAILED"


def test_retrieval_present_not_applicable():
    c, _ = DC.value_path_diagnosis(_m(needle_baseline=0.8))
    assert c == "NOT_APPLICABLE_RETRIEVAL_PRESENT"


def test_value_path_not_localized_when_nothing_recovers_and_not_decodable():
    c, _ = DC.value_path_diagnosis(_m(postwrite_decodable=0.1, query_decodable=0.1))
    assert c == "VALUE_PATH_NOT_LOCALIZED"


def test_storage_requires_query_loss_not_just_recovery():
    # post-write recovers but query decodability NOT materially lost -> not STORAGE; address recovers
    c, _ = DC.value_path_diagnosis(_m(postwrite_decodable=0.9, query_decodable=0.85,
                                      oracle_postwrite_needle=0.9, oracle_address_needle=0.9))
    assert c == "ADDRESS_DISTRIBUTION_FAILED"


# ---------- quality rules ----------
def test_quality_conflict_localized():
    c, r = DC.quality_diagnosis(_m(quality_failed=True,
                                   failed_alignment_by_group={"backbone": -0.3, "slot_keys": 0.5},
                                   control_alignment_by_group={"backbone": 0.2, "slot_keys": 0.5}))
    assert c == "QUALITY_GRADIENT_CONFLICT_LOCALIZED" and r["n_conflicted"] == 1


def test_quality_not_localized_without_material_conflict():
    c, _ = DC.quality_diagnosis(_m(quality_failed=True,
                                   failed_alignment_by_group={"backbone": -0.05},
                                   control_alignment_by_group={"backbone": 0.2}))
    assert c == "QUALITY_INTERFERENCE_NOT_LOCALIZED"


def test_quality_not_localized_when_control_equally_negative():
    # negative but control equally negative (no gap) -> not attributable
    c, _ = DC.quality_diagnosis(_m(quality_failed=True,
                                   failed_alignment_by_group={"backbone": -0.3},
                                   control_alignment_by_group={"backbone": -0.28}))
    assert c == "QUALITY_INTERFERENCE_NOT_LOCALIZED"


def test_quality_not_applicable_when_quality_ok():
    c, _ = DC.quality_diagnosis(_m(quality_failed=False))
    assert c == "NOT_APPLICABLE_QUALITY_OK"


def test_none_cosine_is_zero_gradient_safe():
    # a None cosine (zero-gradient group) is skipped, not crashed
    c, _ = DC.quality_diagnosis(_m(quality_failed=True,
                                   failed_alignment_by_group={"write_gate": None, "backbone": -0.3},
                                   control_alignment_by_group={"backbone": 0.2}))
    assert c == "QUALITY_GRADIENT_CONFLICT_LOCALIZED"


# ---------- combined seed diagnosis + non-informative flag ----------
def test_seed_diagnosis_flags_collapsed_baseline_non_informative():
    d = DC.seed_diagnosis("H2", 23, _m(needle_baseline=0.0, postwrite_decodable=0.9,
                                       query_decodable=0.2, oracle_postwrite_needle=0.9))
    assert d["baseline_collapsed_ablations_non_informative"] is True
    assert d["value_path_diagnosis"] == "STORAGE_VALUE_DEGRADED"


def test_seed_diagnosis_present_baseline_not_flagged():
    d = DC.seed_diagnosis("R0", 24, _m(needle_baseline=1.0))
    assert d["baseline_collapsed_ablations_non_informative"] is False


# ---------- verdict aggregation ----------
def test_verdict_both_localized():
    ps = [DC.seed_diagnosis("H2", 23, _m(needle_baseline=0.0, query_decodable=0.2,
                                         oracle_postwrite_needle=0.9)),
          DC.seed_diagnosis("O1R", 24, _m(needle_baseline=1.0, quality_failed=True,
                                          failed_alignment_by_group={"backbone": -0.3},
                                          control_alignment_by_group={"backbone": 0.2}))]
    assert DC.aggregate_verdict(ps) == "BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED"


def test_verdict_value_path_only():
    ps = [DC.seed_diagnosis("H2", 23, _m(needle_baseline=0.0, query_decodable=0.2,
                                         oracle_postwrite_needle=0.9))]
    assert DC.aggregate_verdict(ps) == "BINDINGSLOTS_VALUE_PATH_FAILURE_LOCALIZED"


def test_verdict_quality_only():
    ps = [DC.seed_diagnosis("O1R", 24, _m(needle_baseline=1.0, quality_failed=True,
                                          failed_alignment_by_group={"backbone": -0.3},
                                          control_alignment_by_group={"backbone": 0.2}))]
    assert DC.aggregate_verdict(ps) == "BINDINGSLOTS_QUALITY_INTERFERENCE_LOCALIZED"


def test_verdict_inconclusive():
    ps = [DC.seed_diagnosis("R0", 24, _m(needle_baseline=1.0))]
    assert DC.aggregate_verdict(ps) == "BINDINGSLOTS_DIAGNOSTIC_RESULTS_INCONCLUSIVE"


# ---------- frozen constants match preregistration ----------
def test_frozen_constants_match_preregistration():
    prereg = json.loads((EXP / "preregistration.json").read_text())
    pc = prereg["frozen_decision_constants"]
    assert DC.DECODABLE_MIN == pc["DECODABLE_MIN"]
    assert DC.MATERIAL_DROP == pc["MATERIAL_DROP"]
    assert DC.RETRIEVAL_PRESENT_MIN == pc["RETRIEVAL_PRESENT_MIN"]
    assert DC.RETRIEVAL_FAILS_MAX == pc["RETRIEVAL_FAILS_MAX"]
    assert DC.RECOVER_MIN == pc["RECOVER_MIN"]
    assert DC.CONFLICT_COS == pc["CONFLICT_COS"]
    assert DC.CONTROL_GAP == pc["CONTROL_GAP"]


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"diagnosis-classify tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
