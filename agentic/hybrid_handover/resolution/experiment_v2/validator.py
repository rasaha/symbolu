#!/usr/bin/env python3
"""
Proposal Validation Layer — deterministic. Evaluates each proposed edge
INDEPENDENTLY and either accepts it into the validated graph or rejects it with a
categorized reason and a decomposable confidence vector.

Boundary: this layer sees only the parsed nodes and the v0.1 proposal output
(edges + per-edge lexical confidence + provenance needle). It never sees gold, ids,
capability, difficulty, or the hidden split. Proposal generation is unchanged;
governance and packet construction are untouched (downstream of this file).

Confidence is a VECTOR, never collapsed into one opaque score:
  lexical    — cue strength that triggered the proposal (from v0.1)
  structural — does the destination exist as a real node / named target
  authority  — is the edge direction authority/temporal-consistent for its type
  reference  — does a named reference/alias destination actually resolve

Decisions use component-wise hard gates + floors, so the vector stays interpretable.
"""

from __future__ import annotations

import re

# rejection taxonomy (frozen category slugs)
UNSUPPORTED_WORDING = "unsupported_wording"
AUTHORITY_MISMATCH = "authority_mismatch"
TEMPORAL_MISMATCH = "temporal_mismatch"
MISSING_DEST_EVIDENCE = "missing_destination_evidence"
MISSING_SRC_EVIDENCE = "missing_source_evidence"
GRAPH_CONTRADICTION = "graph_contradiction"
DUPLICATE_EDGE = "duplicate_edge"
RELATIONSHIP_AMBIGUITY = "relationship_ambiguity"
LOW_EVIDENCE = "low_evidence"
TYPE_CONFLICT = "type_conflict"

CATEGORIES = [UNSUPPORTED_WORDING, AUTHORITY_MISMATCH, TEMPORAL_MISMATCH,
              MISSING_DEST_EVIDENCE, MISSING_SRC_EVIDENCE, GRAPH_CONTRADICTION,
              DUPLICATE_EDGE, RELATIONSHIP_AMBIGUITY, LOW_EVIDENCE, TYPE_CONFLICT]

# types for which the modifying instrument must be the same-or-later node (by order)
ORDER_SENSITIVE = ("supersedes", "amends", "effective_after")
# types whose destination must resolve to a real node (dangling is invalid)
DEST_REQUIRED = ("supersedes", "amends", "overrides", "governs_over", "exception_to",
                 "conflicts_with", "effective_after")
# mutually exclusive edge families on a single (src,dst) pair
EXCLUSIVE_PAIR = {"supersedes": "amends", "amends": "supersedes"}

_SECNUM = re.compile(r"(\d+(?:\.\d+)*)")

# frozen floors (selected on the VISIBLE corpus so NO correct visible edge is
# rejected; see PROPOSAL_VALIDATION_PREREGISTRATION.md)
FLOOR_LEXICAL = 0.6
FLOOR_STRUCTURAL = 0.5


class ValidatorConfig:
    """Ablation switches. V4 (full) enables all gates."""
    def __init__(self, dedupe=True, evidence=True, authority_temporal=True,
                 type_specific=True, exclusivity=True, min_confidence=True):
        self.dedupe = dedupe
        self.evidence = evidence
        self.authority_temporal = authority_temporal
        self.type_specific = type_specific
        self.exclusivity = exclusivity
        self.min_confidence = min_confidence


def _norm_section(key):
    m = _SECNUM.search(key.split("§")[-1] if "§" in key else key)
    if not m:
        return None
    # collapse formatting differences: 7.01 -> 7.1, strip trailing zeros in decimals
    parts = m.group(1).split(".")
    parts = [p.lstrip("0") or "0" for p in parts]
    return ".".join(parts)


def _confidence_vector(nodes_by_key, edge, lexical, prov):
    src = nodes_by_key.get(edge.src)
    dst = nodes_by_key.get(edge.dst)
    dangling = bool(edge.attrs.get("dangling")) or dst is None
    t = edge.type

    # structural: destination existence / named-target quality
    if dst is not None:
        structural = 1.0
    elif t in ("references", "same_as"):
        structural = 0.5          # named but unresolved reference target
    else:
        structural = 0.0

    # authority / temporal consistency
    authority = 1.0
    if t in ORDER_SENSITIVE and src is not None and dst is not None:
        so, do = src.attrs.get("order"), dst.attrs.get("order")
        if so is not None and do is not None and not (so > do):
            authority = 0.0       # modifying instrument is not strictly later

    # reference consistency
    if t in ("references", "same_as"):
        reference = 1.0 if dst is not None else (0.5 if dangling else 0.0)
    else:
        reference = 1.0

    return {"lexical": round(float(lexical), 3), "structural": structural,
            "authority": authority, "reference": reference}


