"""Phase-3 cost-evidence tests (matrix D: cost behavior + construction rejections)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.planning import (
    CostBasis,
    CostBook,
    CostError,
    CostEvidence,
    Money,
)
import ph_helpers as H


def _s(wid, tenant="tenant-1"):
    return CapacitySubject(workload_id=wid, tenant_id=tenant)


def test_money_negative_rejected_in_cost_evidence():
    with pytest.raises(CostError):
        CostEvidence(_s("app"), Money(-1, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(10))


def test_money_non_integer_rejected():
    with pytest.raises(CostError):
        Money(1.5, "USD")  # type: ignore[arg-type]


def test_money_bad_currency_rejected():
    with pytest.raises(CostError):
        Money(100, "US")
    with pytest.raises(CostError):
        Money(100, "US1")


def test_money_currency_normalized_upper():
    assert Money(100, "usd").currency == "USD"


def test_cost_evidence_bad_interval_rejected():
    with pytest.raises(CostError):
        CostEvidence(_s("app"), Money(100, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(10), H.at(0))


def test_cost_evidence_effective_at():
    c = CostEvidence(_s("app"), Money(100, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(100))
    assert c.is_effective_at(H.at(50)) is True
    assert c.is_effective_at(H.at(200)) is False


def test_cost_book_cross_tenant_rejected():
    app = _s("app", "tenant-1")
    db = _s("db", "tenant-2")
    with pytest.raises(CostError):
        CostBook(subject=app, entries=(
            CostEvidence(db, Money(5, "USD"), CostBasis.PER_CONNECTION_HOUR, H.at(0), H.at(10)),))


def test_cost_book_duplicate_subject_rejected():
    app = _s("app")
    e = CostEvidence(app, Money(5, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(10))
    with pytest.raises(CostError):
        CostBook(subject=app, entries=(e, e))


def test_cost_book_round_trip():
    app, db = _s("app"), _s("db")
    book = CostBook(subject=app, entries=(
        CostEvidence(app, Money(1000, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(100)),
        CostEvidence(db, Money(50, "USD"), CostBasis.PER_CONNECTION_HOUR, H.at(0), H.at(100)),
    ))
    book2 = CostBook.from_dict(book.to_canonical_dict())
    assert book2.digest() == book.digest()


def test_cost_evidence_forged_digest_detected_via_content():
    """A cost evidence's digest is a pure function of its content — a mismatched money value
    produces a different digest, so a 'forged' digest cannot be paired with other content."""
    a = CostEvidence(_s("app"), Money(1000, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(100))
    b = CostEvidence(_s("app"), Money(2000, "USD"), CostBasis.PER_REPLICA_HOUR, H.at(0), H.at(100))
    assert a.digest() != b.digest()


def test_cost_book_from_dict_rejects_unknown_field():
    app = _s("app")
    book = CostBook(subject=app, entries=())
    d = book.to_canonical_dict()
    d["surprise"] = True
    with pytest.raises(CostError):
        CostBook.from_dict(d)
