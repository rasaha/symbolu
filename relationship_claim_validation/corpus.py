"""
Self-authored SYNTHETIC relationship-claim corpus for the v0.1 experiment.

HONESTY: this corpus is authored by this experiment. It is NOT the "hidden
relationship corpus" referenced by the brief (that artifact does not exist in this
repository). Ground-truth statuses are author-assigned. Because the deterministic
judges implement the intended grounding logic, a positive result is largely
*construction/mechanism* validation, not independent evidence — see FINAL_VERDICT.md.
A handful of deliberately hard cases are included so the outcome is not trivially
perfect and false-removals/false-acceptances remain observable.

Each claim cites specific document spans. Judges reason only over span assertions;
they never see gold.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation.model import (
    ClaimStatus, Document, GoldLabel, RelationshipClaim, Span,
)

_docs: Dict[str, List[Span]] = {}
_claims: List[RelationshipClaim] = []
_gold: List[GoldLabel] = []


def _span(doc_id: str, span_id: str, text: str, **assertions) -> str:
    _docs.setdefault(doc_id, []).append(Span(span_id, text, dict(assertions)))
    return span_id


def _case(rid: str, rtype: str, src: str, tgt: str, gold: ClaimStatus,
          difficulty: int, family: str, rationale: str, *,
          docs=(), spans=(), scope=None, temporal=None, authority=None):
    _claims.append(RelationshipClaim(
        rid, rtype, src, tgt, tuple(docs), tuple(spans), scope, temporal, authority))
    _gold.append(GoldLabel(rid, gold, rationale, difficulty, family))


# =============================================================================
# SUPPORTED (12) — explicit relation span, all predicates satisfiable
# =============================================================================
for i, (src, tgt, rtype, dom) in enumerate([
    ("PolicyA", "PolicyB", "SUPERSEDES", "access_control"),
    ("RetentionA", "RetentionB", "AMENDS", "data_retention"),
    ("ProcureA", "ProcureB", "REQUIRES", "procurement"),
    ("HRLeaveA", "HRLeaveB", "SUPERSEDES", "employment"),
    ("FinApprA", "FinApprB", "REQUIRES", "financial_approval"),
    ("SafetyA", "SafetyB", "PRECEDES", "safety"),
    ("VendorA", "VendorB", "REQUIRES", "vendor"),
    ("PrivacyA", "PrivacyB", "RESTRICTS", "privacy"),
    ("IncidentA", "IncidentB", "PRECEDES", "incident_response"),
    ("RecordsA", "RecordsB", "AMENDS", "records"),
    ("LicenseA", "LicenseB", "DELEGATES_TO", "licensing"),
    ("OpsA", "OpsB", "SUPERSEDES", "operational_compliance"),
]):
    d = f"DS{i}"
    s = _span(d, f"ds{i}_1", f"{src} {rtype} {tgt} (clause).",
              source=src, target=tgt, relation=rtype)
    _case(f"S{i}", rtype, src, tgt, ClaimStatus.SUPPORTED, 2, "supported",
          "explicit relation span; all predicates satisfiable",
          docs=[d], spans=[s])

# =============================================================================
# PARTIALLY_SUPPORTED (8) — relation asserted but a narrowing dim not matched
# =============================================================================
# scope-narrowed (claim broader than the scoped evidence)
for i, (src, tgt, rtype, sc) in enumerate([
    ("PayA", "PayB", "REQUIRES", "payroll"),
    ("AccessX", "AccessY", "RESTRICTS", "contractors"),
    ("RetX", "RetY", "SUPERSEDES", "eu_region"),
]):
    d = f"DP{i}"
    s = _span(d, f"dp{i}_1", f"Within {sc}, {src} {rtype} {tgt}.",
              source=src, target=tgt, relation=rtype, scope=sc)
    _case(f"P{i}", rtype, src, tgt, ClaimStatus.PARTIALLY_SUPPORTED, 3, "partial_scope",
          "relation explicit but scoped narrower than the (unscoped) claim",
          docs=[d], spans=[s], scope=None)
# temporal-narrowed (claim window outside the evidence window)
for j, (src, tgt, rtype, tf, tt) in enumerate([
    ("TempA", "TempB", "AMENDS", 2020, 2022),
    ("TempC", "TempD", "REQUIRES", 2018, 2019),
]):
    d = f"DPT{j}"
    s = _span(d, f"dpt{j}_1", f"From {tf}-{tt}, {src} {rtype} {tgt}.",
              source=src, target=tgt, relation=rtype, temporal={"from": tf, "to": tt})
    _case(f"PT{j}", rtype, src, tgt, ClaimStatus.PARTIALLY_SUPPORTED, 4, "partial_temporal",
          "relation explicit but claim's temporal window falls outside evidence",
          docs=[d], spans=[s], temporal=(tt + 1, tt + 3))
# authority-narrowed
for k, (src, tgt, rtype, au) in enumerate([
    ("AuthA", "AuthB", "DELEGATES_TO", "regional_office"),
    ("AuthC", "AuthD", "REQUIRES", "business_unit_x"),
    ("AuthE", "AuthF", "RESTRICTS", "audit_committee"),
]):
    d = f"DPA{k}"
    s = _span(d, f"dpa{k}_1", f"Under {au}, {src} {rtype} {tgt}.",
              source=src, target=tgt, relation=rtype, authority=au)
    _case(f"PA{k}", rtype, src, tgt, ClaimStatus.PARTIALLY_SUPPORTED, 3, "partial_authority",
          "relation explicit but claimed under a different authority than evidence",
          docs=[d], spans=[s], authority="global_office")

# =============================================================================
# CONTRADICTED (8) — A finds support, B finds an explicit negation elsewhere
# =============================================================================
for i, (src, tgt, rtype) in enumerate([
    ("ConA", "ConB", "SUPERSEDES"),
    ("ConC", "ConD", "REQUIRES"),
    ("ConE", "ConF", "AMENDS"),
    ("ConG", "ConH", "RESTRICTS"),
    ("ConI", "ConJ", "PRECEDES"),
    ("ConK", "ConL", "DELEGATES_TO"),
    ("ConM", "ConN", "SUPERSEDES"),
    ("ConO", "ConP", "REQUIRES"),
]):
    d = f"DC{i}"
    sup = _span(d, f"dc{i}_sup", f"{src} {rtype} {tgt}.",
                source=src, target=tgt, relation=rtype)
    # explicit negation in a *different* document (challenger scans all docs)
    dn = f"DCN{i}"
    _span(dn, f"dcn{i}_neg", f"{src} does NOT {rtype} {tgt}; the prior clause is void.",
          source=src, target=tgt, relation=rtype, negates=True)
    _case(f"C{i}", rtype, src, tgt, ClaimStatus.CONTRADICTED, 4, "contradicted",
          "cited support exists but an explicit negation contradicts it",
          docs=[d], spans=[sup])

# =============================================================================
# UNSUPPORTED (8) — cited evidence mentions the entities but asserts no relation
# =============================================================================
for i, (src, tgt) in enumerate([
    ("UnsA", "UnsB"), ("UnsC", "UnsD"), ("UnsE", "UnsF"), ("UnsG", "UnsH"),
]):
    d = f"DU{i}"
    s = _span(d, f"du{i}_1", f"{src} and {tgt} are both enterprise policies.",
              source=src, target=tgt)  # NO relation asserted
    _case(f"U{i}", "REQUIRES", src, tgt, ClaimStatus.UNSUPPORTED, 3, "unsupported_no_relation",
          "entities co-mentioned but no relation asserted between them",
          docs=[d], spans=[s])
# duplicate-of-a-retained-claim (deterministic removal -> UNSUPPORTED)
_span("DUD", "dud_1", "PolicyA SUPERSEDES PolicyB.",
      source="PolicyA", target="PolicyB", relation="SUPERSEDES")
_case("U4", "SUPERSEDES", "PolicyA", "PolicyB", ClaimStatus.UNSUPPORTED, 2,
      "unsupported_duplicate",
      "exact duplicate of an already-retained claim (deterministic removal)",
      docs=["DUD"], spans=["dud_1"])
# illegal relationship type (deterministic removal -> UNSUPPORTED)
_span("DUL", "dul_1", "PolicyQ FROBNICATES PolicyR.",
      source="PolicyQ", target="PolicyR", relation="FROBNICATES")
_case("U5", "FROBNICATES", "PolicyQ", "PolicyR", ClaimStatus.UNSUPPORTED, 2,
      "unsupported_illegal_type",
      "illegal relationship type (schema/legality removal)",
      docs=["DUL"], spans=["dul_1"])
# self-loop (malformed direction -> UNSUPPORTED)
_span("DUS", "dus_1", "PolicyZ references itself.", source="PolicyZ", target="PolicyZ")
_case("U6", "REFERENCES", "PolicyZ", "PolicyZ", ClaimStatus.UNSUPPORTED, 2,
      "unsupported_selfloop", "self-loop malformed direction (schema removal)",
      docs=["DUS"], spans=["dus_1"])
# wrong-entity citation that still mentions neither correctly is UNSUPPORTED via
# entity present-but-relation-absent handled above; add one more no-relation case
_span("DU7", "du7_1", "VendorZ and VendorW appear in the appendix index.",
      source="VendorZ", target="VendorW")
_case("U7", "REQUIRES", "VendorZ", "VendorW", ClaimStatus.UNSUPPORTED, 3,
      "unsupported_no_relation", "co-listed in an index, no relation asserted",
      docs=["DU7"], spans=["du7_1"])

# =============================================================================
# INSUFFICIENT_EVIDENCE (8) — evidence incomplete / does not establish entities
# =============================================================================
# cited span exists but is about DIFFERENT entities (entity not established)
for i in range(3):
    d = f"DI{i}"
    s = _span(d, f"di{i}_1", "OtherX REQUIRES OtherY.",
              source="OtherX", target="OtherY", relation="REQUIRES")
    _case(f"I{i}", "REQUIRES", f"InsSrc{i}", f"InsTgt{i}",
          ClaimStatus.INSUFFICIENT_EVIDENCE, 4, "insufficient_wrong_entities",
          "cited span does not mention the claim's entities",
          docs=[d], spans=[s])
# cites a non-existent document (deterministic -> INSUFFICIENT)
_case("I3", "REQUIRES", "MissDocA", "MissDocB", ClaimStatus.INSUFFICIENT_EVIDENCE, 3,
      "insufficient_missing_doc", "cited document does not exist",
      docs=["NO_SUCH_DOC"], spans=["ghost_1"])
# cites a non-existent span in a real document (deterministic -> INSUFFICIENT)
_span("DI4", "di4_real", "SomeSrc REQUIRES SomeTgt.",
      source="SomeSrc", target="SomeTgt", relation="REQUIRES")
_case("I4", "REQUIRES", "SomeSrc", "SomeTgt", ClaimStatus.INSUFFICIENT_EVIDENCE, 4,
      "insufficient_missing_span", "cited span id absent from the cited document",
      docs=["DI4"], spans=["di4_ghost"])
# cites no evidence spans at all (deterministic -> INSUFFICIENT)
_span("DI5", "di5_1", "NoCiteSrc REQUIRES NoCiteTgt.",
      source="NoCiteSrc", target="NoCiteTgt", relation="REQUIRES")
_case("I5", "REQUIRES", "NoCiteSrc", "NoCiteTgt", ClaimStatus.INSUFFICIENT_EVIDENCE, 3,
      "insufficient_no_citation", "claim cites documents but no evidence spans",
      docs=["DI5"], spans=[])
# entity established but relation predicate partially present via a different pair
for i in range(6, 8):
    d = f"DI{i}"
    s = _span(d, f"di{i}_1", f"InsE{i} is described in the policy register.",
              source=f"InsE{i}", target="__none__")
    _case(f"I{i}", "REQUIRES", f"InsE{i}", f"InsMissing{i}",
          ClaimStatus.INSUFFICIENT_EVIDENCE, 4, "insufficient_partial",
          "only one entity of the pair appears; relation not establishable",
          docs=[d], spans=[s])

# =============================================================================
# UNKNOWN (4) — equally-explicit A/B conflict on DIRECTION -> Judge C -> manual
# =============================================================================
for i, (src, tgt, rtype) in enumerate([
    ("DirA", "DirB", "SUPERSEDES"),
    ("DirC", "DirD", "REQUIRES"),
    ("DirE", "DirF", "PRECEDES"),
    ("DirG", "DirH", "DELEGATES_TO"),
]):
    d = f"DK{i}"
    fwd = _span(d, f"dk{i}_fwd", f"{src} {rtype} {tgt}.",
                source=src, target=tgt, relation=rtype)
    # explicit reverse-exclusive assertion in another doc (equally explicit)
    dr = f"DKR{i}"
    _span(dr, f"dkr{i}_rev", f"Only {tgt} {rtype} {src}; the reverse does not hold.",
          source=tgt, target=src, relation=rtype, exclusive_direction=True)
    _case(f"K{i}", rtype, src, tgt, ClaimStatus.UNKNOWN, 5, "unknown_direction_conflict",
          "equally explicit forward support and reverse-exclusive contradiction",
          docs=[d], spans=[fwd])


# --- build immutable views ---------------------------------------------------

def documents() -> Mapping[str, Document]:
    return {d: Document(d, tuple(spans)) for d, spans in _docs.items()}


def claims() -> Tuple[RelationshipClaim, ...]:
    return tuple(_claims)


def gold() -> Mapping[str, GoldLabel]:
    return {g.relationship_id: g for g in _gold}


def public_claims() -> Tuple[dict, ...]:
    """Executable projection: claims with NO gold/family/difficulty leakage."""
    return tuple({
        "relationship_id": c.relationship_id,
        "relationship_type": c.relationship_type,
        "source_node": c.source_node,
        "target_node": c.target_node,
        "cited_document_ids": list(c.cited_document_ids),
        "cited_span_ids": list(c.cited_span_ids),
        "claimed_scope": c.claimed_scope,
        "claimed_temporal": c.claimed_temporal,
        "claimed_authority": c.claimed_authority,
    } for c in _claims)
