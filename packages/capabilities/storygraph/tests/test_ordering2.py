"""§10 — expanded ordering/clock-status validation."""

from __future__ import annotations

from ugence_storygraph import ordering


def _sig(cid, ing, **kw):
    return ordering.OrderSignals(correlation_id=cid, ingestion_time=ing, **kw)


def test_ordered_by_source_sequence_same_correlation():
    a = _sig("c", 1, source_sequence=1)
    b = _sig("c", 2, source_sequence=2)
    assert ordering.resolve_pair(a, b) == ordering.A_BEFORE_B
    assert ordering.assembly_status([a, b]) == ordering.ORDERED


def test_conflicting_source_vs_event_time():
    a = _sig("c", 1, source_sequence=1, event_time=300.0)
    b = _sig("c", 2, source_sequence=2, event_time=100.0)  # time disagrees with seq
    assert ordering.resolve_pair(a, b) == ordering.CONFLICTING
    assert ordering.assembly_status([a, b]) == ordering.CONFLICTING_ORDER


def test_ambiguous_when_no_discriminator():
    a = _sig("x", 1)   # different correlations, no time/seq
    b = _sig("y", 2)
    assert ordering.resolve_pair(a, b) == ordering.AMBIGUOUS
    assert ordering.assembly_status([a, b]) == ordering.AMBIGUOUS_ORDER


def test_cross_correlation_resolved_by_event_time():
    a = _sig("x", 1, event_time=100.0)
    b = _sig("y", 2, event_time=200.0)
    assert ordering.resolve_pair(a, b) == ordering.A_BEFORE_B


def test_receipt_sequence_resolves_when_time_missing():
    a = _sig("x", 1, receipt_sequence=5)
    b = _sig("y", 2, receipt_sequence=9)
    assert ordering.resolve_pair(a, b) == ordering.A_BEFORE_B


def test_partially_ordered_mix():
    a = _sig("c", 1, source_sequence=1)     # a<b resolvable
    b = _sig("c", 2, source_sequence=2)
    c = _sig("z", 3)                        # unrelated, ambiguous vs a,b
    st = ordering.assembly_status([a, b, c])
    assert st == ordering.PARTIALLY_ORDERED


def test_strict_ordering_not_satisfied_under_ambiguity_by_default():
    assert ordering.satisfies_strict_ordering(ordering.AMBIGUOUS_ORDER, False) is False
    assert ordering.satisfies_strict_ordering(ordering.CONFLICTING_ORDER, False) is False
    # only when the recipe explicitly permits
    assert ordering.satisfies_strict_ordering(ordering.AMBIGUOUS_ORDER, True) is True
    # partially-ordered is acceptable
    assert ordering.satisfies_strict_ordering(ordering.PARTIALLY_ORDERED, False) is True
