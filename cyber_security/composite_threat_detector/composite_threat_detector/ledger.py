"""Multi-timescale state + persistent capability ledger (§3, §13).

A short recent-event window, on its own, does **not** stop a low-and-slow
adversary — it *helps* one, by letting an early part scroll out of view before
the last part lands. This module implements the corrected model:

1. **Short operational window** — recent raw-event bookkeeping (diagnostics,
   ordering) with a bounded count.
2. **Medium case history** — the assembly's fragment record over the workflow.
3. **Persistent capability ledger** — PERSISTENT fragments (a credential
   obtained, a privilege granted, a foothold) survive here until explicitly
   revoked, so a durable part never silently disappears.
4. **Decaying evidence** — TRANSIENT fragments lose weight smoothly
   (``0.5 ** (elapsed / half_life)``) rather than being abruptly deleted; below a
   floor they are retained as ``DECAYED`` (recorded, non-contributing), not lost.
5. **Explicit lifecycle** — the layer distinguishes *event expiry* (raw event
   ages out of the short window), *evidence decay* (weight below floor),
   *case closure* (explicit), and *administrative reset* (explicit). None of
   these is a silent count-window deletion.

Determinism: all aging is computed against an **evaluation time supplied as event
data** (epoch seconds when timestamps are present, else the monotonic step
position) — never wall-clock. Bounded state is enforced; exhaustion is reported
to the analyzer as ``UNAVAILABLE`` (fail-loud), never as silent evidence loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import PERSISTENT, FragmentInstance

# instance lifecycle states
ACTIVE = "ACTIVE"        # contributes to matching
DECAYED = "DECAYED"      # retained, weight below floor, not contributing
REVOKED = "REVOKED"      # a persistent capability explicitly revoked
CLOSED = "CLOSED"        # the case was closed


@dataclass(frozen=True)
class TimescalePolicy:
    """How state ages. Units are 'seconds' (timestamps present) or 'steps'."""

    unit: str = "steps"
    decay_half_life: float = 50.0     # transient evidence half-life
    decay_floor: float = 0.25         # weight below this ⇒ DECAYED
    short_window: int = 25            # raw-event bookkeeping window (diagnostics)
    case_window: float | None = None  # optional medium-horizon cap (units)

    def __post_init__(self) -> None:
        if self.unit not in ("seconds", "steps"):
            raise ValueError(f"bad timescale unit {self.unit!r}")
        if self.decay_half_life <= 0:
            raise ValueError("decay_half_life must be > 0")
        if not 0.0 <= self.decay_floor < 1.0:
            raise ValueError("decay_floor must be in [0, 1)")


@dataclass(frozen=True)
class StateLimits:
    """Bounded-state caps. Breach ⇒ UNAVAILABLE (fail-visible), never silent drop.

    The first three are enforced structurally by the ledger; the rest are
    enforced by the ResourceGovernor (§7) and surfaced in findings + audit log.
    """

    max_tenants: int = 10_000
    max_assemblies_per_tenant: int = 50_000
    max_instances_per_assembly: int = 10_000
    # governance (§7)
    max_assemblies_per_actor: int = 25_000
    max_candidate_linkages_per_event: int = 16
    max_recipe_evaluations: int = 10_000
    max_benign_records_per_assembly: int = 512
    max_replay_backlog: int = 1_000_000


class LimitExceeded(Exception):
    """Raised when a bounded-state cap would be violated (fail-loud)."""

    def __init__(self, scope: str, detail: str):
        super().__init__(f"{scope}: {detail}")
        self.scope = scope
        self.detail = detail


@dataclass
class _LedgerInstance:
    inst: FragmentInstance
    t: float               # aging coordinate (epoch or position)
    state: str = ACTIVE

    def weight(self, now: float, policy: TimescalePolicy) -> float:
        if self.state in (REVOKED, CLOSED):
            return 0.0
        if self.inst.decay_class == PERSISTENT:
            return 1.0
        elapsed = max(0.0, now - self.t)
        return 0.5 ** (elapsed / policy.decay_half_life)


@dataclass
class Assembly:
    tenant_id: str
    assembly_key: str
    key_spec: str
    instances: list[_LedgerInstance] = field(default_factory=list)
    seen_event_ids: set[str] = field(default_factory=set)
    seen_idempotency_keys: set[str] = field(default_factory=set)
    first_position: int | None = None
    last_position: int = 0
    first_t: float | None = None
    last_t: float | None = None
    closed: bool = False
    link_dims: dict[str, str] = field(default_factory=dict)
    related_correlations: set[str] = field(default_factory=set)
    # phase-2 additions (all backward-compatible defaults)
    lifecycle: str = "OPEN"                 # OPEN|DECAYING|CLOSED|EXPIRED|RESET|SUPERSEDED
    bound_recipe_versions: dict = field(default_factory=dict)  # recipe_id -> version
    max_severity_rank: int = 0              # for priority retention
    actors: set = field(default_factory=set)
    ingest_count: int = 0

    def active(self, now: float, policy: TimescalePolicy) -> list[_LedgerInstance]:
        """Instances that currently contribute (state ACTIVE, weight >= floor)."""
        out = []
        for li in self.instances:
            if li.state in (REVOKED, CLOSED):
                continue
            w = li.weight(now, policy)
            li.state = ACTIVE if w >= policy.decay_floor else DECAYED
            if li.state == ACTIVE:
                out.append(li)
        return out


@dataclass
class AddResult:
    added: bool
    duplicate: bool = False        # suppressed by event_id
    retried: bool = False          # suppressed by idempotency_key
    revoked_ids: tuple[str, ...] = ()


class CapabilityLedger:
    """All assemblies, keyed by (tenant_id, assembly_key). Bounded + deterministic."""

    def __init__(self, policy: TimescalePolicy, limits: StateLimits):
        self.policy = policy
        self.limits = limits
        self._by_tenant: dict[str, dict[str, Assembly]] = {}

    # -- lifecycle ---------------------------------------------------------
    def get(self, tenant_id: str, assembly_key: str) -> Assembly | None:
        return self._by_tenant.get(tenant_id, {}).get(assembly_key)

    def _ensure(self, tenant_id, assembly_key, key_spec, link_dims) -> Assembly:
        tenants = self._by_tenant
        if tenant_id not in tenants:
            if len(tenants) >= self.limits.max_tenants:
                raise LimitExceeded("tenants",
                                    f"max_tenants={self.limits.max_tenants} reached")
            tenants[tenant_id] = {}
        asm_map = tenants[tenant_id]
        asm = asm_map.get(assembly_key)
        if asm is None:
            if len(asm_map) >= self.limits.max_assemblies_per_tenant:
                raise LimitExceeded(
                    "assemblies",
                    f"max_assemblies_per_tenant={self.limits.max_assemblies_per_tenant} "
                    f"reached for tenant {tenant_id!r}")
            asm = Assembly(tenant_id=tenant_id, assembly_key=assembly_key,
                           key_spec=key_spec, link_dims=dict(link_dims))
            asm_map[assembly_key] = asm
        return asm

    def add(
        self, tenant_id, assembly_key, key_spec, link_dims,
        instances: list[FragmentInstance], now: float,
        *, event_id: str, idempotency_key: str, correlation_id: str,
        revokes: tuple[str, ...] = (),
    ) -> AddResult:
        """Insert an event's fragments into its assembly, with dedup + limits.

        Raises :class:`LimitExceeded` (fail-loud) on bounded-state breach.
        """
        asm = self._ensure(tenant_id, assembly_key, key_spec, link_dims)
        if asm.closed:
            # a closed case does not accumulate further; caller may reopen via reset
            return AddResult(added=False)

        # dedup: exact duplicate (same event id) or retry (same idempotency key)
        if event_id and event_id in asm.seen_event_ids:
            return AddResult(added=False, duplicate=True)
        if idempotency_key and idempotency_key in asm.seen_idempotency_keys:
            return AddResult(added=False, retried=True)

        # revocations first (a rotation event can retire prior persistent capability)
        revoked_ids: list[str] = []
        for li in asm.instances:
            if li.inst.fragment_id in revokes and li.state == ACTIVE:
                li.state = REVOKED
                revoked_ids.append(li.inst.fragment_id)

        if instances and (len(asm.instances) + len(instances)
                          > self.limits.max_instances_per_assembly):
            raise LimitExceeded(
                "instances",
                f"max_instances_per_assembly="
                f"{self.limits.max_instances_per_assembly} reached for assembly "
                f"{assembly_key[:16]}…")

        if event_id:
            asm.seen_event_ids.add(event_id)
        if idempotency_key:
            asm.seen_idempotency_keys.add(idempotency_key)
        if correlation_id:
            asm.related_correlations.add(correlation_id)

        for inst in instances:
            asm.instances.append(_LedgerInstance(inst=inst, t=now))
            if asm.first_position is None:
                asm.first_position = inst.position
                asm.first_t = now
            asm.last_position = max(asm.last_position, inst.position)
            asm.last_t = now
        for d, v in link_dims.items():
            asm.link_dims.setdefault(d, v)

        return AddResult(added=bool(instances), revoked_ids=tuple(revoked_ids))

    def close_case(self, tenant_id: str, assembly_key: str) -> bool:
        asm = self.get(tenant_id, assembly_key)
        if asm is None:
            return False
        asm.closed = True
        for li in asm.instances:
            li.state = CLOSED
        return True

    def reset(self, tenant_id: str, assembly_key: str) -> bool:
        """Administrative reset — remove the assembly entirely (audited by caller)."""
        asm_map = self._by_tenant.get(tenant_id)
        if asm_map and assembly_key in asm_map:
            del asm_map[assembly_key]
            return True
        return False

    # -- introspection -----------------------------------------------------
    def tenant_count(self) -> int:
        return len(self._by_tenant)

    def assembly_count(self, tenant_id: str) -> int:
        return len(self._by_tenant.get(tenant_id, {}))
