"""Entity-linkage layer: group events by *explicit identifiers*, never by
inferred intent.

Threat grouping must not hinge on ``correlation_id`` alone (§4). A single
capability can be assembled across many correlation IDs, by several actors, over
many sessions, mixing human and agent actions. Conversely, unrelated workflows
interleaved in the same trace must not contaminate one another, and identical
fragments under different tenants must never link.

This layer resolves, per event:

* a normalized ``tenant_id`` (isolation boundary — keys are always tenant-scoped,
  so cross-tenant linkage is impossible by construction);
* a normalized entity map (actor, agent, workflow/case, target family, credential,
  dataset, destination, device, tool, environment);
* one **assembly key** per configured :class:`AssemblyKeySpec`, plus a record of
  *which* identifiers caused the link and a deterministic linkage confidence
  (``EXACT`` / ``PARTIAL`` / ``AMBIGUOUS``) — a rule output, not a probability.

No embeddings, no LLM, no probabilistic model. Everything here is a pure function
of the event's structured fields.

Schema version: ``ctd.linkage/1.0.0`` (see LINKAGE_SCHEMA_VERSION).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .canonical import digest

LINKAGE_SCHEMA_VERSION = "ctd.linkage/1.0.0"
UNTENANTED = "__untenanted__"

_WS = re.compile(r"\s+")

# Entity dimensions the linkage layer understands. ``target_family`` is a
# coarsened projection of a resource URN (scheme + first path segment) so that
# actions on sibling resources in the same family link.
ENTITY_DIMS = (
    "actor", "agent", "workflow", "target_family",
    "credential", "dataset", "destination", "device", "tool", "environment",
    # ``correlation`` is offered as a configurable dim for legacy/synthetic
    # grouping only; §4 forbids it as the *sole* default assembly boundary.
    "correlation",
)


def _norm(value) -> str:
    if value is None:
        return ""
    return _WS.sub(" ", str(value).strip().lower())


def _target_family(resource) -> str:
    """Coarsen a resource id to a stable family key.

    ``arn:aws:s3:::billing/2026/q3`` -> ``arn:aws:s3:::billing``. A bare token is
    returned normalized. Deterministic and lossy on purpose.
    """
    r = _norm(resource)
    if not r:
        return ""
    # split on the first run of path separators after any scheme
    parts = re.split(r"[/:]+", r)
    parts = [p for p in parts if p]
    if not parts:
        return ""
    # keep scheme-ish prefix + first meaningful segment
    return ":".join(parts[: min(4, len(parts))])


def extract_entities(event: dict) -> dict[str, str]:
    """Deterministically pull normalized entity identifiers from an event.

    Understands both flat events and ActionGate canonical envelopes.
    """
    a = event.get("arguments", {}) or {}
    cred = event.get("credential_scope", {}) or {}
    tool = event.get("tool", {}) or {}
    agent_identity = event.get("agent_identity", {}) or {}
    delegator = event.get("delegator", {}) or {}
    targets = event.get("target_resource") or []
    if isinstance(targets, str):
        targets = [targets]

    ent = {
        "actor": _norm(event.get("actor") or cred.get("principal")
                       or delegator.get("id")),
        "agent": _norm(event.get("agent") or agent_identity.get("id")),
        "workflow": _norm(event.get("workflow_id") or event.get("case_id")
                          or a.get("workflow_id") or a.get("case_id")),
        "target_family": _target_family(targets[0] if targets else a.get("target")),
        "credential": _norm(event.get("credential") or a.get("credential")
                            or a.get("secret_id") or cred.get("principal")),
        "dataset": _norm(event.get("dataset") or a.get("dataset")),
        "destination": _norm(event.get("destination") or a.get("destination")
                             or a.get("sink") or a.get("cidr")),
        "device": _norm(event.get("device") or a.get("device")),
        "tool": _norm((tool.get("tool_name") or tool.get("name"))
                      if isinstance(tool, dict) else tool),
        "environment": _norm(event.get("environment") or a.get("environment")),
        "correlation": _norm(event.get("correlation_id")),
    }
    return ent


def tenant_of(event: dict) -> str:
    return _norm(event.get("tenant_id")) or UNTENANTED


@dataclass(frozen=True)
class AssemblyKeySpec:
    """A configurable, versioned grouping rule.

    ``dims`` are entity dimensions (from :data:`ENTITY_DIMS`) that, together with
    the tenant, define an assembly boundary. Excluding ``correlation_id`` on
    purpose lets one assembly span sessions/correlations.
    """

    key_id: str
    version: str
    dims: tuple[str, ...]

    def __post_init__(self) -> None:
        bad = set(self.dims) - set(ENTITY_DIMS)
        if bad:
            raise ValueError(f"assembly key spec {self.key_id!r}: unknown dims "
                             f"{sorted(bad)}")
        if not self.dims:
            raise ValueError(f"assembly key spec {self.key_id!r}: needs >=1 dim")

    @property
    def ref(self) -> str:
        return f"{self.key_id}@{self.version}"


# Named presets covering the required linkage cases.
BY_ACTOR = AssemblyKeySpec("by_actor", "1.0.0", ("actor",))
BY_CASE = AssemblyKeySpec("by_case", "1.0.0", ("workflow",))
BY_TARGET = AssemblyKeySpec("by_target", "1.0.0", ("target_family",))
BY_ACTOR_TARGET = AssemblyKeySpec("by_actor_target", "1.0.0", ("actor", "target_family"))
# Legacy / synthetic-illustration only: group strictly by correlation_id.
BY_CORRELATION = AssemblyKeySpec("by_correlation", "1.0.0", ("correlation",))


@dataclass(frozen=True)
class AssemblyLink:
    """The resolution of one event against one key spec."""

    key_spec: str          # AssemblyKeySpec.ref
    assembly_key: str      # deterministic digest, tenant-scoped; "" if ambiguous
    confidence: str        # EXACT | PARTIAL | AMBIGUOUS
    link_dims: dict[str, str]  # which normalized identifiers formed the key


@dataclass(frozen=True)
class LinkResult:
    tenant_id: str
    entities: dict[str, str]
    links: tuple[AssemblyLink, ...]
    correlation_id: str
    ambiguous: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _assembly_key(tenant: str, spec: AssemblyKeySpec, link_dims: dict[str, str]) -> str:
    body = {"tenant": tenant, "spec": spec.ref,
            "dims": {k: link_dims[k] for k in sorted(link_dims)}}
    return digest(body, domain="CTD-ASM")


def link_event(event: dict, specs: tuple[AssemblyKeySpec, ...]) -> LinkResult:
    """Resolve tenant, entities, and one AssemblyLink per spec (deterministic)."""
    tenant = tenant_of(event)
    ent = extract_entities(event)
    correlation_id = _norm(event.get("correlation_id"))
    links: list[AssemblyLink] = []
    reasons: list[str] = []
    any_key = False

    for spec in specs:
        present = {d: ent[d] for d in spec.dims if ent.get(d)}
        if not present:
            links.append(AssemblyLink(spec.ref, "", "AMBIGUOUS", {}))
            reasons.append(f"no linking identifier present for {spec.ref} "
                           f"(dims: {list(spec.dims)})")
            continue
        confidence = "EXACT" if len(present) == len(spec.dims) else "PARTIAL"
        key = _assembly_key(tenant, spec, present)
        links.append(AssemblyLink(spec.ref, key, confidence, present))
        any_key = True

    ambiguous = not any_key
    return LinkResult(
        tenant_id=tenant, entities=ent, links=tuple(links),
        correlation_id=correlation_id, ambiguous=ambiguous, reasons=tuple(reasons),
    )