def _type_specific_ok(nodes_by_key, edge):
    """Deterministic type constraints. Returns (ok, reason_or_None)."""
    t = edge.type
    src = nodes_by_key.get(edge.src)
    dst = nodes_by_key.get(edge.dst)
    if t == "conflicts_with":
        if src is None or dst is None:
            return False, MISSING_DEST_EVIDENCE
        sa, da = src.attrs, dst.attrs
        # genuine conflict requires a differing operative attribute OR a shared
        # definition term with differing text
        operative = ("allows", "negation", "notice_days", "penalty_months")
        differs = any(sa.get(k) != da.get(k) for k in operative)
        same_def = (sa.get("definition_term") and sa.get("definition_term") == da.get("definition_term"))
        if not (differs or same_def):
            return False, TYPE_CONFLICT
    if t == "same_as":
        if dst is None:
            return True, None     # named-dangling alias handled by reference gate
        sa, da = src.attrs, dst.attrs
        shared_version = sa.get("version_base") and sa.get("version_base") == da.get("version_base")
        same_section = (_norm_section(edge.src) is not None
                        and _norm_section(edge.src) == _norm_section(edge.dst))
        if not (shared_version or same_section):
            return False, RELATIONSHIP_AMBIGUITY
    return True, None


def validate(nodes, edges, conf, prov, config: ValidatorConfig):
    """
    Returns (validated_edges, records). Each record documents proposal evidence,
    validation evidence, decision, rejection reason, and the confidence vector.
    """
    nodes_by_key = {n.key: n for n in nodes}
    validated = []
    records = []
    seen = set()
    kept_types_by_pair = {}

    for edge in edges:
        triple = edge.triple()
        t = edge.type
        vec = _confidence_vector(nodes_by_key, edge, conf.get(triple, 0.0), prov.get(triple))
        reason = None

        # --- duplicate suppression ---
        if config.dedupe and triple in seen:
            reason = DUPLICATE_EDGE

        # --- evidence consistency ---
        if reason is None and config.evidence:
            if prov.get(triple) in (None, ""):
                reason = MISSING_SRC_EVIDENCE
            elif t in DEST_REQUIRED and vec["structural"] < FLOOR_STRUCTURAL:
                reason = MISSING_DEST_EVIDENCE
            elif vec["reference"] < FLOOR_STRUCTURAL:
                reason = UNSUPPORTED_WORDING

        # --- authority / temporal ---
        if reason is None and config.authority_temporal and vec["authority"] == 0.0:
            reason = TEMPORAL_MISMATCH if t == "effective_after" else AUTHORITY_MISMATCH

        # --- type-specific constraints ---
        if reason is None and config.type_specific:
            ok, why = _type_specific_ok(nodes_by_key, edge)
            if not ok:
                reason = why

        # --- relationship exclusivity / graph contradiction ---
        if reason is None and config.exclusivity:
            pair = (edge.src, edge.dst)
            excl = EXCLUSIVE_PAIR.get(t)
            if excl and excl in kept_types_by_pair.get(pair, set()):
                reason = GRAPH_CONTRADICTION
            # cycle of the same order-sensitive type (A sup B while B sup A kept)
            if reason is None and t in ORDER_SENSITIVE and \
               t in kept_types_by_pair.get((edge.dst, edge.src), set()):
                reason = GRAPH_CONTRADICTION

        # --- minimum confidence floor ---
        if reason is None and config.min_confidence and vec["lexical"] < FLOOR_LEXICAL:
            reason = LOW_EVIDENCE

        decision = "accept" if reason is None else "reject"
        records.append({
            "src": edge.src, "dst": edge.dst, "type": t,
            "proposal_evidence": prov.get(triple),
            "validation_evidence": {
                "destination_exists": nodes_by_key.get(edge.dst) is not None,
                "authority_consistent": vec["authority"] == 1.0,
                "reference_resolves": vec["reference"] == 1.0,
            },
            "decision": decision, "rejection_reason": reason,
            "confidence_vector": vec,
        })
        if decision == "accept":
            validated.append(edge)
            seen.add(triple)
            kept_types_by_pair.setdefault((edge.src, edge.dst), set()).add(t)

    return validated, records


# preregistered ablations
ABLATIONS = {
    "V0_none": None,   # pass-through (no validation) == Hybrid v0.1
    "V1_dedupe_only": ValidatorConfig(dedupe=True, evidence=False, authority_temporal=False,
                                      type_specific=False, exclusivity=False, min_confidence=False),
    "V2_evidence_only": ValidatorConfig(dedupe=False, evidence=True, authority_temporal=False,
                                        type_specific=False, exclusivity=False, min_confidence=True),
    "V3_authority_temporal": ValidatorConfig(dedupe=False, evidence=False, authority_temporal=True,
                                             type_specific=True, exclusivity=False, min_confidence=False),
    "V4_full": ValidatorConfig(),
}
