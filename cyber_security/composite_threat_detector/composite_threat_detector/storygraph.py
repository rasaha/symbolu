"""Story-graph engine — structural assembly measurement (not event counting).

A *story graph* represents a known harmful (or, symmetrically, a legitimate)
pattern as a typed graph rather than a flat checklist:

* **Nodes** are capability events (reusing the fragment vocabulary).
* **Edges** are typed constraints between *specific* node pairs:
  ``Order`` (before→after), ``SameEntity(dim)`` (same beneficiary/device/account),
  ``Within`` (max time gap), ``RelatedActors`` (same / any), and
  ``RequiresCorroboration`` (a corroborating fragment must be present).

Matching is a **bounded, deterministic subgraph embedding**: observed events are
assigned to nodes to maximize satisfied edges, and the result is a *decomposed*
risk vector — coverage, ordering-, entity-, timing-consistency, corroboration,
proximity — NOT a single "N of M matched" count. Escalation gates on the
structural dimensions (entity + ordering), so "3 of 5 events but the wrong
beneficiary and out of order" scores low. Everything here is deterministic and
explainable (frozen weights, sorted iteration, per-edge failure reporting); it is
advisory only, exactly like the rest of the analyzer.

This engine is domain-agnostic: it operates on :class:`ObservedEvent` views, which
can be adapted from ledger instances (:func:`from_ledger`) or built directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import digest

# versioned StoryGraph schema (§1 "versioned schema").
# 1.1.0: adds edge/node discriminating metadata + explicit CONTRADICTS condition.
STORYGRAPH_SCHEMA_VERSION = "ctd.storygraph/1.1.0"
# The matching *semantics* are versioned separately from the graph schema (§11).
# 2.0.0 corrects partial-match semantics: a non-evaluable edge is NEVER treated as
# satisfied, dimensions never default to 1.0 on a zero denominator, and partial
# stories require positive discriminating evidence before escalation.
MATCHER_SEMANTICS_VERSION = "ctd.storygraph.matcher/2.0.0"

# ---------------------------------------------------------------------------
# Explicit edge-evaluation states (§3) — every evaluated edge is exactly one.
# NOT_EVALUABLE is never conflated with SATISFIED or FAILED.
# ---------------------------------------------------------------------------
EDGE_SATISFIED = "SATISFIED"
EDGE_FAILED = "FAILED"
EDGE_NOT_EVALUABLE = "NOT_EVALUABLE"
EDGE_AMBIGUOUS = "AMBIGUOUS"

# structural-dimension statuses (§5)
DIM_SATISFIED = "SATISFIED"
DIM_FAILED = "FAILED"
DIM_PARTIAL = "PARTIAL"
DIM_NOT_EVALUABLE = "NOT_EVALUABLE"
DIM_AMBIGUOUS = "AMBIGUOUS"
DIM_NOT_APPLICABLE = "NOT_APPLICABLE"

# ---------------------------------------------------------------------------
# Edge types (§1)
# ---------------------------------------------------------------------------
ORDER = "ORDER"
SAME_ENTITY = "SAME_ENTITY"
WITHIN = "WITHIN"
RELATED_ACTORS = "RELATED_ACTORS"
REQUIRES_CORROBORATION = "REQUIRES_CORROBORATION"
CONTRADICTS = "CONTRADICTS"                        # if both present ⇒ story weakened
COVERED_BY_AUTHORIZATION = "COVERED_BY_AUTHORIZATION"  # legit-graph coverage annotation

# edge kinds that contribute to the *harmful* structural risk dimensions
_HARMFUL_KINDS = (ORDER, SAME_ENTITY, WITHIN, RELATED_ACTORS, REQUIRES_CORROBORATION)


@dataclass(frozen=True)
class Edge:
    kind: str
    a: str                      # node id
    b: str = ""                 # node id (unused for corroboration / auth annotation)
    dim: str = ""               # for SAME_ENTITY: the entity dimension
    max_gap: float | None = None  # for WITHIN: max |Δ| in the active time unit
    actor_mode: str = "SAME"    # for RELATED_ACTORS: SAME | ANY
    corroborating_fragment: str = ""  # for REQUIRES_CORROBORATION
    auth_tag: str = ""          # for COVERED_BY_AUTHORIZATION: authorization tag
    # for CONTRADICTS: the explicit mutual-incompatibility condition. Mere
    # coexistence never fires a contradiction. One of:
    #   "BOTH_PRESENT"            — the two node states are declared incompatible
    #   "SAME_ENTITY:<dim>"       — fire only if both share entity <dim>
    #   "DIFFERENT_ENTITY:<dim>"  — fire only if both differ on entity <dim>
    incompatible_when: str = ""
    # discriminating metadata (§8): a discriminating edge encodes a high-specificity
    # relationship (e.g. transfer beneficiary == the newly added beneficiary). Only
    # an *evaluated & satisfied* discriminating edge counts as positive harmful
    # evidence for partial escalation. Common/low-specificity edges do not.
    is_discriminating: bool = False

    def endpoints(self) -> tuple[str, ...]:
        if self.kind in (REQUIRES_CORROBORATION, COVERED_BY_AUTHORIZATION):
            return (self.a,)
        return (self.a, self.b)


def order(a, b, *, discriminating=False):
    return Edge(ORDER, a, b, is_discriminating=discriminating)


def same_entity(a, b, dim, *, discriminating=False):
    return Edge(SAME_ENTITY, a, b, dim=dim, is_discriminating=discriminating)


def within(a, b, max_gap, *, discriminating=False):
    return Edge(WITHIN, a, b, max_gap=max_gap, is_discriminating=discriminating)


def related_actors(a, b, mode="SAME"):
    return Edge(RELATED_ACTORS, a, b, actor_mode=mode)


def requires_corroboration(a, corroborating_fragment):
    return Edge(REQUIRES_CORROBORATION, a, corroborating_fragment=corroborating_fragment)


def contradicts(a, b, incompatible_when):
    """A CONTRADICTS edge fires only under an explicit incompatibility condition
    (§8) — mere coexistence of the two nodes is never sufficient.

    ``incompatible_when`` ∈ {"BOTH_PRESENT", "SAME_ENTITY:<dim>",
    "DIFFERENT_ENTITY:<dim>"}.
    """
    if not incompatible_when:
        raise ValueError("CONTRADICTS edge requires an explicit incompatible_when")
    return Edge(CONTRADICTS, a, b, incompatible_when=incompatible_when)


def covered_by_authorization(a, auth_tag):
    """Legit-graph annotation: node ``a`` is covered by authorization ``auth_tag``."""
    return Edge(COVERED_BY_AUTHORIZATION, a, auth_tag=auth_tag)


# spec edge-name aliases (§1) — BEFORE/WITHIN_TIME/SAME_* map onto the primitives
def before(a, b):
    return order(a, b)


def within_time(a, b, max_gap):
    return within(a, b, max_gap)


def same_account(a, b):
    return same_entity(a, b, "account")


def same_device(a, b):
    return same_entity(a, b, "device")


def same_beneficiary(a, b):
    return same_entity(a, b, "beneficiary")


def same_destination(a, b):
    return same_entity(a, b, "destination")


def related_actor(a, b, mode="SAME"):
    return related_actors(a, b, mode)


@dataclass(frozen=True)
class StoryNode:
    node_id: str
    fragment_id: str            # the capability fragment this node requires
    title: str = ""
    required: bool = True
    is_completion: bool = False  # a loss-producing final action
    # specificity metadata (§8): COMMON administrative events (password reset,
    # device enrollment) are low-specificity and are NOT strong harmful evidence on
    # their own; DISCRIMINATING nodes carry pattern-specific meaning.
    specificity_class: str = "COMMON"   # COMMON | DISCRIMINATING


# default frozen weights (human-set, NOT learned) — sum need not be 1; normalized.
DEFAULT_WEIGHTS = {
    "coverage": 0.35, "ordering_consistency": 0.15, "entity_consistency": 0.25,
    "timing_consistency": 0.10, "corroboration": 0.05, "proximity": 0.10,
}

# frozen partial-escalation decision policy (§7). A partial (non-completing) story
# may only be treated as escalation-eligible when POSITIVE structural evidence is
# present — never merely because common admin events occurred, the completion node
# is absent, discriminating edges were untested, or a ratio over one edge is 1.0.
PARTIAL_ESCALATION_POLICY_VERSION = "ctd.partial_escalation/1.0.0"


@dataclass(frozen=True)
class PartialEscalationPolicy:
    version: str = PARTIAL_ESCALATION_POLICY_VERSION
    min_required_coverage: float = 0.60       # required-node coverage floor
    min_discriminating_satisfied: int = 1     # >=1 discriminating mandatory edge SAT
    min_completion_proximity: float = 0.999   # all non-completion required present
    # positive-evidence alternatives to proximity (any one suffices, in addition to
    # coverage + a satisfied discriminating edge and no mandatory failure/ambiguity):
    allow_corroboration_evidence: bool = True
    allow_decisive_contradiction_evidence: bool = False  # weakens harmful, not raises


DEFAULT_PARTIAL_POLICY = PartialEscalationPolicy()


@dataclass(frozen=True)
class StoryGraph:
    story_id: str
    version: str
    name: str
    nodes: tuple[StoryNode, ...]
    edges: tuple[Edge, ...] = ()
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    # structural gates: a threat-consistent verdict requires these minima
    entity_gate: float = 0.999
    ordering_gate: float = 0.999
    timing_gate: float = 0.0          # 0 = timing is soft (low-and-slow tolerant)
    material_floor: float = 0.40      # coverage below this => no material pattern
    threat_threshold: float = 0.70    # harmful_score at/above => threat-consistent
    severity: str = "HIGH"
    recommended_consequence: str = "HOLD_FOR_REVIEW"
    partial_policy: "PartialEscalationPolicy" = field(
        default_factory=lambda: DEFAULT_PARTIAL_POLICY)

    def __post_init__(self) -> None:
        ids = {n.node_id for n in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError(f"story {self.story_id!r}: duplicate node ids")
        for e in self.edges:
            for ep in e.endpoints():
                if ep not in ids:
                    raise ValueError(f"story {self.story_id!r}: edge references "
                                     f"unknown node {ep!r}")
            if e.kind == CONTRADICTS and not e.incompatible_when:
                raise ValueError(f"story {self.story_id!r}: CONTRADICTS edge must "
                                 f"declare an explicit incompatible_when (§8)")
        if not any(n.is_completion for n in self.nodes):
            raise ValueError(f"story {self.story_id!r}: needs >=1 completion node")

    @property
    def ref(self) -> str:
        return f"{self.story_id}@{self.version}"

    def node(self, node_id: str) -> StoryNode:
        return next(n for n in self.nodes if n.node_id == node_id)

    def required_nodes(self) -> tuple[StoryNode, ...]:
        return tuple(n for n in self.nodes if n.required)


@dataclass(frozen=True)
class ObservedEvent:
    """A minimal, engine-facing view of one observed capability event."""

    fragment_id: str
    event_id: str
    position: int
    epoch: float | None
    actor: str
    entities: dict

    @property
    def coord(self) -> float:
        return float(self.epoch) if self.epoch is not None else float(self.position)


def from_ledger(active) -> list[ObservedEvent]:
    """Adapt ledger ``_LedgerInstance`` objects to ObservedEvent views."""
    out = []
    for li in active:
        inst = li.inst
        out.append(ObservedEvent(
            fragment_id=inst.fragment_id, event_id=inst.event_id,
            position=inst.position, epoch=inst.at_epoch, actor=inst.actor,
            entities=dict(inst.entities)))
    return out


# ---------------------------------------------------------------------------
# Structural-dimension result (§5) — explicit counts + status, never a bare 1.0.
# ---------------------------------------------------------------------------
@dataclass
class DimensionResult:
    dimension: str
    satisfied_count: int
    failed_count: int
    not_evaluable_count: int
    ambiguous_count: int
    applicable_count: int
    status: str
    evaluable_ratio: float | None   # over evaluable (sat+failed) ONLY; None if none

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "satisfied_count": self.satisfied_count,
            "failed_count": self.failed_count,
            "not_evaluable_count": self.not_evaluable_count,
            "ambiguous_count": self.ambiguous_count,
            "applicable_count": self.applicable_count,
            "status": self.status,
            "evaluable_ratio": (round(self.evaluable_ratio, 4)
                                if self.evaluable_ratio is not None else None),
        }


def _dim_result(dimension, sat, failed, ne, amb) -> DimensionResult:
    applicable = sat + failed + ne + amb
    evaluable = sat + failed
    ratio = (sat / evaluable) if evaluable else None
    if applicable == 0:
        status = DIM_NOT_APPLICABLE
    elif failed > 0:
        status = DIM_FAILED                     # a proven-false edge — non-compensatory
    elif evaluable == 0:
        status = DIM_AMBIGUOUS if amb > 0 else DIM_NOT_EVALUABLE
    elif sat == applicable:
        status = DIM_SATISFIED
    else:
        status = DIM_PARTIAL                     # some satisfied, some untested/ambiguous
    return DimensionResult(dimension, sat, failed, ne, amb, applicable, status, ratio)


# ---------------------------------------------------------------------------
# Risk vector + match result
# ---------------------------------------------------------------------------
@dataclass
class RiskVector:
    coverage: float
    ordering_consistency: float
    entity_consistency: float
    timing_consistency: float
    corroboration: float
    proximity: float
    harmful_score: float
    gate_triggered: bool
    gate_reasons: list

    def to_dict(self) -> dict:
        return {
            "coverage": round(self.coverage, 4),
            "ordering_consistency": round(self.ordering_consistency, 4),
            "entity_consistency": round(self.entity_consistency, 4),
            "timing_consistency": round(self.timing_consistency, 4),
            "corroboration": round(self.corroboration, 4),
            "proximity": round(self.proximity, 4),
            "harmful_score": round(self.harmful_score, 4),
            "gate_triggered": self.gate_triggered, "gate_reasons": self.gate_reasons,
        }


@dataclass
class StoryMatch:
    story_ref: str
    risk: RiskVector
    binding: dict                 # node_id -> event_id
    present_nodes: list
    missing_required: list
    completion_present: bool
    failed_edges: list
    evaluable_edges: dict         # kind -> (satisfied, total)
    bounded: bool
    match_digest: str
    unavailable: bool = False              # matcher limit exceeded (fail-visible)
    ordering_ambiguous: bool = False       # an ORDER edge has unresolved (equal) coords
    multiple_optimal_bindings: int = 1     # count of bindings achieving the best score
    satisfied_edges: list = field(default_factory=list)   # which edges are satisfied
    contradicts_triggered: list = field(default_factory=list)  # CONTRADICTS edges fired
    # §3/§4/§5 explicit partial-match reporting
    edge_results: list = field(default_factory=list)      # per-edge full state record
    not_evaluable_edges: list = field(default_factory=list)
    ambiguous_edges: list = field(default_factory=list)
    dimension_results: dict = field(default_factory=dict)  # dim -> DimensionResult dict
    mandatory_unsatisfied: bool = False   # a mandatory edge is FAILED/AMBIGUOUS/NE
    # §7 positive-evidence partial-escalation gate
    escalation_eligible: bool = False
    escalation_reasons: list = field(default_factory=list)
    discriminating_satisfied: int = 0
    matcher_semantics_version: str = MATCHER_SEMANTICS_VERSION

    def is_complete(self) -> bool:
        """Exact completion requires every required node present AND every mandatory
        edge positively SATISFIED (§9, fail-closed). A mandatory edge that is
        FAILED / AMBIGUOUS / NOT_EVALUABLE never counts as satisfied."""
        return not self.completion_blockers()

    def completion_blockers(self) -> list:
        """The explicit reasons exact completion is not proven (empty => complete)."""
        blockers = []
        if self.unavailable:
            blockers.append("matcher_unavailable")
        if self.missing_required:
            blockers.append("missing_required:" + ",".join(self.missing_required))
        if not self.completion_present:
            blockers.append("no_completion_node")
        if self.mandatory_unsatisfied:
            blockers.append("mandatory_edge_not_positively_satisfied")
        if self.risk.gate_triggered:
            blockers.append("structural_gate:" + ";".join(self.risk.gate_reasons))
        if self.contradicts_triggered:
            blockers.append("contradiction_fired")
        return blockers

    def mandatory_edge_states(self) -> list:
        """The state of every mandatory (all-endpoints-required) edge, for proofs."""
        return [r for r in self.edge_results if r.get("mandatory")]

    def to_dict(self) -> dict:
        return {
            "story_ref": self.story_ref, "risk": self.risk.to_dict(),
            "unavailable": self.unavailable,
            "ordering_ambiguous": self.ordering_ambiguous,
            "multiple_optimal_bindings": self.multiple_optimal_bindings,
            "binding": self.binding, "present_nodes": self.present_nodes,
            "missing_required": self.missing_required,
            "completion_present": self.completion_present,
            "failed_edges": self.failed_edges, "satisfied_edges": self.satisfied_edges,
            "not_evaluable_edges": self.not_evaluable_edges,
            "ambiguous_edges": self.ambiguous_edges,
            "contradicts_triggered": self.contradicts_triggered,
            "evaluable_edges": self.evaluable_edges,
            "edge_results": self.edge_results,
            "dimension_results": self.dimension_results,
            "mandatory_unsatisfied": self.mandatory_unsatisfied,
            "escalation_eligible": self.escalation_eligible,
            "escalation_reasons": self.escalation_reasons,
            "discriminating_satisfied": self.discriminating_satisfied,
            "matcher_semantics_version": self.matcher_semantics_version,
            "bounded": self.bounded, "match_digest": self.match_digest,
        }


_MAX_CANDIDATES_PER_NODE = 6
_MAX_COMBINATIONS = 4096


def _edge_state(edge: Edge, binding: dict, events_by_id: dict, present: set,
                all_frag_ids: set) -> tuple[str, dict]:
    """Return the explicit edge-evaluation state (§3) + a detail record (§4).

    NOT_EVALUABLE is returned whenever an endpoint node is unbound or the evidence
    needed to judge the edge is absent — it is NEVER conflated with SATISFIED. For
    CONTRADICTS, a fired incompatibility maps to FAILED (the harmful hypothesis is
    weakened); a non-fired evaluable one maps to SATISFIED (harmful intact).
    """
    if edge.kind == COVERED_BY_AUTHORIZATION:
        return EDGE_NOT_EVALUABLE, {"reason": "legit-graph annotation; not scored "
                                    "on harmful events"}
    if edge.kind == REQUIRES_CORROBORATION:
        if edge.a not in present:
            return EDGE_NOT_EVALUABLE, {"reason": f"anchor node {edge.a!r} absent"}
        ok = edge.corroborating_fragment in all_frag_ids
        return ((EDGE_SATISFIED if ok else EDGE_FAILED),
                {"corroborating_fragment": edge.corroborating_fragment,
                 "observed": ok})
    a, b = edge.a, edge.b
    if a not in binding or b not in binding:
        missing = [n for n in (a, b) if n not in binding]
        return EDGE_NOT_EVALUABLE, {"reason": "endpoint node(s) absent",
                                    "missing_nodes": missing}
    ea, eb = events_by_id[binding[a]], events_by_id[binding[b]]
    if edge.kind == ORDER:
        if ea.coord == eb.coord:
            return EDGE_AMBIGUOUS, {"reason": "endpoints share a coordinate; order "
                                    "unresolved", "coord": ea.coord}
        return ((EDGE_SATISFIED if ea.coord < eb.coord else EDGE_FAILED),
                {"a_coord": ea.coord, "b_coord": eb.coord})
    if edge.kind == SAME_ENTITY:
        va, vb = ea.entities.get(edge.dim, ""), eb.entities.get(edge.dim, "")
        if not va or not vb:
            return EDGE_NOT_EVALUABLE, {"reason": f"entity {edge.dim!r} missing on "
                                        "an endpoint", "dim": edge.dim,
                                        "expected": va, "observed": vb}
        return ((EDGE_SATISFIED if va == vb else EDGE_FAILED),
                {"dim": edge.dim, "expected": va, "observed": vb})
    if edge.kind == WITHIN:
        gap = abs(eb.coord - ea.coord)
        return ((EDGE_SATISFIED if gap <= (edge.max_gap or float("inf"))
                 else EDGE_FAILED), {"gap": gap, "max_gap": edge.max_gap})
    if edge.kind == RELATED_ACTORS:
        if edge.actor_mode == "ANY":
            return EDGE_SATISFIED, {"mode": "ANY"}
        if not ea.actor or not eb.actor:
            return EDGE_NOT_EVALUABLE, {"reason": "actor missing on an endpoint"}
        return ((EDGE_SATISFIED if ea.actor == eb.actor else EDGE_FAILED),
                {"a_actor": ea.actor, "b_actor": eb.actor})
    if edge.kind == CONTRADICTS:
        cond = edge.incompatible_when
        va = vb = ""
        if cond.startswith("SAME_ENTITY:") or cond.startswith("DIFFERENT_ENTITY:"):
            dim = cond.split(":", 1)[1]
            va, vb = ea.entities.get(dim, ""), eb.entities.get(dim, "")
            if not va or not vb:
                return EDGE_NOT_EVALUABLE, {"reason": f"entity {dim!r} missing; "
                                            "contradiction not evaluable", "dim": dim}
        if cond == "BOTH_PRESENT":
            fired = True
        elif cond.startswith("SAME_ENTITY:"):
            fired = va == vb
        elif cond.startswith("DIFFERENT_ENTITY:"):
            fired = va != vb
        else:
            fired = False  # no explicit condition ⇒ mere coexistence never fires
        # a fired contradiction FAILS the harmful hypothesis for this edge.
        return ((EDGE_FAILED if fired else EDGE_SATISFIED),
                {"condition": cond, "fired": fired})
    return EDGE_SATISFIED, {}


def _edge_ok(edge: Edge, binding: dict, events_by_id: dict, present: set,
             all_frag_ids: set) -> bool | None:
    """Back-compat tri-state: True=SATISFIED, False=FAILED, None=NOT_EVALUABLE.

    AMBIGUOUS collapses to None (not evaluable to a definite pass/fail). CONTRADICTS
    keeps its historical meaning here (True == the contradiction FIRES) so
    ``_score_binding`` and the legacy contradicts reporting are unchanged.
    """
    if edge.kind == CONTRADICTS:
        state, detail = _edge_state(edge, binding, events_by_id, present, all_frag_ids)
        if state == EDGE_NOT_EVALUABLE:
            return None
        return bool(detail.get("fired"))
    state, _ = _edge_state(edge, binding, events_by_id, present, all_frag_ids)
    if state == EDGE_SATISFIED:
        return True
    if state == EDGE_FAILED:
        return False
    return None  # NOT_EVALUABLE or AMBIGUOUS


def _score_binding(graph: StoryGraph, binding: dict, events_by_id: dict, present: set,
                   all_frag_ids: set) -> int:
    """Score = satisfied HARMFUL-supporting edges minus fired CONTRADICTS edges."""
    n = 0
    for e in graph.edges:
        ok = _edge_ok(e, binding, events_by_id, present, all_frag_ids)
        if not ok:
            continue
        if e.kind in _HARMFUL_KINDS:
            n += 1
        elif e.kind == CONTRADICTS:
            n -= 1
    return n


def match(graph: StoryGraph, events: list[ObservedEvent]) -> StoryMatch:
    """Deterministic bounded subgraph embedding + decomposed risk vector."""
    events_by_id = {e.event_id: e for e in events}
    all_frag_ids = {e.fragment_id for e in events}
    # candidate events per node (deterministically ordered), capped
    cands: dict[str, list[str]] = {}
    for node in graph.nodes:
        matches = sorted((e for e in events if e.fragment_id == node.fragment_id),
                         key=lambda e: (e.position, e.coord, e.event_id))
        cands[node.node_id] = [e.event_id for e in matches[:_MAX_CANDIDATES_PER_NODE]]
    present_ids = [n.node_id for n in graph.nodes if cands[n.node_id]]
    present = set(present_ids)

    # search bindings over present nodes to maximize satisfied edges (bounded)
    combos = 1
    for nid in present_ids:
        combos *= max(1, len(cands[nid]))
    unavailable = combos > _MAX_COMBINATIONS
    optimal_count = 1
    if not unavailable:
        best_binding, best_score, optimal_count = _exhaustive(
            graph, present_ids, cands, events_by_id, present, all_frag_ids)
    else:
        # limit exceeded: keep a deterministic greedy binding for explainability,
        # but report UNAVAILABLE (fail-visible) — never a silent best-guess verdict.
        best_binding = {nid: cands[nid][0] for nid in present_ids}

    return _build_match(graph, best_binding, events_by_id, present, all_frag_ids,
                        unavailable, optimal_count)


def _exhaustive(graph, present_ids, cands, events_by_id, present, all_frag_ids):
    best_binding, best_score, count = {}, -1, 0

    def rec(i, binding):
        nonlocal best_binding, best_score, count
        if i == len(present_ids):
            s = _score_binding(graph, binding, events_by_id, present, all_frag_ids)
            if s > best_score:
                best_binding, best_score, count = dict(binding), s, 1
            elif s == best_score:
                count += 1
            return
        nid = present_ids[i]
        for eid in cands[nid]:
            binding[nid] = eid
            rec(i + 1, binding)
        binding.pop(nid, None)

    rec(0, {})
    return best_binding, best_score, max(1, count)


def _build_match(graph, binding, events_by_id, present, all_frag_ids, unavailable,
                 optimal_count) -> StoryMatch:
    req = graph.required_nodes()
    req_ids = {n.node_id for n in req}
    present_req = sorted(present & req_ids)
    missing_req = sorted(req_ids - present)
    completion_ids = {n.node_id for n in graph.nodes if n.is_completion}
    completion_present = bool(completion_ids & present)
    required_node_ids = req_ids

    # --- explicit per-edge evaluation (§3, §4) -------------------------------
    # count[kind] = [satisfied, failed, not_evaluable, ambiguous] for harmful kinds
    counts = {k: [0, 0, 0, 0] for k in _HARMFUL_KINDS}
    contra_counts = [0, 0, 0]   # [fired(FAILED), not_fired(SATISFIED), not_evaluable]
    edge_results, satisfied, failed = [], [], []
    not_evaluable_edges, ambiguous_edges, contradicts_triggered = [], [], []
    mandatory_unsatisfied = False
    discriminating_satisfied = 0

    def _node_endpoints(edge):
        if edge.kind in (REQUIRES_CORROBORATION, COVERED_BY_AUTHORIZATION):
            return (edge.a,)
        return (edge.a, edge.b)

    for e in graph.edges:
        state, detail = _edge_state(e, binding, events_by_id, present, all_frag_ids)
        node_eps = _node_endpoints(e)
        eps_all_required = all(graph.node(n).required for n in node_eps)
        eps_all_bound = all((n in binding) if e.kind not in
                            (REQUIRES_CORROBORATION,) else (n in present)
                            for n in node_eps)
        rec = {"edge_id": f"{e.kind}:{e.a}->{e.b}" if e.b else f"{e.kind}:{e.a}",
               "kind": e.kind, "a": e.a, "b": e.b, "dim": e.dim,
               "mandatory": eps_all_required, "is_discriminating": e.is_discriminating,
               "state": state,
               "bound_source": binding.get(e.a, ""), "bound_target": binding.get(e.b, ""),
               "detail": detail}
        edge_results.append(rec)

        if e.kind == COVERED_BY_AUTHORIZATION:
            continue
        if e.kind == CONTRADICTS:
            if state == EDGE_NOT_EVALUABLE:
                contra_counts[2] += 1
            elif detail.get("fired"):
                contra_counts[0] += 1
                contradicts_triggered.append({
                    "kind": e.kind, "a": e.a, "b": e.b, "dim": e.dim,
                    "condition": e.incompatible_when, "weakens": "HARMFUL",
                    "severity": "decisive", "resolution_status": "unresolved"})
                # a fired mandatory contradiction weakens completion
                if eps_all_required and eps_all_bound:
                    mandatory_unsatisfied = True
            else:
                contra_counts[1] += 1
            continue

        # harmful structural kinds
        idx = {EDGE_SATISFIED: 0, EDGE_FAILED: 1, EDGE_NOT_EVALUABLE: 2,
               EDGE_AMBIGUOUS: 3}[state]
        counts[e.kind][idx] += 1
        if state == EDGE_SATISFIED:
            satisfied.append(rec)
            if e.is_discriminating:
                discriminating_satisfied += 1
        elif state == EDGE_FAILED:
            failed.append(rec)
        elif state == EDGE_NOT_EVALUABLE:
            not_evaluable_edges.append(rec)
        else:
            ambiguous_edges.append(rec)
        # §6: a mandatory edge that is bound but NOT satisfied blocks completion,
        # whether it FAILED, is AMBIGUOUS, or is NOT_EVALUABLE (never "assumed ok").
        if eps_all_required and eps_all_bound and state != EDGE_SATISFIED:
            mandatory_unsatisfied = True

    # --- dimension results (§5) — counts + status, NEVER a bare 1.0 ----------
    dim_map = {"ordering_consistency": ORDER, "entity_consistency": SAME_ENTITY,
               "timing_consistency": WITHIN, "corroboration": REQUIRES_CORROBORATION}
    dim_results = {}
    for name, kind in dim_map.items():
        s, f, ne, amb = counts[kind]
        dim_results[name] = _dim_result(name, s, f, ne, amb)
    dim_results["contradictions"] = _dim_result(
        "contradictions", contra_counts[1], contra_counts[0], contra_counts[2], 0)

    coverage = len(present_req) / len(req_ids) if req_ids else 0.0
    non_completion_req = {n.node_id for n in req if not n.is_completion}
    proximity = (len(present & non_completion_req) / len(non_completion_req)
                 if non_completion_req else 1.0)
    dim_results["coverage"] = _dim_result("coverage", len(present_req),
                                          len(missing_req), 0, 0)

    # honest scalar consistency values: the evaluable ratio, or 0.0 when nothing was
    # evaluable (positive evidence absent) — NEVER 1.0 on a zero denominator.
    def _scalar(name):
        r = dim_results[name].evaluable_ratio
        return r if r is not None else 0.0
    ordering_c = _scalar("ordering_consistency")
    entity_c = _scalar("entity_consistency")
    timing_c = _scalar("timing_consistency")
    corr = _scalar("corroboration")

    # weighted harmful score: NOT_APPLICABLE dims are excluded from the denominator;
    # NOT_EVALUABLE dims contribute 0 (no positive evidence) but keep their weight,
    # so an incomplete story with untested discriminators cannot score high.
    w = graph.weights
    scalar_dims = {"coverage": coverage, "proximity": proximity,
                   "ordering_consistency": ordering_c, "entity_consistency": entity_c,
                   "timing_consistency": timing_c, "corroboration": corr}
    edge_backed = {"ordering_consistency", "entity_consistency", "timing_consistency",
                   "corroboration"}
    num = den = 0.0
    for k, v in scalar_dims.items():
        if k in edge_backed and dim_results[k].status == DIM_NOT_APPLICABLE:
            continue                       # exclude a dimension the graph never uses
        den += w.get(k, 0)
        num += w.get(k, 0) * v
    raw = (num / den) if den else 0.0

    # structural gate: fires ONLY on a genuinely evaluated failure (a dimension with
    # evaluable edges whose ratio is below the gate). A NOT_EVALUABLE dimension is
    # never a gate failure — absence of tested evidence is not proof of violation.
    gate_reasons = []

    def _gate(name, threshold):
        dr = dim_results[name]
        if threshold <= 0 or dr.evaluable_ratio is None:
            return
        if dr.evaluable_ratio < threshold:
            gate_reasons.append(f"{name} {dr.evaluable_ratio:.2f} < gate {threshold} "
                                f"(status {dr.status})")
    _gate("entity_consistency", graph.entity_gate)
    _gate("ordering_consistency", graph.ordering_gate)
    _gate("timing_consistency", graph.timing_gate)
    gate_triggered = bool(gate_reasons)
    harmful = min(raw, graph.threat_threshold - 1e-9) if gate_triggered else raw

    ordering_ambiguous = any(r["kind"] == ORDER and r["state"] == EDGE_AMBIGUOUS
                             for r in edge_results)

    # --- positive-evidence partial-escalation gate (§7) ----------------------
    pol = graph.partial_policy
    mandatory_failure = any(
        r["mandatory"] and r["state"] in (EDGE_FAILED, EDGE_AMBIGUOUS)
        for r in edge_results if r["kind"] != COVERED_BY_AUTHORIZATION)
    positive_proximity = proximity >= pol.min_completion_proximity
    positive_corr = (pol.allow_corroboration_evidence
                     and dim_results["corroboration"].satisfied_count >= 1)
    esc_reasons = []
    if coverage < pol.min_required_coverage:
        esc_reasons.append(f"coverage {coverage:.2f} < {pol.min_required_coverage}")
    if discriminating_satisfied < pol.min_discriminating_satisfied:
        esc_reasons.append(
            f"discriminating_satisfied {discriminating_satisfied} < "
            f"{pol.min_discriminating_satisfied}")
    if mandatory_failure:
        esc_reasons.append("a mandatory edge FAILED/AMBIGUOUS")
    if not (positive_proximity or positive_corr):
        esc_reasons.append("no completion-proximity or corroboration evidence")
    escalation_eligible = not esc_reasons

    risk = RiskVector(coverage, ordering_c, entity_c, timing_c, corr, proximity,
                      harmful, gate_triggered, gate_reasons)
    body = {"schema": STORYGRAPH_SCHEMA_VERSION,
            "matcher": MATCHER_SEMANTICS_VERSION, "story": graph.ref,
            "binding": binding, "risk": risk.to_dict(),
            "dims": {k: v.to_dict() for k, v in dim_results.items()},
            "completion_present": completion_present, "unavailable": unavailable,
            "mandatory_unsatisfied": mandatory_unsatisfied,
            "escalation_eligible": escalation_eligible,
            "contradicts": contradicts_triggered}
    per_kind_evaluable = {k: (counts[k][0], counts[k][0] + counts[k][1])
                          for k in _HARMFUL_KINDS if sum(counts[k])}
    return StoryMatch(
        story_ref=graph.ref, risk=risk, binding=dict(binding),
        present_nodes=sorted(present), missing_required=missing_req,
        completion_present=completion_present, failed_edges=failed,
        evaluable_edges=per_kind_evaluable,
        bounded=unavailable, match_digest=digest(body, domain="CTD-STORY"),
        unavailable=unavailable, ordering_ambiguous=ordering_ambiguous,
        multiple_optimal_bindings=optimal_count, satisfied_edges=satisfied,
        contradicts_triggered=contradicts_triggered,
        edge_results=edge_results, not_evaluable_edges=not_evaluable_edges,
        ambiguous_edges=ambiguous_edges,
        dimension_results={k: v.to_dict() for k, v in dim_results.items()},
        mandatory_unsatisfied=mandatory_unsatisfied,
        escalation_eligible=escalation_eligible, escalation_reasons=esc_reasons,
        discriminating_satisfied=discriminating_satisfied)


def from_recipe(recipe, *, completion_fragments=None) -> StoryGraph:
    """Compile a flat fragment recipe into a simple StoryGraph (backward compat, §1).

    Existing recipes keep working: each fragment becomes a node, ``ordering`` pairs
    become ORDER edges, ``pair_gaps`` become WITHIN edges. Entity edges are absent
    (flat recipes had only global scope), so the entity gate is relaxed — the
    compiled graph reproduces the flat recipe's structural expectations without
    inventing per-edge entity constraints it never had.
    """
    frag_ids = sorted(recipe.required) + sorted(set(recipe.optional) - set(recipe.required))
    if completion_fragments is None:
        befores = {a for a, b in recipe.ordering}
        afters = {b for a, b in recipe.ordering}
        completion = (afters - befores) or {sorted(recipe.required)[-1]}
    else:
        completion = set(completion_fragments)
    nodes = tuple(
        StoryNode(node_id=f, fragment_id=f, title=f,
                  required=(f in recipe.required), is_completion=(f in completion))
        for f in frag_ids)
    edges = tuple(order(a, b) for a, b in recipe.ordering)
    edges += tuple(within(a, b, hi) for (a, b), (lo, hi) in
                   getattr(recipe, "pair_gaps", {}).items() if hi is not None)
    return StoryGraph(
        story_id=f"compiled.{recipe.recipe_id}", version=recipe.version,
        name=f"compiled:{recipe.name}", nodes=nodes, edges=edges,
        entity_gate=0.0, ordering_gate=0.999, timing_gate=0.0,
        material_floor=0.40, threat_threshold=recipe.escalation_threshold,
        severity=recipe.severity,
        recommended_consequence=recipe.recommended_consequence)
