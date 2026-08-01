"""StoryPolicyPack schema + deterministic validator (§5).

A ``StoryPolicyPack`` is a plain JSON/YAML-serializable dict. ``validate_pack``
returns a list of precise, human-readable errors (empty == valid). The consequence
vocabulary is bound to the canonical StoryVerdict categories and the ActionGate
consequence names; provider/graph/matcher references must be versioned.
"""

from __future__ import annotations

from .. import storyverdict as V

SCHEMA_VERSION = "ctd.storypolicypack/1.0.0"

# canonical StoryGraph finding categories a pack must map (§5 ActionGate consequences)
FINDING_CATEGORIES = (
    "NO_MATERIAL_PATTERN",
    "PARTIAL_HARMFUL_STORY",
    "AMBIGUOUS_COMPETING_STORIES",
    "VERIFIED_LEGITIMATE_STORY",
    "LEGITIMATE_STORY_PARTIAL_COVERAGE",
    "ADDITIONAL_CONTEXT_REQUIRED",
    "THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT",
    "WOULD_COMPLETE_PROHIBITED_CAPABILITY",
    "HARD_POLICY_VIOLATION",
    "ANALYZER_UNAVAILABLE",
)

# approved ActionGate consequence vocabulary the policy may map findings onto.
# StoryGraph stays advisory: policy owns the binding consequence.
CONSEQUENCE_VOCAB = (
    "OBSERVE",
    "ADDITIONAL_CONTEXT_REQUIRED",
    "REQUIRE_REVIEW",
    "WOULD_HOLD_FOR_REVIEW",
    "HOLD_FOR_REVIEW",
    "REQUIRE_ADDITIONAL_EVIDENCE",
    "DENY",
    "UNAVAILABLE",
)

EDGE_KINDS = ("ORDER", "SAME_ENTITY", "WITHIN", "RELATED_ACTORS",
              "REQUIRES_CORROBORATION", "CONTRADICTS", "COVERED_BY_AUTHORIZATION")

_REQUIRED_TOP = ("schema_version", "policy_identity", "business_objective", "scope",
                 "canonical_action", "harmful_story", "legitimate_stories",
                 "consequences", "governance", "validation")

_ID_FIELDS = ("policy_id", "policy_name", "policy_version", "schema_version",
              "domain", "status")


def _req(obj, fields, prefix, errs):
    for f in fields:
        if f not in obj:
            errs.append(f"{prefix}: missing required '{f}'")


def validate_pack(pack: dict) -> list:
    errs: list = []
    if not isinstance(pack, dict):
        return ["pack must be an object"]
    _req(pack, _REQUIRED_TOP, "pack", errs)
    if pack.get("schema_version") not in (SCHEMA_VERSION, None):
        errs.append(f"pack.schema_version must be {SCHEMA_VERSION}")

    ident = pack.get("policy_identity", {})
    _req(ident, _ID_FIELDS, "policy_identity", errs)
    if ident.get("status") not in (None, "DRAFT", "VALIDATING", "SHADOW_APPROVED",
                                   "SHADOW_ACTIVE", "ENFORCEMENT_CANDIDATE",
                                   "ENFORCED", "SUSPENDED", "RETIRED"):
        errs.append("policy_identity.status is not a valid lifecycle state")

    _req(pack.get("business_objective", {}), ("prevent",), "business_objective", errs)
    _req(pack.get("scope", {}), ("action_types",), "scope", errs)
    _req(pack.get("canonical_action", {}),
         ("operation", "actor", "resource", "environment", "payload_digest"),
         "canonical_action", errs)

    errs += _validate_harmful_story(pack.get("harmful_story", {}))
    node_ids = {n.get("node_id") for n in pack.get("harmful_story", {}).get("nodes", [])}
    errs += _validate_legit(pack.get("legitimate_stories", []), node_ids)
    errs += _validate_consequences(pack.get("consequences", {}))
    errs += _validate_provider_mappings(pack.get("provider_mappings", []))
    errs += _validate_governance(pack.get("governance", {}), ident.get("status"))
    return errs


