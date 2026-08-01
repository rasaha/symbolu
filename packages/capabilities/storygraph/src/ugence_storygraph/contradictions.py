"""Typed contradiction evidence (§5).

Not one contradiction score — explicit typed findings, each stating which graph it
weakens (HARMFUL / LEGITIMATE / BOTH), which node or edge it affects, its
supporting evidence, and whether it is advisory or decisive. Decisive
contradictions against the legitimate story mean the authorization does not cover
the activity (hard, non-compensatory); ambiguity findings weaken both stories.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import legitimate as L

# contradiction types
APPROVAL_ACCOUNT_MISMATCH = "APPROVAL_ACCOUNT_MISMATCH"
APPROVAL_DESTINATION_MISMATCH = "APPROVAL_DESTINATION_MISMATCH"
APPROVAL_AMOUNT_EXCEEDED = "APPROVAL_AMOUNT_EXCEEDED"
APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
ACTOR_SCOPE_MISMATCH = "ACTOR_SCOPE_MISMATCH"
DEVICE_BINDING_MISMATCH = "DEVICE_BINDING_MISMATCH"
BENEFICIARY_BINDING_MATCH = "BENEFICIARY_BINDING_MATCH"
CONCEALMENT_EVENT_PRESENT = "CONCEALMENT_EVENT_PRESENT"
ORDERING_AMBIGUOUS = "ORDERING_AMBIGUOUS"
ENTITY_LINKAGE_AMBIGUOUS = "ENTITY_LINKAGE_AMBIGUOUS"

# which graph a contradiction weakens
HARMFUL = "HARMFUL"
LEGITIMATE = "LEGITIMATE"
BOTH = "BOTH"


@dataclass(frozen=True)
class Contradiction:
    type: str
    weakens: str                 # HARMFUL | LEGITIMATE | BOTH
    affects: str                 # node id or "edge:a->b" or ""
    evidence: str
    decisive: bool               # decisive vs advisory

    def to_dict(self) -> dict:
        return {"type": self.type, "weakens": self.weakens, "affects": self.affects,
                "evidence": self.evidence, "decisive": self.decisive}


def detect(harmful_match, legit_coverage, facts: dict) -> list:
    """Deterministically emit typed contradictions from match + coverage + facts."""
    out: list = []

    # from per-node legitimate coverage failures (decisive against the benign story)
    if legit_coverage is not None:
        for node_id, info in sorted(legit_coverage.per_node.items()):
            if info["status"] != L.UNCOVERED:
                continue
            reason = info.get("reason", "")
            if "account mismatch" in reason:
                out.append(Contradiction(APPROVAL_ACCOUNT_MISMATCH, LEGITIMATE,
                                         node_id, reason, True))
            elif "amount" in reason and "exceeds" in reason:
                out.append(Contradiction(APPROVAL_AMOUNT_EXCEEDED, LEGITIMATE,
                                         node_id, reason, True))
            elif "expired" in reason:
                out.append(Contradiction(APPROVAL_EXPIRED, LEGITIMATE, node_id,
                                         reason, True))
            elif "destination mismatch" in reason:
                out.append(Contradiction(APPROVAL_DESTINATION_MISMATCH, LEGITIMATE,
                                         node_id, reason, True))

    # from harmful-graph edge outcomes
    for fe in harmful_match.failed_edges:
        if fe["kind"] == "SAME_ENTITY" and fe.get("dim") == "device":
            out.append(Contradiction(DEVICE_BINDING_MISMATCH, HARMFUL,
                                     f"edge:{fe['a']}->{fe['b']}",
                                     "transfer device != enrolled device", True))
    # a satisfied beneficiary binding is corroborating harmful evidence
    ee = harmful_match.evaluable_edges.get("SAME_ENTITY")
    if ee and ee[0] >= 1 and not any(
            f["kind"] == "SAME_ENTITY" and f.get("dim") == "beneficiary"
            for f in harmful_match.failed_edges):
        # only assert the match if a beneficiary edge exists and passed
        out.append(Contradiction(BENEFICIARY_BINDING_MATCH, LEGITIMATE, "",
                                 "transfer beneficiary == newly added beneficiary",
                                 False))

    if harmful_match.ordering_ambiguous:
        out.append(Contradiction(ORDERING_AMBIGUOUS, BOTH, "",
                                 "an ordering edge could not be resolved", False))

    # explicit facts (deterministic)
    if facts.get("destination_authorized") is False:
        out.append(Contradiction(APPROVAL_DESTINATION_MISMATCH, LEGITIMATE, "",
                                 "outbound destination not authorized", True))
    if facts.get("amount_within_cap") is False:
        out.append(Contradiction(APPROVAL_AMOUNT_EXCEEDED, LEGITIMATE, "",
                                 "value exceeds approved amount", True))
    if facts.get("after_approval_expiry") is True:
        out.append(Contradiction(APPROVAL_EXPIRED, LEGITIMATE, "",
                                 "activity after approval window", True))
    if facts.get("actor_scope_ok") is False:
        out.append(Contradiction(ACTOR_SCOPE_MISMATCH, LEGITIMATE, "",
                                 "actor outside approved scope", True))
    if facts.get("concealment_present") is True:
        out.append(Contradiction(CONCEALMENT_EVENT_PRESENT, LEGITIMATE, "",
                                 "control-bypass/concealment behavior present", False))
    if facts.get("linkage_confident") is False:
        out.append(Contradiction(ENTITY_LINKAGE_AMBIGUOUS, BOTH, "",
                                 "actors/resources cannot be reliably linked", False))
    # dedupe deterministically by (type, affects)
    seen, uniq = set(), []
    for c in out:
        k = (c.type, c.affects)
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq
