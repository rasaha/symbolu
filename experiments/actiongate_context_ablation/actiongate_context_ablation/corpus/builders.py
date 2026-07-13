"""Compact builders for naturalistic corpus items + a filler-span library.

Realistic contexts carry a lot of NON-critical material (justification prose,
history, logs, restated context). Including it is the point: it is what makes the
naturalistic critical fraction realistically low, unlike the dense synthetic
fixtures. Filler libraries below are parameterized so contexts vary.
"""

from __future__ import annotations

from ..units import SemanticUnit as U
from .schema import CorpusItem, Provenance
from ..labels import (  # re-exported for core.py and corpus modules
    ANNOTATION_LABELS, ASSURANCE_CRITICAL, DECISION_CRITICAL, ENVELOPE_CRITICAL,
    NON_CRITICAL, REDUNDANT, STRUCTURE_CRITICAL, UNCERTAIN,
)


def span(uid, stype, text, *, contrib=None, expected=NON_CRITICAL,
         redundancy_set=None, references=(), dependency_links=()):
    return U(id=uid, source_type=stype, text=text, contrib=contrib or {},
             expected=expected, redundancy_set=redundancy_set,
             references=tuple(references), dependency_links=tuple(dependency_links))


# ---------- filler libraries (non-critical realistic content) ----------
_JUSTIFY = [
    "This change was requested by the platform team during the weekly planning review.",
    "The work item is tracked under the current sprint and was groomed last Tuesday.",
    "Product asked for this ahead of the upcoming customer launch.",
    "This is part of the ongoing reliability initiative for the quarter.",
    "The on-call engineer flagged this during the last operational review.",
]
_HISTORY = [
    "A similar change was applied to the staging environment two weeks ago without issues.",
    "The previous rollout of this service completed in eleven minutes.",
    "Last quarter the team migrated the adjacent service with no incidents.",
    "Historical logs show this component restarts cleanly under load.",
    "An earlier version of this request was withdrawn pending review.",
]
_LOGS = [
    "log: 2026-07-12T13:40:02Z scheduler assigned pod to node-7",
    "log: 2026-07-12T13:41:10Z healthcheck OK latency_p50=42ms",
    "log: 2026-07-12T13:42:55Z config reloaded generation=8",
    "log: 2026-07-12T13:44:01Z connection pool warmed size=32",
]
_STALE = [
    "Note (possibly stale): an older runbook mentioned a manual step that is no longer required.",
    "Outdated comment from last year suggests a different owner; ignore.",
]


def _pick(lst, i):
    return lst[i % len(lst)]


def filler(prefix, kinds):
    """Build a list of non-critical filler spans from named kinds."""
    out = []
    counters = {"justify": 0, "history": 0, "logs": 0, "stale": 0}
    src = {"justify": _JUSTIFY, "history": _HISTORY, "logs": _LOGS, "stale": _STALE}
    stype = {"justify": "sentence", "history": "sentence", "logs": "log_event",
             "stale": "sentence"}
    for n, k in enumerate(kinds):
        i = counters[k]
        counters[k] += 1
        out.append(span(f"{prefix}_{k}{i}", stype[k], _pick(src[k], i),
                        expected=NON_CRITICAL))
    return out


def item(*, item_id, partition, split, domain, action_type, structure_family,
         base, units, provenance, template_family, linked_pairs=()):
    from ..units import Context
    ctx = Context(id=item_id, base=base, units=tuple(units),
                  data_origin=partition, description=provenance.expected_envelope,
                  linked_pairs=tuple(linked_pairs))
    return CorpusItem(
        item_id=item_id, partition=partition, split=split, domain=domain,
        action_type=action_type, structure_family=structure_family, context=ctx,
        provenance=provenance, template_family=template_family)


def prov(source, title, license, adaptations, action_type, tool_domain,
         expected_envelope, *, adapted=True, retrieved=""):
    return Provenance(source=source, title=title, license=license, adapted=adapted,
                      adaptations=adaptations, action_type=action_type,
                      tool_domain=tool_domain, expected_envelope=expected_envelope,
                      retrieved=retrieved)
