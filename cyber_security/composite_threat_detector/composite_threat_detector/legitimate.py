"""Verified legitimate counter-story as its own graph, with per-node coverage.

The benign explanation is not a single status — it is a graph over the *same*
observable events whose nodes are satisfied only by **verified** authorization
evidence (``COVERED_BY_AUTHORIZATION``). It can cover some nodes and not others,
producing the key finding: "account recovery covers the password reset and device
enrollment but does not cover the beneficiary addition or the transfer."

A claimed authorization is only usable if a trusted provider verified it
(``valid``); self-declared purpose covers nothing. Hard policy violations remain
non-compensatory — coverage never overrides them (see contradictions.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import digest

# per-node coverage status
COVERED = "COVERED"
UNCOVERED = "UNCOVERED"
NOT_PRESENT = "NOT_PRESENT"

# overall coverage status
FULL = "FULL"
PARTIAL = "PARTIAL"
NONE = "NONE"


@dataclass(frozen=True)
class Authorization:
    """A verified authorization record (from a trusted provider)."""

    tag: str
    valid: bool                          # True only if a provider VERIFIED it
    covered_operations: frozenset        # operations this authorization legitimizes
    account: str = ""
    device: str = ""
    beneficiary: str = ""
    destination: str = ""
    amount_cap: float | None = None
    expires_at: float | None = None
    record_id: str = ""
    source: str = ""


@dataclass(frozen=True)
class CoverageRule:
    """Which authorization can legitimize one harmful-graph node."""

    node_id: str
    operation: str
    match_dims: tuple = ("account",)     # entity dims the authorization must match
    amount_dim: str = ""                 # if set, event[amount] must be <= auth.amount_cap


@dataclass(frozen=True)
class LegitimateStory:
    story_id: str
    version: str
    name: str
    rules: tuple                         # tuple[CoverageRule]
    accepted_tags: frozenset

    @property
    def ref(self) -> str:
        return f"{self.story_id}@{self.version}"


@dataclass
class LegitimateCoverage:
    story_ref: str
    status: str                          # FULL / PARTIAL / NONE
    per_node: dict                       # node_id -> {status, by, reason}
    covered_nodes: list
    uncovered_nodes: list
    completion_covered: bool
    coverage_digest: str

    def to_dict(self) -> dict:
        return {
            "story_ref": self.story_ref, "status": self.status,
            "per_node": self.per_node, "covered_nodes": self.covered_nodes,
            "uncovered_nodes": self.uncovered_nodes,
            "completion_covered": self.completion_covered,
            "coverage_digest": self.coverage_digest,
        }


def _covers(auth: Authorization, rule: CoverageRule, event, now) -> tuple[bool, str]:
    if not auth.valid:
        return False, "authorization not verified by a trusted provider"
    if rule.operation not in auth.covered_operations:
        return False, f"operation {rule.operation} not in the authorization's scope"
    for dim in rule.match_dims:
        want = getattr(auth, dim, "")
        have = event.entities.get(dim, "")
        if want and have and want != have:
            return False, f"{dim} mismatch (authorization {want!r} != event {have!r})"
    if auth.expires_at is not None and now is not None and now > auth.expires_at:
        return False, "authorization expired"
    if rule.amount_dim and auth.amount_cap is not None:
        try:
            amt = float(event.entities.get(rule.amount_dim, "0") or 0)
        except ValueError:
            amt = 0.0
        if amt > auth.amount_cap:
            return False, f"amount {amt} exceeds cap {auth.amount_cap}"
    return True, f"covered by {auth.tag} ({auth.record_id or 'verified'})"


def coverage(legit: LegitimateStory, harmful_match, harmful_graph, events_by_id: dict,
             authorizations: list, now: float | None,
             completion_node_ids: set) -> LegitimateCoverage:
    """Per-node coverage of the HARMFUL graph's nodes by verified authorizations.

    Coverage is assessed relative to the harmful story: every *present* harmful
    node needs a legitimate rule that a verified authorization satisfies, else it
    is UNCOVERED. A recovery story that only covers reset+device therefore yields
    PARTIAL coverage of an assembly that also added a beneficiary and a transfer.
    """
    per_node: dict = {}
    covered, uncovered = [], []
    auths = [a for a in authorizations if a.tag in legit.accepted_tags]
    rules_by_node = {r.node_id: r for r in legit.rules}
    for node in harmful_graph.nodes:
        nid = node.node_id
        eid = harmful_match.binding.get(nid)
        if eid is None:
            per_node[nid] = {"status": NOT_PRESENT, "by": "", "reason": ""}
            continue
        rule = rules_by_node.get(nid)
        if rule is None:
            per_node[nid] = {"status": UNCOVERED, "by": "",
                             "reason": "no legitimate rule covers this node"}
            uncovered.append(nid)
            continue
        event = events_by_id[eid]
        best = None
        for a in auths:
            ok, reason = _covers(a, rule, event, now)
            if ok:
                best = (a, reason)
                break
            best = best or (None, reason)
        if best and best[0] is not None:
            per_node[nid] = {"status": COVERED, "by": best[0].tag, "reason": best[1]}
            covered.append(nid)
        else:
            per_node[nid] = {"status": UNCOVERED, "by": "",
                             "reason": best[1] if best else "no authorization"}
            uncovered.append(nid)

    present_nodes = [nid for nid, i in per_node.items() if i["status"] != NOT_PRESENT]
    if not covered:
        status = NONE
    elif all(per_node[n]["status"] == COVERED for n in present_nodes):
        status = FULL
    else:
        status = PARTIAL
    completion_covered = bool(completion_node_ids) and all(
        per_node.get(n, {}).get("status") == COVERED for n in completion_node_ids)

    body = {"story": legit.ref, "per_node": per_node, "status": status}
    return LegitimateCoverage(
        story_ref=legit.ref, status=status, per_node=per_node,
        covered_nodes=sorted(covered), uncovered_nodes=sorted(uncovered),
        completion_covered=completion_covered,
        coverage_digest=digest(body, domain="CTD-LEGIT"))
