#!/usr/bin/env python3
"""
Competing Operative Resolution Layer — deterministic.

Sits AFTER the frozen G3 operative-source selection. It builds a typed OperativeCandidate
per governing clause, models scope across deterministic dimensions, tests genuine conflict
with an explicit predicate battery, classifies each competition, and abstains at the
governance stage ONLY when the operative outcome is genuinely unresolved. It never abstains
merely because permission and prohibition language co-occur.

Core principle (frozen): a conflict exists only when two candidates are simultaneously
applicable to the same subject/action/object/condition/scope/time/authority-domain AND
prescribe incompatible outcomes AND no graph relationship already resolves it. A value that
cannot be derived is UNKNOWN and implies neither overlap nor non-overlap; genuine conflict
requires overlap to be POSITIVELY established, so unknown scope never forces an abstention.
"""

from __future__ import annotations

import re

from ..experiment_v4.governance_semantics import _tfc_signal

# ---- operative polarity ---- #
REQUIRED = "REQUIRED"
PROHIBITED = "PROHIBITED"
PERMITTED = "PERMITTED"
CONDITIONALLY_REQUIRED = "CONDITIONALLY_REQUIRED"
CONDITIONALLY_PROHIBITED = "CONDITIONALLY_PROHIBITED"
CONDITIONALLY_PERMITTED = "CONDITIONALLY_PERMITTED"
UNDETERMINED = "UNDETERMINED"
NON_OPERATIVE = "NON_OPERATIVE"

# ---- conflict categories ---- #
NO_SCOPE_OVERLAP = "NO_SCOPE_OVERLAP"
TEMPORALLY_SEPARATED = "TEMPORALLY_SEPARATED"
DIFFERENT_AUTHORITY_DOMAIN = "DIFFERENT_AUTHORITY_DOMAIN"
CONDITIONALLY_SEPARATED = "CONDITIONALLY_SEPARATED"
RESOLVED_BY_SUPERSESSION = "RESOLVED_BY_SUPERSESSION"
RESOLVED_BY_OVERRIDE = "RESOLVED_BY_OVERRIDE"
RESOLVED_BY_EXCEPTION = "RESOLVED_BY_EXCEPTION"
PARALLEL_APPLICABILITY = "PARALLEL_APPLICABILITY"
CUMULATIVE_REQUIREMENT = "CUMULATIVE_REQUIREMENT"
COMPATIBLE_OPERATIVES = "COMPATIBLE_OPERATIVES"
GENUINE_RESOLVED_CONFLICT = "GENUINE_RESOLVED_CONFLICT"
GENUINE_UNRESOLVED_CONFLICT = "GENUINE_UNRESOLVED_CONFLICT"
INSUFFICIENT_SCOPE_EVIDENCE = "INSUFFICIENT_SCOPE_EVIDENCE"

# ---- preregistered abstention reasons ---- #
AB_GENUINE_UNRESOLVED = "GENUINE_UNRESOLVED_CONFLICT"
AB_INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE_EVIDENCE"
AB_OPERATIVE_NOT_LOCATED = "OPERATIVE_TERM_NOT_LOCATED"
AB_MULTIPLE_INCOMPATIBLE = "MULTIPLE_INCOMPATIBLE_OPERATIVE_TERMS"
AB_PACKET_CARDINALITY = "FROZEN_PACKET_CARDINALITY_LIMIT"
AB_MISSING_PROVENANCE = "MISSING_DECISIVE_PROVENANCE"

_YEAR = re.compile(r"(19|20)\d{2}")
_RESOLVING_EDGE = ("supersedes", "overrides", "governs_over", "exception_to", "same_as", "amends")


class Config:
    """Ablation switches. C4 (full) enables everything."""
    def __init__(self, extract=True, scope=True, classify=True, resolve_abstain=True):
        self.extract = extract
        self.scope = scope
        self.classify = classify
        self.resolve_abstain = resolve_abstain


def _polarity(node):
    sig = _tfc_signal(node)
    if sig == "prohibited":
        return PROHIBITED
    if sig == "allowed":
        return PERMITTED
    if node.attrs.get("notice_days") or node.attrs.get("penalty_months"):
        return CONDITIONALLY_PERMITTED   # carries an operative term but not a bare polarity
    return NON_OPERATIVE


def _authority_domain(node):
    k = (node.key + " " + (node.text or "")).lower()
    if any(w in k for w in ("regulat", "statut", "directive", "law ", "ordinance", "code §")):
        return "REGULATORY"
    if any(w in k for w in ("policy", "corporate", "standard", "guideline")):
        return "CORPORATE_POLICY"
    if any(w in k for w in ("msa", "master", "agreement", "order form", "schedule",
                            "amendment", "clause", "exhibit", "rider", "addend")):
        return "CONTRACT"
    return "UNKNOWN"


def _year(node):
    m = _YEAR.search(node.key + " " + (node.text or ""))
    return int(m.group(0)) if m else None


def build_candidate(node, graph, conf, config: Config):
    out = [e for e in graph.edges if e.src == node.key]
    cand = {
        "node": node.key,
        "polarity": _polarity(node),
        "operative_action": "terminate_for_convenience",   # the benchmark's single decision matter
        "operative_subject": "contract_parties",
        "operative_object": "the_agreement",
        "answer_bearing_term": _tfc_signal(node) or (
            "notice" if node.attrs.get("notice_days") else
            ("penalty" if node.attrs.get("penalty_months") else None)),
        "provenance": bool(out),
        "support_nodes": sorted({e.dst for e in out}),
    }
    if config.scope:
        cand["scope"] = {
            "entity": "contract_parties",
            "action": "terminate_for_convenience",
            "object": "the_agreement",
            "authority_domain": _authority_domain(node),
            "temporal_year": _year(node),
            "condition": "exception" if node.type == "Exception" else "UNKNOWN",
            "amendment_target": node.attrs.get("supersede_target") or "UNKNOWN",
        }
    else:
        cand["scope"] = {"authority_domain": "UNKNOWN", "temporal_year": None}
    cand["evidence_vector"] = {
        "lexical_operative_support": round(max((conf.get(e.triple(), 0.0) for e in out), default=0.0), 3),
        "subject_match": True, "action_match": True, "object_match": True,
        "scope_overlap": "UNKNOWN", "temporal_applicability": cand["scope"].get("temporal_year") is not None,
        "authority_applicability": cand["scope"].get("authority_domain") != "UNKNOWN",
        "condition_applicability": cand["scope"].get("condition") != "exception",
        "graph_resolution_support": None, "provenance_complete": bool(out),
        "answer_term_support": cand["answer_bearing_term"] is not None,
    }
    return cand


def _resolving_edge(a_key, b_key, graph):
    for e in graph.edges:
        if e.type in _RESOLVING_EDGE and {e.src, e.dst} == {a_key, b_key}:
            return e.type
    return None


def conflict_predicates(a, b, graph):
    """The 10 explicit predicates; every result is exposed."""
    dom_a = a["scope"].get("authority_domain", "UNKNOWN")
    dom_b = b["scope"].get("authority_domain", "UNKNOWN")
    yr_a, yr_b = a["scope"].get("temporal_year"), b["scope"].get("temporal_year")
    resolving = _resolving_edge(a["node"], b["node"], graph)
    # temporal overlap: positively separated only if both dated and a resolving/dated edge splits them
    temporally_separated = bool(yr_a and yr_b and yr_a != yr_b and resolving in ("supersedes", "amends"))
    incompatible = ({a["polarity"], b["polarity"]} == {PROHIBITED, PERMITTED})
    return {
        "both_applicable": True,
        "compatible_subjects": a["operative_subject"] == b["operative_subject"],
        "overlapping_action": a["operative_action"] == b["operative_action"],
        "overlapping_object": a["operative_object"] == b["operative_object"],
        "temporal_overlap": not temporally_separated,
        "authority_overlap": (dom_a == dom_b) and dom_a != "UNKNOWN",
        "conditions_simultaneous": not (a["scope"].get("condition") == "exception"
                                        or b["scope"].get("condition") == "exception"),
        "incompatible_outcomes": incompatible,
        "no_resolving_relationship": resolving is None,
        "neither_supporting": a["polarity"] != NON_OPERATIVE and b["polarity"] != NON_OPERATIVE,
        "_resolving_edge": resolving,
        "_authority_domains": [dom_a, dom_b],
    }


def classify(pred):
    """Exactly one primary conflict category from the predicate results."""
    if not pred["incompatible_outcomes"]:
        return COMPATIBLE_OPERATIVES
    if pred["_resolving_edge"] in ("supersedes",):
        return RESOLVED_BY_SUPERSESSION
    if pred["_resolving_edge"] in ("overrides",):
        return RESOLVED_BY_OVERRIDE
    if pred["_resolving_edge"] in ("exception_to",):
        return RESOLVED_BY_EXCEPTION
    if pred["_resolving_edge"] in ("governs_over", "same_as", "amends"):
        return GENUINE_RESOLVED_CONFLICT
    if not pred["temporal_overlap"]:
        return TEMPORALLY_SEPARATED
    if not pred["conditions_simultaneous"]:
        return CONDITIONALLY_SEPARATED
    if pred["_authority_domains"][0] != pred["_authority_domains"][1] \
       and "UNKNOWN" not in pred["_authority_domains"]:
        return DIFFERENT_AUTHORITY_DOMAIN
    if not pred["authority_overlap"]:
        # domains not positively established as overlapping → cannot assert genuine conflict
        return INSUFFICIENT_SCOPE_EVIDENCE
    if all(pred[k] for k in ("both_applicable", "compatible_subjects", "overlapping_action",
                             "overlapping_object", "temporal_overlap", "authority_overlap",
                             "conditions_simultaneous", "incompatible_outcomes",
                             "no_resolving_relationship", "neither_supporting")):
        return GENUINE_UNRESOLVED_CONFLICT
    return INSUFFICIENT_SCOPE_EVIDENCE


