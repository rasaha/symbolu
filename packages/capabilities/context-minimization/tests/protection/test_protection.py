"""Protected-span contract tests — required scenarios 29–33."""

from __future__ import annotations

from ugence_context_minimization import reasons
from ugence_context_minimization.api import (
    EquivalenceStatus,
    ProtectionResult,
    minimize_context,
    structural_minimize,
)

from support import (
    KeywordOracle,
    KeywordProtection,
    MalformedProtection,
    RaisingProtection,
    context,
    unit,
)


def test_protected_unit_never_selected_for_extractive_removal():
    # A protected filler span that the ranking would otherwise remove first.
    ctx = context([
        unit("p", "weekly sprint filler", source_type="log_event", protected=True),
        unit("q", "another filler", source_type="log_event"),
        unit("anchor", "deploy anchor", source_type="state_fact"),
    ])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                         protected_ids=["p"], evaluation_time=1.0)
    assert "p" in r.surviving_ids
    assert "p" not in r.removed_ids


def test_uncertain_protection_retains_unit():
    ctx = context([
        unit("u", "removable filler", source_type="log_event"),
        unit("anchor", "deploy anchor", source_type="state_fact"),
    ])
    prot = KeywordProtection(keywords=("nothing",), uncertain_ids=["u"])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                         protection=prot, evaluation_time=1.0)
    assert "u" in r.surviving_ids  # uncertain => retained (fail closed)


def test_optional_ranking_cannot_override_protection():
    # Even the single lowest-priority, filler-hinted, largest span cannot be removed
    # if protected. Structural mode too.
    ctx = context([
        unit("p", "historical on-call maintenance window log: verbose filler text here",
             source_type="log_event", protected=True),
        unit("p2", "historical on-call maintenance window log: verbose filler text here",
             source_type="log_event"),
    ])
    rs = structural_minimize(ctx, protected_ids=["p"])
    assert "p" in rs.surviving_ids
    ro = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                          protected_ids=["p"], evaluation_time=1.0)
    assert "p" in ro.surviving_ids


def test_protection_provider_failure_fails_closed():
    ctx = context([unit("a", "deploy"), unit("b", "filler")])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                         protection=RaisingProtection(), evaluation_time=1.0)
    # provider raised => protect everything => nothing removed, reported honestly
    assert r.surviving_ids == r.original_ids
    assert reasons.PROTECTION_PROVIDER_FAILED in r.reason_codes
    assert not r.fell_back  # equivalence trivially holds; we simply removed nothing


def test_malformed_protection_result_fails_closed():
    ctx = context([unit("a", "deploy"), unit("b", "filler")])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                         protection=MalformedProtection(), evaluation_time=1.0)
    assert r.surviving_ids == r.original_ids
    assert reasons.PROTECTION_PROVIDER_FAILED in r.reason_codes


def test_duplicate_protected_units_both_retained_v1_contract():
    # v1 contract: every protected unit id remains — even two protected duplicates.
    ctx = context([
        unit("p1", "identical fact", redundancy_set="r1", protected=True),
        unit("p2", "identical fact", redundancy_set="r1", protected=True),
        unit("u", "identical fact", redundancy_set="r1"),  # unprotected dup may go
    ])
    r = structural_minimize(ctx, protected_ids=["p1", "p2"])
    assert "p1" in r.surviving_ids and "p2" in r.surviving_ids
    assert "u" in r.removed_ids


def test_protection_result_supplied_directly():
    ctx = context([unit("a", "deploy"), unit("b", "filler")])
    pr = ProtectionResult(protected_ids=frozenset({"b"}))
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0,
                         protection=pr, evaluation_time=1.0)
    assert "b" in r.surviving_ids
