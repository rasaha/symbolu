"""Canonical dependency topology — supplied, capacity-relevant dependency *evidence*.

A :class:`DependencyTopology` records which subjects/resources depend on which others for
the purpose of capacity reasoning. It is **supplied evidence**, not a proof of runtime
causality: an edge asserts "the operator/observer believes downstream capacity constrains
upstream throughput", and Phase 3 reasons over it explicitly and conservatively. Nothing
here observes traffic, calls a service mesh, or infers a graph — the topology is a canonical
input, exactly like the forecast and the cost book.

Design rules (mirroring the Phase-1/Phase-2 canonical conventions):
  * Every edge names a canonical upstream and downstream :class:`CapacitySubject`.
  * The whole topology is bound to one tenant/scope: every subject must be tenant- and
    scope-compatible with the topology's ``subject`` anchor (no cross-tenant edges).
  * Relationships are typed (:class:`DependencyKind`).
  * The topology carries an ``as_of`` effective time and an ``evidence_source`` identity.
  * Serialization is deterministic; the content digest is a stable identity (not a
    signature or a causality proof).
  * Construction fails closed on self-edges, duplicate edges, conflicting edges
    (same upstream/downstream, contradictory kind), and cross-tenant edges.

Cycle detection is available (:meth:`DependencyTopology.has_cycle`) but is NOT a
construction error here: a cycle is *reported* so the recommendation pipeline can abstain
with a typed ``DEPENDENCY_CYCLE`` reason rather than crash. A topology is a fact record; the
policy decision about what an unusable topology means lives in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest

DEPENDENCY_TOPOLOGY_SCHEMA_VERSION = "capacity-dependency-topology-1"
DEPENDENCY_EDGE_SCHEMA_VERSION = "capacity-dependency-edge-1"


class TopologyError(ValueError):
    """Raised when a dependency topology is malformed or self-contradictory (fail closed)."""


class DependencyKind(str, Enum):
    """Typed, capacity-relevant dependency relationship (upstream -> downstream)."""

    # Upstream throughput is bounded by the downstream's capacity (app -> database pool).
    CAPACITY_BOUND = "capacity_bound"
    # Upstream drains into a downstream queue/broker throughput (worker -> queue).
    THROUGHPUT_BOUND = "throughput_bound"
    # A soft/informational dependency with no capacity coupling asserted.
    INFORMATIONAL = "informational"


def _subject_scope_compatible(a: CapacitySubject, b: CapacitySubject) -> bool:
    """Exact tenant/scope compatibility using the canonical subject authority.

    Two subjects are scope-compatible when their tenant and every present placement field
    agree. ``None`` (absent) is NOT equivalent to a named value — a missing tenant never
    matches a named tenant (no missing-vs-named equivalence)."""
    for name in ("tenant_id", "environment", "cluster", "region", "zone"):
        if getattr(a, name) != getattr(b, name):
            return False
    return True


@dataclass(frozen=True)
class DependencyEdge:
    """One typed, directed dependency-evidence edge (upstream depends on downstream).

    A capacity-coupling edge (``CAPACITY_BOUND`` / ``THROUGHPUT_BOUND``) MAY carry supplied
    downstream capacity evidence: ``downstream_current_capacity`` (the dependency's current
    capacity, e.g. connection-pool size) and ``required_per_upstream_unit`` (downstream units
    needed per one unit of upstream capacity, e.g. 20 DB connections per app replica). When a
    capacity-coupling edge omits them, the recommendation pipeline fails closed with a typed
    ``MISSING_DEPENDENCY_CAPACITY`` abstention rather than guessing. An ``INFORMATIONAL`` edge
    asserts no capacity coupling and must leave both fields absent.
    """

    upstream: CapacitySubject
    downstream: CapacitySubject
    kind: DependencyKind
    downstream_current_capacity: Optional[int] = None
    required_per_upstream_unit: Optional[float] = None
    schema_version: str = DEPENDENCY_EDGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.upstream, CapacitySubject):
            raise TopologyError("edge upstream must be a CapacitySubject")
        if not isinstance(self.downstream, CapacitySubject):
            raise TopologyError("edge downstream must be a CapacitySubject")
        if not isinstance(self.kind, DependencyKind):
            raise TopologyError("edge kind must be a DependencyKind")
        if self.upstream == self.downstream:
            raise TopologyError("self-edge is not a valid dependency (upstream == downstream)")
        if self.downstream_current_capacity is not None:
            v = self.downstream_current_capacity
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise TopologyError("downstream_current_capacity must be an int >= 0 or None")
        if self.required_per_upstream_unit is not None:
            import math as _math
            v = self.required_per_upstream_unit
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not _math.isfinite(v) or v <= 0:
                raise TopologyError("required_per_upstream_unit must be a finite number > 0 or None")
        if self.kind is DependencyKind.INFORMATIONAL and (
            self.downstream_current_capacity is not None or self.required_per_upstream_unit is not None
        ):
            raise TopologyError("INFORMATIONAL edge must not carry capacity coupling evidence")

    @property
    def has_capacity_evidence(self) -> bool:
        return (self.downstream_current_capacity is not None
                and self.required_per_upstream_unit is not None)

    @property
    def key(self) -> Tuple[Any, Any]:
        """Direction-sensitive identity of the (upstream, downstream) pair."""
        return (
            tuple(sorted(self.upstream.to_canonical_dict().items())),
            tuple(sorted(self.downstream.to_canonical_dict().items())),
        )

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "upstream": self.upstream.to_canonical_dict(),
            "downstream": self.downstream.to_canonical_dict(),
            "kind": self.kind.value,
            "downstream_current_capacity": self.downstream_current_capacity,
            "required_per_upstream_unit": self.required_per_upstream_unit,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "DependencyEdge":
        if not isinstance(data, Mapping):
            raise TopologyError("edge must be a mapping")
        known = {"schema_version", "upstream", "downstream", "kind",
                 "downstream_current_capacity", "required_per_upstream_unit"}
        unknown = set(data) - known
        if unknown:
            raise TopologyError(f"unknown edge field(s): {sorted(unknown)}")
        for req in ("upstream", "downstream", "kind"):
            if req not in data:
                raise TopologyError(f"edge requires '{req}'")
        try:
            kind = DependencyKind(data["kind"])
        except ValueError as exc:
            raise TopologyError(f"unsupported dependency kind: {data['kind']!r}") from exc
        return cls(
            upstream=CapacitySubject.from_dict(data["upstream"]),
            downstream=CapacitySubject.from_dict(data["downstream"]),
            kind=kind,
            downstream_current_capacity=data.get("downstream_current_capacity"),
            required_per_upstream_unit=data.get("required_per_upstream_unit"),
            schema_version=data.get("schema_version", DEPENDENCY_EDGE_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class DependencyTopology:
    """Immutable, tenant/scope-bound set of typed dependency-evidence edges."""

    subject: CapacitySubject
    as_of: datetime
    edges: Tuple[DependencyEdge, ...] = ()
    evidence_source: Optional[str] = None
    schema_version: str = DEPENDENCY_TOPOLOGY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.subject, CapacitySubject):
            raise TopologyError("topology subject must be a CapacitySubject")
        if not isinstance(self.as_of, datetime):
            raise TopologyError("topology as_of must be a datetime")
        if self.evidence_source is not None and (
            not isinstance(self.evidence_source, str) or self.evidence_source == ""
        ):
            raise TopologyError("evidence_source must be a non-empty string or None")
        if not isinstance(self.edges, tuple):
            object.__setattr__(self, "edges", tuple(self.edges))
        seen: Dict[Tuple[Any, Any], DependencyKind] = {}
        for edge in self.edges:
            if not isinstance(edge, DependencyEdge):
                raise TopologyError("every edge must be a DependencyEdge")
            # Cross-tenant / cross-scope edges are rejected: both endpoints must be
            # scope-compatible with the topology anchor subject's tenant/scope.
            if not _subject_scope_compatible(edge.upstream, self.subject):
                raise TopologyError("cross-tenant/scope edge: upstream not scope-compatible")
            if not _subject_scope_compatible(edge.downstream, self.subject):
                raise TopologyError("cross-tenant/scope edge: downstream not scope-compatible")
            key = edge.key
            if key in seen:
                if seen[key] != edge.kind:
                    raise TopologyError(
                        "conflicting dependency evidence: same (upstream, downstream) with "
                        "contradictory kind")
                raise TopologyError("duplicate dependency edge")
            seen[key] = edge.kind

    def downstreams_of(self, subject: CapacitySubject) -> Tuple[DependencyEdge, ...]:
        """Edges whose upstream is ``subject`` (capacity-relevant dependencies)."""
        return tuple(e for e in self.edges if e.upstream == subject)

    def capacity_dependencies_of(self, subject: CapacitySubject) -> Tuple[DependencyEdge, ...]:
        """Downstream edges that assert a capacity/throughput coupling (not informational)."""
        return tuple(
            e for e in self.downstreams_of(subject)
            if e.kind in (DependencyKind.CAPACITY_BOUND, DependencyKind.THROUGHPUT_BOUND)
        )

    def has_cycle(self) -> bool:
        """True iff the directed dependency graph contains a cycle (order-independent)."""
        adj: Dict[Any, List[Any]] = {}
        for e in self.edges:
            u = tuple(sorted(e.upstream.to_canonical_dict().items()))
            d = tuple(sorted(e.downstream.to_canonical_dict().items()))
            adj.setdefault(u, []).append(d)
            adj.setdefault(d, [])
        WHITE, GREY, BLACK = 0, 1, 2
        color: Dict[Any, int] = {n: WHITE for n in adj}

        def visit(n: Any) -> bool:
            color[n] = GREY
            for m in adj.get(n, ()):
                if color[m] == GREY:
                    return True
                if color[m] == WHITE and visit(m):
                    return True
            color[n] = BLACK
            return False

        return any(color[n] == WHITE and visit(n) for n in sorted(adj))

    def to_canonical_dict(self) -> Dict[str, Any]:
        # Edges are sorted by canonical identity so digest is order-independent.
        edge_dicts = [e.to_canonical_dict() for e in self.edges]
        edge_dicts.sort(key=lambda d: (str(d["upstream"]), str(d["downstream"]), d["kind"]))
        return {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "as_of": self.as_of,
            "evidence_source": self.evidence_source,
            "edges": edge_dicts,
        }

    def digest(self) -> str:
        """Stable ``sha256:`` content identity of this supplied topology."""
        return content_digest("capacity_dependency_topology", self.schema_version,
                              self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "DependencyTopology":
        if not isinstance(data, Mapping):
            raise TopologyError("topology must be a mapping")
        known = {"schema_version", "subject", "as_of", "evidence_source", "edges"}
        unknown = set(data) - known
        if unknown:
            raise TopologyError(f"unknown topology field(s): {sorted(unknown)}")
        for req in ("subject", "as_of"):
            if req not in data:
                raise TopologyError(f"topology requires '{req}'")
        as_of = data["as_of"]
        if not isinstance(as_of, datetime):
            raise TopologyError("topology as_of must be a datetime")
        edges_raw = data.get("edges") or ()
        if not isinstance(edges_raw, (list, tuple)):
            raise TopologyError("edges must be a list")
        return cls(
            subject=CapacitySubject.from_dict(data["subject"]),
            as_of=as_of,
            edges=tuple(DependencyEdge.from_dict(e) for e in edges_raw),
            evidence_source=data.get("evidence_source"),
            schema_version=data.get("schema_version", DEPENDENCY_TOPOLOGY_SCHEMA_VERSION),
        )


__all__ = [
    "DEPENDENCY_TOPOLOGY_SCHEMA_VERSION",
    "DEPENDENCY_EDGE_SCHEMA_VERSION",
    "TopologyError",
    "DependencyKind",
    "DependencyEdge",
    "DependencyTopology",
]
