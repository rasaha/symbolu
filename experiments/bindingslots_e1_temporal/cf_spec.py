#!/usr/bin/env python3
"""FROZEN counterfactual-diagnostic protocol + attribution rules for the T4 latest-state shortfall.

Zero new training / zero optimizer steps. All arms run the FROZEN E1 (deterministic replay, byte-identical
param hash verified) on the EXACT committed T4 episodes (reserved seeds 6140-6144). Oracle information
(evaluator entity identity, ground-truth latest record, episode metadata) is used ONLY as a diagnostic
counterfactual and is NEVER a deployable policy. New diagnostic evidence is written separately; no prior
evidence, prediction, gate, metric, or verdict is replaced.

Arms (all on the same committed T4 episodes):
  D0  ordinary frozen E1 (argmax over the 32 keys + null)          — reference; must be byte-identical.
  D1  null-suppressed read (argmax over the 32 real keys only).    — max gain from suppressing abstention.
  D2  correct-entity restricted (argmax over {correct-entity records, null}). oracle entity identity.
  D3  correct-entity + null-suppressed (argmax over correct-entity records only). pure latest ranking.
  D4  correct-latest oracle read (select the ground-truth latest record; return its stored value via the
      existing read path).                                          — value/read-path check.
  D5  correct-entity latest-by-position (metadata max position among correct-entity records; return its
      value).                                                       — upper bound of an explicit selector.
"""
from __future__ import annotations

PRESERVE = ["E1_TEMPORAL_TRANSFER_PARTIAL",
            "ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
            "KDA_VALIDATION_BLOCKED"]

CONCLUSIONS = [
    "T4_SHORTFALL_PRIMARILY_ABSTENTION",
    "T4_SHORTFALL_PRIMARILY_ENTITY_RETRIEVAL",
    "T4_SHORTFALL_PRIMARILY_LATEST_RANKING",
    "T4_SHORTFALL_MIXED",
    "T4_SHORTFALL_VALUE_PATH",
    "T4_COUNTERFACTUAL_INCONCLUSIVE",
    "T4_COUNTERFACTUAL_PROTOCOL_VIOLATED",
    "T4_COUNTERFACTUAL_RESOURCE_BLOCKED",
]

# frozen thresholds
PRIMARY_RECOVERY = 0.60
ABSTENTION_ADD_MAX = 0.15       # D2/D3 add < 15pp beyond D1 -> abstention dominates
LATEST_D1_MAX = 0.40            # D1 alone recovers < 40% -> not abstention-driven
ENTITY_WITHIN_D3_MIN = 0.90     # within-entity latest selection under D3
MIXED_COMPONENT_MIN = 0.20      # each of >=2 components >= 20% of D0 failures
VALUE_PATH_FAIL_MAX = 0.10      # D4 fails on > 10% despite correct latest record


def conclude(m):
    """m: dict of frozen scalars computed BEFORE this call is read (see cf_diagnostics).
    Keys: byte_identical, oracle_valid, d1_rec, d2_rec, d3_rec, d4_fail_rate,
    abstention_component, entity_component, latest_component, within_entity_latest_d3,
    entity_recovered_from_wrongentity_majority (bool), latest_older_majority_in_residual (bool).
    Returns (primary_conclusion, value_path_secondary: bool)."""
    if not m["byte_identical"] or not m["oracle_valid"]:
        return "T4_COUNTERFACTUAL_PROTOCOL_VIOLATED", False

    value_path_secondary = m["d4_fail_rate"] > VALUE_PATH_FAIL_MAX

    # VALUE_PATH primary only if it explains the majority of failures
    if value_path_secondary and m["d4_fail_rate"] >= 0.50:
        return "T4_SHORTFALL_VALUE_PATH", False

    abstention = (m["d1_rec"] >= PRIMARY_RECOVERY
                  and (m["d2_rec"] - m["d1_rec"]) < ABSTENTION_ADD_MAX
                  and (m["d3_rec"] - m["d1_rec"]) < ABSTENTION_ADD_MAX)
    entity = ((max(m["d2_rec"], m["d3_rec"]) >= PRIMARY_RECOVERY)
              and m["entity_recovered_from_wrongentity_majority"]
              and m["within_entity_latest_d3"] >= ENTITY_WITHIN_D3_MIN)
    latest = (m["d3_rec"] >= PRIMARY_RECOVERY and m["d1_rec"] < LATEST_D1_MAX
              and m["latest_older_majority_in_residual"])

    if abstention and not (entity or latest):
        return "T4_SHORTFALL_PRIMARILY_ABSTENTION", value_path_secondary
    if entity and not (abstention or latest):
        return "T4_SHORTFALL_PRIMARILY_ENTITY_RETRIEVAL", value_path_secondary
    if latest and not (abstention or entity):
        return "T4_SHORTFALL_PRIMARILY_LATEST_RANKING", value_path_secondary

    comps = [m["abstention_component"], m["entity_component"], m["latest_component"]]
    if sum(1 for c in comps if c >= MIXED_COMPONENT_MIN) >= 2:
        return "T4_SHORTFALL_MIXED", value_path_secondary
    return "T4_COUNTERFACTUAL_INCONCLUSIVE", value_path_secondary


RECOMMENDATION = {
    "T4_SHORTFALL_PRIMARILY_ABSTENTION": "future preregistered no-match / null-gating diagnostic",
    "T4_SHORTFALL_PRIMARILY_ENTITY_RETRIEVAL": "future clean retrieval-capacity or predicate-conditioning diagnostic",
    "T4_SHORTFALL_PRIMARILY_LATEST_RANKING": "future preregistered order-aware diagnostic; do NOT assume a capacity arm is needed",
    "T4_SHORTFALL_MIXED": "future preregistered factorial separating null-gating, entity retrieval, and latest ranking",
    "T4_SHORTFALL_VALUE_PATH": "investigate value storage/read/output before any addressing intervention",
    "T4_COUNTERFACTUAL_INCONCLUSIVE": "identify the minimum missing instrumentation only",
    "T4_COUNTERFACTUAL_PROTOCOL_VIOLATED": "recover exact frozen artifacts / byte-identical D0 before analysis",
    "T4_COUNTERFACTUAL_RESOURCE_BLOCKED": "required artifacts/torch unavailable",
}
