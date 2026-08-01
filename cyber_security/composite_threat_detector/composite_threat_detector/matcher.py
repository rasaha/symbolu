"""Constraint-aware recipe matcher (§6).

Given the currently-contributing fragment instances for one assembly and one
recipe, decide the pre-benign advisory signal. Fragment *count* is necessary but
never sufficient: a sequence must also satisfy the recipe's structural
constraints — mutual exclusions, ordering, temporal gaps, actor and resource
scoping, and required corroboration — before it can escalate. A sequence that
merely "contains the same nouns" as a prohibited capability stays at OBSERVE (or
nothing), not ESCALATE.

Pure and deterministic: a function of the active instances plus the recipe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import signals
from .ledger import _LedgerInstance
from .model import Recipe


@dataclass
class MatchResult:
    recipe: Recipe
    signal: str                        # NONE | OBSERVE | ESCALATE (pre-benign)
    completeness: float
    present_required: list[str]
    missing_required: list[str]
    present_optional: list[str]
    constraints: dict[str, bool]
    impossible: bool
    impossible_reason: str
    gap_span: float | None
    contributing: dict[str, _LedgerInstance] = field(default_factory=dict)
    blocking_reasons: list[str] = field(default_factory=list)


def _by_fragment(active: list[_LedgerInstance]) -> dict[str, list[_LedgerInstance]]:
    out: dict[str, list[_LedgerInstance]] = {}
    for li in active:
        out.setdefault(li.inst.fragment_id, []).append(li)
    for v in out.values():
        v.sort(key=lambda li: (li.inst.position, li.inst.sequence_id))
    return out


def _actors(grouped, frags) -> set[str]:
    """Actors that appear across the given present fragments (intersection)."""
    sets = []
    for f in frags:
        acts = {li.inst.actor for li in grouped.get(f, []) if li.inst.actor}
        sets.append(acts)
    if not sets:
        return set()
    common = sets[0]
    for s in sets[1:]:
        common = common & s
    return common


def _families(grouped, frags) -> set[str]:
    sets = []
    for f in frags:
        fams = {li.inst.entities.get("target_family", "")
                for li in grouped.get(f, [])}
        fams = {x for x in fams if x}
        if fams:
            sets.append(fams)
    if not sets:
        return set()
    common = sets[0]
    for s in sets[1:]:
        common = common & s
    return common


def match(recipe: Recipe, active: list[_LedgerInstance]) -> MatchResult:
    grouped = _by_fragment(active)
    present = set(grouped)
    present_required = sorted(recipe.required & present)
    missing_required = sorted(recipe.required - present)
    present_optional = sorted(recipe.optional & present)
    completeness = len(present_required) / len(recipe.required)

    # pick a stable contributing instance per present fragment (earliest position)
    contributing = {f: grouped[f][0] for f in (recipe.required | recipe.optional)
                    if f in grouped}

    blocking: list[str] = []
    impossible = False
    impossible_reason = ""

    # mutually exclusive fragments both present ⇒ this recipe cannot apply
    for group in recipe.mutually_exclusive:
        both = sorted(group & present)
        if len(both) >= 2:
            impossible = True
            impossible_reason = f"mutually exclusive fragments present: {both}"
            break

    # ordering: some instance of `before` earlier than some instance of `after`.
    # Uses the universal order coordinate `li.t` (epoch when timestamps are
    # supplied, else the sequence position) so ordering holds across sessions and
    # under out-of-order arrival alike.
    ordering_ok = True
    for before, after in recipe.ordering:
        if before in grouped and after in grouped:
            min_before = min(li.t for li in grouped[before])
            max_after = max(li.t for li in grouped[after])
            if not (min_before < max_after):
                ordering_ok = False
                blocking.append(f"ordering {before}->{after} not satisfied")

    # temporal: span between first & last contributing required fragment
    gap_span = None
    temporal_ok = True
    req_ts = [li.t for f in present_required for li in grouped.get(f, [])
              if li.t is not None]
    if req_ts:
        gap_span = max(req_ts) - min(req_ts)
        if recipe.max_assembly_gap is not None and gap_span > recipe.max_assembly_gap:
            temporal_ok = False
            impossible = True  # span only grows; cannot be repaired
            impossible_reason = (f"assembly gap {gap_span} exceeds "
                                 f"max_assembly_gap {recipe.max_assembly_gap}")
    for (a, b), (lo, hi) in recipe.pair_gaps.items():
        if a in grouped and b in grouped:
            ta = min(li.t for li in grouped[a] if li.t is not None)
            tb = max(li.t for li in grouped[b] if li.t is not None)
            gap = tb - ta
            if lo is not None and gap < lo:
                temporal_ok = False
                blocking.append(f"pair gap {a}->{b} below min {lo}")
            if hi is not None and gap > hi:
                temporal_ok = False
                blocking.append(f"pair gap {a}->{b} above max {hi}")

    # actor scoping across the present required fragments
    actor_ok = True
    if recipe.actor_scope == "SAME_ACTOR":
        actor_ok = bool(_actors(grouped, present_required)) if len(present_required) > 1 \
            else True
        if not actor_ok:
            blocking.append("required fragments do not share a common actor")
    elif recipe.actor_scope == "REQUIRE_MULTI_ACTOR":
        distinct = {li.inst.actor for f in present_required
                    for li in grouped.get(f, []) if li.inst.actor}
        actor_ok = len(distinct) >= 2
        if not actor_ok:
            blocking.append("recipe requires multiple distinct actors")

    # resource scoping
    resource_ok = True
    if recipe.resource_scope == "SAME_TARGET_FAMILY" and len(present_required) > 1:
        resource_ok = bool(_families(grouped, present_required))
        if not resource_ok:
            blocking.append("required fragments do not share a target family")

    corroboration_ok = recipe.required_corroboration <= present
    if not corroboration_ok:
        blocking.append("required corroborating fragments absent: "
                        + ", ".join(sorted(recipe.required_corroboration - present)))
    min_optional_ok = len(present_optional) >= recipe.min_optional_for_escalation
    if not min_optional_ok:
        blocking.append(f"needs >= {recipe.min_optional_for_escalation} optional "
                        f"corroborators, have {len(present_optional)}")

    constraints = {
        "ordering_ok": ordering_ok,
        "temporal_ok": temporal_ok,
        "actor_ok": actor_ok,
        "resource_ok": resource_ok,
        "corroboration_ok": corroboration_ok,
        "min_optional_ok": min_optional_ok,
        "mutually_exclusive_conflict": impossible and "mutually exclusive" in impossible_reason,
    }
    all_constraints_ok = (ordering_ok and temporal_ok and actor_ok and resource_ok
                          and corroboration_ok and min_optional_ok and not impossible)

    # signal: count is necessary; constraints gate escalation.
    base = signals.signal_for(
        completeness, observe_at=recipe.observe_threshold,
        escalate_at=recipe.escalation_threshold)
    if impossible:
        signal = signals.NONE
    elif base == signals.ESCALATE and not all_constraints_ok:
        # right nouns, wrong structure ⇒ watch, do not escalate
        signal = signals.OBSERVE if completeness >= recipe.observe_threshold else signals.NONE
    else:
        signal = base

    return MatchResult(
        recipe=recipe, signal=signal, completeness=completeness,
        present_required=present_required, missing_required=missing_required,
        present_optional=present_optional, constraints=constraints,
        impossible=impossible, impossible_reason=impossible_reason,
        gap_span=gap_span, contributing=contributing, blocking_reasons=blocking,
    )
