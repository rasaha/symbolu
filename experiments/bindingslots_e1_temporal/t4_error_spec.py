#!/usr/bin/env python3
"""FROZEN T4 error-classification specification (committed BEFORE reading any aggregate result).

Zero new training: per-query T4 predictions are recovered by DETERMINISTIC REPLAY of the frozen E1
(byte-identical param hash verified against the committed per-seed e1_param_sha256) and inference on the
committed reserved T4 episodes. No model, seed, gate, metric, or verdict is changed.

Every T4 query is classified into EXACTLY ONE category:
"""
from __future__ import annotations

CATEGORIES = [
    "RIGHT_ENTITY_RIGHT_LATEST_STEP",   # correct latest record selected (consistency check; a "failure"
                                        # here would indicate a bug)
    "RIGHT_ENTITY_WRONG_OLDER_STEP",    # a valid record of the CORRECT entity, but not its latest state
    "WRONG_ENTITY",                     # selected record belongs to a different entity
    "NULL_OR_ABSTAIN",                  # learned null key selected despite a matching memory existing
    "INVALID_OR_OTHER",                 # anything else (with written explanation)
]

# A T4 query is a FAILURE iff the predicted index != the target (latest) record index.
# Failure categories = {RIGHT_ENTITY_WRONG_OLDER_STEP, WRONG_ENTITY, NULL_OR_ABSTAIN, INVALID_OR_OTHER}.

# ---- FROZEN mechanical conclusion rule (fixed before reading the aggregate) -------------
INVALID_OTHER_MAX_FRACTION = 0.10       # if INVALID_OR_OTHER exceeds this share of failures -> INCONCLUSIVE
PRIMARY_THRESHOLD = 0.70                # >=70% of failures in one category -> PRIMARILY_*
MIXED_COMBINED_THRESHOLD = 0.80         # neither reaches 0.70 but the two together >= 0.80 -> MIXED


def conclude(failure_counts, replay_byte_identical, total_failures):
    """failure_counts: dict category -> count (over all failed T4 queries, all seeds)."""
    if not replay_byte_identical:
        return "T4_ERROR_ANALYSIS_PROTOCOL_VIOLATED"
    if total_failures == 0:
        return "T4_ERROR_ANALYSIS_INCONCLUSIVE"
    frac = {c: failure_counts.get(c, 0) / total_failures for c in CATEGORIES}
    if frac["INVALID_OR_OTHER"] > INVALID_OTHER_MAX_FRACTION:
        return "T4_ERROR_ANALYSIS_INCONCLUSIVE"
    older = frac["RIGHT_ENTITY_WRONG_OLDER_STEP"]
    wrong = frac["WRONG_ENTITY"]
    if older >= PRIMARY_THRESHOLD:
        return "T4_FAILURE_PRIMARILY_LATEST_SELECTION"
    if wrong >= PRIMARY_THRESHOLD:
        return "T4_FAILURE_PRIMARILY_ENTITY_RETRIEVAL"
    if (older + wrong) >= MIXED_COMBINED_THRESHOLD:
        return "T4_FAILURE_MIXED"
    return "T4_ERROR_ANALYSIS_INCONCLUSIVE"


ALWAYS = ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "KDA_VALIDATION_BLOCKED"]

# Decision recommendation mapping (from the mechanical conclusion; T5 stays outside the conclusion).
RECOMMENDATION = {
    "T4_FAILURE_PRIMARILY_LATEST_SELECTION":
        "future preregistered ORDER-AWARE diagnostic; a capacity arm may be unnecessary unless separately justified",
    "T4_FAILURE_PRIMARILY_ENTITY_RETRIEVAL":
        "future clean CAPACITY/OPTIMIZATION diagnostic before adding temporal logic",
    "T4_FAILURE_MIXED":
        "preregistered E0 vs capacity-only vs order-aware experiment",
    "T4_ERROR_ANALYSIS_INCONCLUSIVE":
        "identify the minimum additional instrumentation needed; do NOT run a new experiment",
    "T4_ERROR_ANALYSIS_PROTOCOL_VIOLATED":
        "replay not byte-identical; recover exact frozen artifacts before any analysis",
    "T4_ERROR_ANALYSIS_RESOURCE_BLOCKED":
        "required artifacts/torch unavailable",
}