def _validate_harmful_story(hs: dict) -> list:
    errs: list = []
    _req(hs, ("story_id", "version", "nodes", "edges", "graph_version",
              "matcher_version"), "harmful_story", errs)
    nodes = hs.get("nodes", [])
    node_ids = set()
    for i, n in enumerate(nodes):
        _req(n, ("node_id", "fragment_id"), f"harmful_story.nodes[{i}]", errs)
        node_ids.add(n.get("node_id"))
    if nodes and not any(n.get("is_completion") for n in nodes):
        errs.append("harmful_story: needs >=1 completion node")
    frag_ids = {n.get("node_id") for n in nodes}
    for i, e in enumerate(hs.get("edges", [])):
        p = f"harmful_story.edges[{i}]"
        kind = e.get("kind")
        if kind not in EDGE_KINDS:
            errs.append(f"{p}: unknown edge kind {kind!r}")
        # endpoint checks (§7 compiler rejections surfaced early)
        for ep in ("a", "b"):
            v = e.get(ep)
            if kind == "REQUIRES_CORROBORATION" and ep == "b":
                continue
            if kind == "COVERED_BY_AUTHORIZATION" and ep == "b":
                continue
            if v and v not in frag_ids and kind not in ("REQUIRES_CORROBORATION",):
                errs.append(f"{p}: endpoint {ep}={v!r} references unknown node")
        if kind == "CONTRADICTS" and not e.get("incompatible_when"):
            errs.append(f"{p}: CONTRADICTS edge must declare an explicit "
                        "incompatible_when (mandatory contradiction condition)")
    return errs


def _validate_legit(legit: list, harmful_node_ids: set) -> list:
    errs: list = []
    for i, s in enumerate(legit):
        p = f"legitimate_stories[{i}]"
        _req(s, ("story_id", "version", "accepted_tags", "rules"), p, errs)
        for j, r in enumerate(s.get("rules", [])):
            rp = f"{p}.rules[{j}]"
            _req(r, ("node_id", "operation"), rp, errs)
            if r.get("node_id") and harmful_node_ids and \
                    r.get("node_id") not in harmful_node_ids:
                errs.append(f"{rp}: covers unknown harmful node {r.get('node_id')!r}")
    return errs


def _validate_consequences(cons: dict) -> list:
    errs: list = []
    for cat in FINDING_CATEGORIES:
        if cat not in cons:
            errs.append(f"consequences: missing mapping for finding '{cat}'")
    for cat, dec in cons.items():
        if cat not in FINDING_CATEGORIES:
            errs.append(f"consequences: unknown finding category '{cat}'")
        if dec not in CONSEQUENCE_VOCAB:
            errs.append(f"consequences[{cat}]: '{dec}' outside approved vocabulary")
    return errs


def _validate_provider_mappings(pms: list) -> list:
    errs: list = []
    for i, pm in enumerate(pms):
        p = f"provider_mappings[{i}]"
        _req(pm, ("provider_id", "provider_type", "schema_version",
                  "availability_behavior"), p, errs)
        if pm.get("schema_version") in (None, ""):
            errs.append(f"{p}: provider mapping must be versioned")
        ab = pm.get("availability_behavior")
        if ab == "ALLOW":
            errs.append(f"{p}: provider unavailability may never map to ALLOW")
    return errs


def _validate_governance(gov: dict, status) -> list:
    errs: list = []
    _req(gov, ("business_owner", "control_owner", "technical_owner",
               "required_approvers", "review_frequency"), "governance", errs)
    # enforcement requires the full approver set + explicit human publication (§7,§8)
    if status in ("ENFORCEMENT_CANDIDATE", "ENFORCED"):
        approvals = gov.get("approvals", {})
        for role in ("business_owner", "control_owner", "technical_owner", "risk"):
            if not approvals.get(role):
                errs.append(f"governance: status {status} requires approval from "
                            f"'{role}'")
        if not gov.get("human_publication_confirmed"):
            errs.append("governance: an enforced policy requires explicit human "
                        "publication (an AI draft must not publish itself)")
    return errs