class OperativeSet:
    def __init__(self):
        self.applicable_operatives = []
        self.displaced_operatives = []
        self.cumulative_operatives = []
        self.conditional_operatives = []
        self.conflicting_operatives = []
        self.compatible_operatives = []
        self.unresolved_operatives = []
        self.selected_operatives = []
        self.operative_abstention = False
        self.operative_abstention_reason = ""
        self.abstention_detail = {}
        self.decision_trace = []
        self.candidates = []
        self.competitions = []

    def as_dict(self):
        return {k: getattr(self, k) for k in (
            "applicable_operatives", "displaced_operatives", "cumulative_operatives",
            "conditional_operatives", "conflicting_operatives", "compatible_operatives",
            "unresolved_operatives", "selected_operatives", "operative_abstention",
            "operative_abstention_reason", "abstention_detail", "decision_trace",
            "candidates", "competitions")}


def resolve(graph, governing_keys, operative_key, conf, config: Config) -> OperativeSet:
    """Build candidates over the frozen governing set, classify competitions, and decide
    abstention. Returns an OperativeSet; the caller keeps the G3 operative unless a genuine
    unresolved conflict forces abstention."""
    r = OperativeSet()
    nodes_by_key = {n.key: n for n in graph.nodes}
    gov_nodes = [nodes_by_key[k] for k in governing_keys if k in nodes_by_key]
    if not config.extract:
        r.selected_operatives = [operative_key] if operative_key else []
        return r

    cands = [build_candidate(n, graph, conf, config) for n in gov_nodes]
    r.candidates = cands
    r.applicable_operatives = [c["node"] for c in cands if c["polarity"] != NON_OPERATIVE]
    r.selected_operatives = [operative_key] if operative_key else []

    if not config.classify:
        return r

    operatives = [c for c in cands if c["polarity"] != NON_OPERATIVE]
    for i in range(len(operatives)):
        for j in range(i + 1, len(operatives)):
            a, b = operatives[i], operatives[j]
            pred = conflict_predicates(a, b, graph)
            cat = classify(pred)
            comp = {"a": a["node"], "b": b["node"], "category": cat,
                    "predicates": {k: v for k, v in pred.items() if not k.startswith("_")},
                    "resolving_edge": pred["_resolving_edge"],
                    "authority_domains": pred["_authority_domains"]}
            r.competitions.append(comp)
            if cat in (PARALLEL_APPLICABILITY, DIFFERENT_AUTHORITY_DOMAIN):
                r.conditional_operatives += [a["node"], b["node"]]
            elif cat == COMPATIBLE_OPERATIVES:
                r.compatible_operatives += [a["node"], b["node"]]
            elif cat == CUMULATIVE_REQUIREMENT:
                r.cumulative_operatives += [a["node"], b["node"]]
            elif cat in (GENUINE_RESOLVED_CONFLICT, RESOLVED_BY_SUPERSESSION,
                         RESOLVED_BY_OVERRIDE, RESOLVED_BY_EXCEPTION):
                r.conflicting_operatives += [a["node"], b["node"]]
            elif cat == GENUINE_UNRESOLVED_CONFLICT:
                r.unresolved_operatives += [a["node"], b["node"]]

    if not config.resolve_abstain:
        return r

    # PRECISE abstention — only on a genuinely unresolved conflict (or the other
    # preregistered reasons). Never on mere permission/prohibition co-occurrence.
    genuine = [c for c in r.competitions if c["category"] == GENUINE_UNRESOLVED_CONFLICT]
    if genuine:
        r.operative_abstention = True
        r.operative_abstention_reason = AB_GENUINE_UNRESOLVED
        r.abstention_detail = {
            "candidate_operatives": sorted(set(r.unresolved_operatives)),
            "unresolved_predicates": genuine[0]["predicates"],
            "rejected_resolution_paths": ["no supersedes/overrides/exception between candidates",
                                          "same authority domain", "temporal overlap"],
            "reason_code": AB_GENUINE_UNRESOLVED}
        r.decision_trace.append(f"abstain: genuine unresolved conflict {genuine[0]['a']} vs {genuine[0]['b']}")
    elif not r.selected_operatives:
        r.operative_abstention = True
        r.operative_abstention_reason = AB_OPERATIVE_NOT_LOCATED
        r.abstention_detail = {"reason_code": AB_OPERATIVE_NOT_LOCATED,
                               "candidate_operatives": r.applicable_operatives}
        r.decision_trace.append("abstain: operative term not located")
    else:
        r.decision_trace.append(f"answer: operative={operative_key}; no genuine unresolved conflict")
    return r


# preregistered ablations
ABLATIONS = {
    "C0_g3_control": None,
    "C1_extract": Config(extract=True, scope=False, classify=False, resolve_abstain=False),
    "C2_scope": Config(extract=True, scope=True, classify=False, resolve_abstain=False),
    "C3_classify": Config(extract=True, scope=True, classify=True, resolve_abstain=False),
    "C4_full": Config(extract=True, scope=True, classify=True, resolve_abstain=True),
}
