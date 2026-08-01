"""Bridge: run story graphs against a live analyzer assembly.

Reuses the existing linkage/ledger (for the observed events) and the
purpose/providers layer (for the verified benign counter-story), so the story
graph is evaluated on the *same* deterministic, entity-linked, deduped state the
rest of the analyzer produces — not a separate pipeline.
"""

from __future__ import annotations

import types

from . import purpose as purpose_mod
from .storygraph import ObservedEvent, from_ledger
from .storyverdict import BenignSummary, evaluate


def _now(asm) -> float:
    return float(asm.last_t if asm.last_t is not None else asm.last_position)


def observed_events(analyzer, tenant_id: str, assembly_key: str) -> list[ObservedEvent]:
    """The currently-active observed events for an assembly, as story views."""
    asm = analyzer.ledger.get(tenant_id, assembly_key)
    if asm is None:
        return []
    active = asm.active(_now(asm), analyzer.timescale)
    return from_ledger(active)


def benign_summary(analyzer, tenant_id: str, assembly_key: str, *,
                   benign_tags=()) -> BenignSummary:
    """Compute a verified-benign summary for an assembly via the purpose layer.

    ``benign_tags`` are the authorization tags this story accepts as a legitimate
    explanation (e.g. ``customer_account_recovery``). Self-declared purpose never
    neutralizes — only a trusted, verified, scope-matched authorization does.
    """
    asm = analyzer.ledger.get(tenant_id, assembly_key)
    if asm is None:
        return BenignSummary()
    now = _now(asm)
    active = asm.active(now, analyzer.timescale)
    scope = analyzer._assembly_scope(asm, active)
    claims = analyzer._claims.get((tenant_id, assembly_key), [])
    shim = types.SimpleNamespace(benign_exclusions=frozenset(benign_tags))
    a = purpose_mod.assess(claims, scope, analyzer.providers, now,
                           analyzer.active_policy_version, shim,
                           activity_start=asm.first_t)
    return BenignSummary(status=a.purpose_consistency_status,
                         scope_mismatch_fields=a.scope_mismatch_fields,
                         provider_unavailable=a.provider_unavailable)


def proposed_event(fragment_id: str, *, entities: dict, actor: str = "",
                   position: int | None = None, epoch: float | None = None,
                   event_id: str = "proposed") -> ObservedEvent:
    """Build a hypothetical pre-commit action for forward completion-gating."""
    return ObservedEvent(
        fragment_id=fragment_id, event_id=event_id,
        position=position if position is not None else 10_000_000,
        epoch=epoch, actor=actor, entities=dict(entities))


def evaluate_story(analyzer, tenant_id: str, assembly_key: str, graph, *,
                   benign_tags=(), facts=None, proposed=None):
    """One-call story evaluation for a live assembly (advisory verdict)."""
    events = observed_events(analyzer, tenant_id, assembly_key)
    benign = benign_summary(analyzer, tenant_id, assembly_key, benign_tags=benign_tags)
    return evaluate(graph, events, benign=benign, facts=facts, proposed=proposed)
