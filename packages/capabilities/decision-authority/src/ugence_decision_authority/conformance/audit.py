"""Audit dimension — governance events are kernel-namespaced and classifiable.

A domain platform may also emit its *own* domain-namespace events upstream (its
evidence/assessment stages). The universal, domain-agnostic invariants are:

* the governance-chain milestone events are present and classified ``KERNEL``;
* every emitted event classifies cleanly into the frozen partition
  (``KERNEL`` / ``LEGACY`` / ``DOMAIN``) — nothing unknown;
* the partition is total and disjoint over the catalog.
"""

from __future__ import annotations

from ..audit import (
    DOMAIN_EVENTS,
    KERNEL_EVENTS,
    LEGACY_EVENTS,
    AuditEventType,
    AuditNamespace,
    audit_namespace,
)
from .results import fail, ok

_GOVERNANCE_MILESTONES = (
    AuditEventType.DECISION_CASE_CREATED,
    AuditEventType.DECISION_RECORDED,
    AuditEventType.ACTION_REQUEST_CREATED,
    AuditEventType.EXECUTION_INTENT_CREATED,
    AuditEventType.EXECUTION_RECONCILED,
)


def check(fixture, platform, outcome):
    results = []
    emitted = {e.event_type for e in outcome.audit_events}

    results.append(
        ok("audit", "events_emitted") if emitted
        else fail("audit", "events_emitted", "no audit events"))

    # Governance milestones are present and KERNEL-classified.
    for milestone in _GOVERNANCE_MILESTONES:
        present_and_kernel = (
            milestone in emitted and audit_namespace(milestone) is AuditNamespace.KERNEL)
        results.append(
            ok("audit", f"governance_kernel:{milestone.value}") if present_and_kernel
            else fail("audit", f"governance_kernel:{milestone.value}",
                      "governance milestone missing or not KERNEL-classified"))

    # Every emitted event classifies cleanly (nothing unknown / off-catalog).
    catalog = frozenset(AuditEventType)
    unclassified = {e for e in emitted if e not in catalog}
    results.append(
        ok("audit", "all_events_classified") if not unclassified
        else fail("audit", "all_events_classified", f"events not in catalog: {unclassified}"))

    # Partition is total and disjoint.
    total_disjoint = (
        (KERNEL_EVENTS | LEGACY_EVENTS | DOMAIN_EVENTS) == catalog
        and not (KERNEL_EVENTS & LEGACY_EVENTS)
        and not (KERNEL_EVENTS & DOMAIN_EVENTS)
        and not (LEGACY_EVENTS & DOMAIN_EVENTS))
    results.append(
        ok("audit", "partition_total_disjoint") if total_disjoint
        else fail("audit", "partition_total_disjoint", "audit namespace partition broken"))

    return results
