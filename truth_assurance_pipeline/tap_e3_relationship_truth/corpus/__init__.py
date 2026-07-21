"""TAP-E3 relationship corpus (new, independently authored)."""
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus import cases
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus.cases import (
    ALL_CASES, ALL_UNITS, Case, GoldRel, cases_for_split, build_retrieval_record,
    eval_lock, manifest,
)
__all__ = ["cases", "ALL_CASES", "ALL_UNITS", "Case", "GoldRel", "cases_for_split",
           "build_retrieval_record", "eval_lock", "manifest"]
