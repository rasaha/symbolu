"""Deterministic StoryPolicyPack compiler (§7).

    business/policy input
        -> validated StoryPolicyPack
        -> canonical StoryGraph
        -> legitimate CoverageRules
        -> ActionGate consequence mapping
        -> frozen policy bundle (+ digest, + source->compiled lineage)

The compiler adds no matching logic; it only *encodes* a declared pack into the
existing frozen StoryGraph objects. An AI-generated draft never publishes itself:
``compile_pack`` produces a bundle, but ``publish`` refuses without the required
human governance approvals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..canonical import digest
from ..legitimate import CoverageRule, LegitimateStory
from ..storygraph import (
    DEFAULT_PARTIAL_POLICY, Edge, PartialEscalationPolicy, StoryGraph, StoryNode,
)
from . import schema as S

COMPILER_VERSION = "ctd.policypack.compiler/1.0.0"


class CompilerError(Exception):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__("; ".join(str(e) for e in self.errors))


@dataclass
class CompiledPolicyBundle:
    policy_ref: str
    graph: StoryGraph
    legitimate_stories: tuple
    consequence_map: dict
    schema_version: str
    compiler_version: str
    graph_version: str
    matcher_version: str
    source_pack_digest: str
    bundle_digest: str
    lineage: dict
    publishable: bool
    provider_mappings: tuple = ()
    event_mappings: tuple = ()

    def to_dict(self) -> dict:
        return {
            "policy_ref": self.policy_ref, "graph_ref": self.graph.ref,
            "consequence_map": self.consequence_map,
            "schema_version": self.schema_version,
            "compiler_version": self.compiler_version,
            "graph_version": self.graph_version, "matcher_version": self.matcher_version,
            "source_pack_digest": self.source_pack_digest,
            "bundle_digest": self.bundle_digest, "lineage": self.lineage,
            "publishable": self.publishable,
        }


def _build_graph(pack: dict) -> StoryGraph:
    hs = pack["harmful_story"]
    nodes = tuple(
        StoryNode(
            node_id=n["node_id"], fragment_id=n["fragment_id"],
            title=n.get("title", n["node_id"]),
            required=n.get("required", True),
            is_completion=n.get("is_completion", False),
            specificity_class=n.get("specificity_class", "COMMON"))
        for n in hs["nodes"])
    edges = tuple(
        Edge(kind=e["kind"], a=e.get("a", ""), b=e.get("b", ""),
             dim=e.get("dim", ""), max_gap=e.get("max_gap"),
             actor_mode=e.get("actor_mode", "SAME"),
             corroborating_fragment=e.get("corroborating_fragment", ""),
             auth_tag=e.get("auth_tag", ""),
             incompatible_when=e.get("incompatible_when", ""),
             is_discriminating=e.get("is_discriminating", False))
        for e in hs["edges"])
    gates = hs.get("gates", {})
    pp = hs.get("partial_policy")
    policy = (PartialEscalationPolicy(**pp) if pp else DEFAULT_PARTIAL_POLICY)
    return StoryGraph(
        story_id=hs["story_id"], version=hs["version"],
        name=hs.get("name", hs["story_id"]), nodes=nodes, edges=edges,
        weights=hs.get("weights", dict(__import__(
            "ugence_storygraph.storygraph", fromlist=["DEFAULT_WEIGHTS"]
        ).DEFAULT_WEIGHTS)),
        entity_gate=gates.get("entity_gate", 0.999),
        ordering_gate=gates.get("ordering_gate", 0.999),
        timing_gate=gates.get("timing_gate", 0.0),
        material_floor=gates.get("material_floor", 0.40),
        threat_threshold=gates.get("threat_threshold", 0.70),
        severity=hs.get("severity", "HIGH"),
        recommended_consequence=hs.get("recommended_consequence", "HOLD_FOR_REVIEW"),
        partial_policy=policy)


def _build_legit(pack: dict) -> tuple:
    out = []
    for s in pack.get("legitimate_stories", []):
        rules = tuple(
            CoverageRule(node_id=r["node_id"], operation=r["operation"],
                         match_dims=tuple(r.get("match_dims", ("account",))),
                         amount_dim=r.get("amount_dim", ""))
            for r in s.get("rules", []))
        out.append(LegitimateStory(
            story_id=s["story_id"], version=s["version"],
            name=s.get("name", s["story_id"]), rules=rules,
            accepted_tags=frozenset(s.get("accepted_tags", []))))
    return tuple(out)


def compile_pack(pack: dict, *, approvals=None) -> CompiledPolicyBundle:
    """Validate + compile a StoryPolicyPack into a frozen bundle (deterministic)."""
    errs = S.validate_pack(pack)
    if errs:
        raise CompilerError(errs)
    try:
        graph = _build_graph(pack)               # StoryGraph.__post_init__ re-validates
    except ValueError as e:
        raise CompilerError([f"graph construction rejected: {e}"])
    legit = _build_legit(pack)
    cons = dict(pack["consequences"])

    source_pack_digest = digest(pack, domain="CTD-POLICYPACK-SRC")
    graph_body = {
        "nodes": [(n.node_id, n.fragment_id, n.required, n.is_completion,
                   n.specificity_class) for n in graph.nodes],
        "edges": [(e.kind, e.a, e.b, e.dim, e.max_gap, e.actor_mode,
                   e.corroborating_fragment, e.auth_tag, e.incompatible_when,
                   e.is_discriminating) for e in graph.edges],
        "gates": [graph.entity_gate, graph.ordering_gate, graph.timing_gate,
                  graph.material_floor, graph.threat_threshold],
        "partial_policy": [graph.partial_policy.version,
                           graph.partial_policy.min_required_coverage,
                           graph.partial_policy.min_discriminating_satisfied,
                           graph.partial_policy.min_completion_proximity],
        "weights": graph.weights}
    # this digest is byte-identical to evaluation/freeze.py's story-graph digest, so a
    # pack that faithfully encodes a frozen graph provably reproduces it (no semantics
    # change): domain "CTD-STORYGRAPH".
    graph_digest = digest(graph_body, domain="CTD-STORYGRAPH")
    legit_body = {s.ref: [(r.node_id, r.operation, r.match_dims, r.amount_dim)
                          for r in s.rules] for s in legit}
    bundle_body = {"policy": pack["policy_identity"], "graph_digest": graph_digest,
                   "legit": legit_body, "consequences": cons,
                   "schema_version": pack.get("schema_version", S.SCHEMA_VERSION),
                   "compiler_version": COMPILER_VERSION}
    bundle_digest = digest(bundle_body, domain="CTD-POLICYPACK-BUNDLE")

    gov = pack.get("governance", {})
    merged_approvals = dict(gov.get("approvals", {}))
    merged_approvals.update(approvals or {})
    publishable = bool(gov.get("human_publication_confirmed")) and all(
        merged_approvals.get(r) for r in
        ("business_owner", "control_owner", "technical_owner"))

    ident = pack["policy_identity"]
    return CompiledPolicyBundle(
        policy_ref=f"{ident['policy_id']}@{ident['policy_version']}",
        graph=graph, legitimate_stories=legit, consequence_map=cons,
        schema_version=pack.get("schema_version", S.SCHEMA_VERSION),
        compiler_version=COMPILER_VERSION,
        graph_version=pack["harmful_story"]["graph_version"],
        matcher_version=pack["harmful_story"]["matcher_version"],
        source_pack_digest=source_pack_digest, bundle_digest=bundle_digest,
        lineage={"source_pack_digest": source_pack_digest,
                 "graph_digest": graph_digest, "bundle_digest": bundle_digest},
        publishable=publishable,
        provider_mappings=tuple(pack.get("provider_mappings", [])),
        event_mappings=tuple(pack.get("event_mappings", [])))


def publish(bundle: CompiledPolicyBundle) -> None:
    """Refuse to publish an unapproved / self-published policy (§7)."""
    if not bundle.publishable:
        raise CompilerError([
            "refusing to publish: requires human publication confirmation and "
            "business/control/technical owner approvals (an AI draft must not "
            "publish itself)"])


def graph_freeze_digest(bundle: CompiledPolicyBundle) -> str:
    """The freeze-style story-graph digest of the compiled graph (for equivalence)."""
    return bundle.lineage["graph_digest"]
