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

# versioned StoryGraph schema (§1 "versioned schema")
STORYGRAPH_SCHEMA_VERSION = "ctd.storygraph/1.0.0"

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

    def endpoints(self) -> tuple[str, ...]:
        if self.kind in (REQUIRES_CORROBORATION, COVERED_BY_AUTHORIZATION):
            return (self.a,)
        return (self.a, self.b)


def order(a, b):
    return Edge(ORDER, a, b)


def same_entity(a, b, dim):
    return Edge(SAME_ENTITY, a, b, dim=dim)


def within(a, b, max_gap):
    return Edge(WITHIN, a, b, max_gap=max_gap)


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


# default frozen weights (human-set, NOT learned) — sum need not be 1; normalized.
DEFAULT_WEIGHTS = {
    "coverage": 0.35, "ordering_consistency": 0.15, "entity_consistency": 0.25,
    "timing_consistency": 0.10, "corroboration": 0.05, "proximity": 0.10,
}


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

    def is_complete(self) -> bool:
        return (not self.missing_required and self.completion_present
                and not self.risk.gate_triggered and not self.unavailable
                and not self.contradicts_triggered)

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
            "contradicts_triggered": self.contradicts_triggered,
            "evaluable_edges": self.evaluable_edges,
            "bounded": self.bounded, "match_digest": self.match_digest,
        }


_MAX_CANDIDATES_PER_NODE = 6
_MAX_COMBINATIONS = 4096


def _edge_ok(edge: Edge, binding: dict, events_by_id: dict, present: set,
             all_frag_ids: set) -> bool | None:
    """True/False if evaluable, None if an endpoint is absent (not yet evaluable)."""
    if edge.kind == COVERED_BY_AUTHORIZATION:
        return None  # legit-graph annotation; not evaluated on the harmful events
    if edge.kind == REQUIRES_CORROBORATION:
        if edge.a not in present:
            return None
        return edge.corroborating_fragment in all_frag_ids
    a, b = edge.a, edge.b
    if a not in binding or b not in binding:
        return None
    ea, eb = events_by_id[binding[a]], events_by_id[binding[b]]
    if edge.kind == ORDER:
        return ea.coord < eb.coord
    if edge.kind == SAME_ENTITY:
        va, vb = ea.entities.get(edge.dim, ""), eb.entities.get(edge.dim, "")
        return bool(va) and va == vb
    if edge.kind == WITHIN:
        return abs(eb.coord - ea.coord) <= (edge.max_gap or float("inf"))
    if edge.kind == RELATED_ACTORS:
        return True if edge.actor_mode == "ANY" else (ea.actor == eb.actor and bool(ea.actor))
    if edge.kind == CONTRADICTS:
        # fire only under the explicit incompatibility condition (§8)
        cond = edge.incompatible_when
        if cond == "BOTH_PRESENT":
            return True
        if cond.startswith("SAME_ENTITY:"):
            dim = cond.split(":", 1)[1]
            va, vb = ea.entities.get(dim, ""), eb.entities.get(dim, "")
            return bool(va) and va == vb
        if cond.startswith("DIFFERENT_ENTITY:"):
            dim = cond.split(":", 1)[1]
            va, vb = ea.entities.get(dim, ""), eb.entities.get(dim, "")
            return bool(va) and bool(vb) and va != vb
        return False  # no explicit condition ⇒ mere coexistence never fires
    return True


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

    # per-edge-kind satisfied / evaluable (HARMFUL-supporting kinds only)
    per_kind = {ORDER: [0, 0], SAME_ENTITY: [0, 0], WITHIN: [0, 0],
                RELATED_ACTORS: [0, 0], REQUIRES_CORROBORATION: [0, 0]}
    failed, satisfied, contradicts_triggered = [], [], []
    for e in graph.edges:
        ok = _edge_ok(e, binding, events_by_id, present, all_frag_ids)
        if ok is None:
            continue
        rec = {"kind": e.kind, "a": e.a, "b": e.b, "dim": e.dim}
        if e.kind == CONTRADICTS:
            if ok:
                contradicts_triggered.append({
                    **rec, "condition": e.incompatible_when,
                    "weakens": "HARMFUL", "severity": "decisive",
                    "resolution_status": "unresolved"})  # story weakened
            continue
        if e.kind not in _HARMFUL_KINDS:
            continue
        per_kind[e.kind][1] += 1
        if ok:
            per_kind[e.kind][0] += 1
            satisfied.append(rec)
        else:
            failed.append(rec)

    def frac(kind):
        s, t = per_kind[kind]
        return (s / t) if t else 1.0

    coverage = len(present_req) / len(req_ids) if req_ids else 0.0
    ordering_c = frac(ORDER)
    entity_c = frac(SAME_ENTITY)
    timing_c = frac(WITHIN)
    corr = frac(REQUIRES_CORROBORATION)
    non_completion_req = {n.node_id for n in req if not n.is_completion}
    proximity = (len(present & non_completion_req) / len(non_completion_req)
                 if non_completion_req else 1.0)

    w = graph.weights
    dims = {"coverage": coverage, "ordering_consistency": ordering_c,
            "entity_consistency": entity_c, "timing_consistency": timing_c,
            "corroboration": corr, "proximity": proximity}
    wsum = sum(w.get(k, 0) for k in dims) or 1.0
    raw = sum(w.get(k, 0) * v for k, v in dims.items()) / wsum

    gate_reasons = []
    if entity_c < graph.entity_gate:
        gate_reasons.append(f"entity_consistency {entity_c:.2f} < gate {graph.entity_gate}")
    if ordering_c < graph.ordering_gate:
        gate_reasons.append(f"ordering_consistency {ordering_c:.2f} < gate {graph.ordering_gate}")
    if graph.timing_gate and timing_c < graph.timing_gate:
        gate_reasons.append(f"timing_consistency {timing_c:.2f} < gate {graph.timing_gate}")
    gate_triggered = bool(gate_reasons)
    # a structural-gate failure caps the harmful score below the threat threshold
    harmful = min(raw, graph.threat_threshold - 1e-9) if gate_triggered else raw

    # ordering ambiguity: an ORDER edge whose bound endpoints share a coordinate
    ordering_ambiguous = False
    for e in graph.edges:
        if e.kind == ORDER and e.a in binding and e.b in binding:
            if events_by_id[binding[e.a]].coord == events_by_id[binding[e.b]].coord:
                ordering_ambiguous = True
                break

    risk = RiskVector(coverage, ordering_c, entity_c, timing_c, corr, proximity,
                      harmful, gate_triggered, gate_reasons)
    body = {"schema": STORYGRAPH_SCHEMA_VERSION, "story": graph.ref,
            "binding": binding, "risk": risk.to_dict(),
            "completion_present": completion_present, "unavailable": unavailable,
            "contradicts": contradicts_triggered}
    return StoryMatch(
        story_ref=graph.ref, risk=risk, binding=dict(binding),
        present_nodes=sorted(present), missing_required=missing_req,
        completion_present=completion_present, failed_edges=failed,
        evaluable_edges={k: tuple(v) for k, v in per_kind.items() if v[1]},
        bounded=unavailable, match_digest=digest(body, domain="CTD-STORY"),
        unavailable=unavailable, ordering_ambiguous=ordering_ambiguous,
        multiple_optimal_bindings=optimal_count, satisfied_edges=satisfied,
        contradicts_triggered=contradicts_triggered)


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
