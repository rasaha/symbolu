"""Package-local canonicalization (_canon) verified against vectors.

Slice 2 must not rely on any underscore-prefixed helper of another
distribution (post-implementation audit, spec §11). The local implementation
is checked against (a) literal vectors computed independently with
ugence_jcs over hand-written JSON shapes, and (b) slice 1's own settled
digests, which are the canonicalization vectors the two packages must agree on.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

import pytest

import matrix_fixtures as fx
import rule_fixtures as rf
from ugence_jcs import canonical_sha256_hex
from ugence_reasoning_method_advisor import _canon
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode as C, ConsequenceClass

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "ugence_reasoning_method_advisor"

# Vector 1: strings, a list with an int-as-string, a bool-as-string and null, a nested
# object with an RFC 3339 UTC instant, and an enum by value.
VECTOR_1 = "38edf272763f7a15bd0b7167093ba3b72aaeb3ee5e21711d21d827584ef86675"
# Vector 2: non-ASCII strings and a null, keys deliberately out of order.
VECTOR_2 = "86e9f491e37d928426a22b232fad4200886fc7153639784b495be805b4c11f40"


@dataclasses.dataclass(frozen=True)
class _Inner:
    d: datetime


@dataclasses.dataclass(frozen=True)
class _Outer:
    a: str
    b: tuple
    c: _Inner
    e: ConsequenceClass
    self_digest: str = ""


def test_vector_1_literal():
    obj = _Outer("x", (1, True, None), _Inner(datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)), ConsequenceClass.RECOVERABLE)
    assert _canon.payload(obj, exclude=("self_digest",)) == {"a": "x", "b": ["1", "true", None], "c": {"d": "2026-09-02T12:00:00.000000Z"}, "e": "RECOVERABLE"}
    assert _canon.digest_of(obj, exclude=("self_digest",)) == VECTOR_1
    # A non-UTC representation of the same instant canonicalizes identically.
    shifted = _Outer("x", (1, True, None), _Inner(datetime(2026, 9, 2, 17, 0, tzinfo=timezone(timedelta(hours=5)))), ConsequenceClass.RECOVERABLE)
    assert _canon.digest_of(shifted, exclude=("self_digest",)) == VECTOR_1


def test_vector_2_literal_and_key_order_irrelevance():
    assert _canon.digest_of({"z": "é", "y": ("aé",), "x": None}) == VECTOR_2
    assert _canon.digest_of({"x": None, "y": ["aé"], "z": "é"}) == VECTOR_2
    assert canonical_sha256_hex({"y": ["aé"], "x": None, "z": "é"}) == VECTOR_2


def test_slice_1_digests_are_reproduced_by_the_local_canonicalizer():
    """Slice 1's settled digests are the shared vectors: task class, catalog and the request/advisory digests."""
    tc = rf.governed_class(("comparison_request",))
    assert _canon.digest_of(tc, exclude=("task_class_digest",)) == tc.task_class_digest
    cat = fx.c4_catalog()
    assert _canon.digest_of(cat, exclude=("catalog_digest",)) == cat.catalog_digest
    rs = rf.research_rules_v0()
    assert _canon.digest_of(rs, exclude=("rule_set_digest",)) == rs.rule_set_digest


def test_payload_refuses_floats_and_unknown_types():
    with pytest.raises(TypeError):
        _canon.payload(0.5)
    with pytest.raises(TypeError):
        _canon.payload(object())
    assert _canon.payload(Decimal("0.90")) == "0.90"


def test_settle_digest_fills_or_verifies():
    class E(str, Enum):
        A = "A"

    @dataclasses.dataclass(frozen=True)
    class D:
        v: E
        d: str = ""

        def __post_init__(self):
            _canon.settle_digest(self, "d", _canon.digest_of(self, exclude=("d",)))

    good = D(E.A)
    assert D(E.A, good.d).d == good.d
    with pytest.raises(ContractError) as ei:
        D(E.A, "0" * 64)
    assert ei.value.code is C.DIGEST_MALFORMED
    with pytest.raises(ContractError) as ei:
        D(E.A, "nothex")
    assert ei.value.code is C.DIGEST_MALFORMED


def test_require_helpers_codes():
    with pytest.raises(ContractError) as ei:
        _canon.require_tzaware(datetime(2026, 9, 2), "x")
    assert ei.value.code is C.DATETIME_NAIVE
    with pytest.raises(ContractError) as ei:
        _canon.require_nonblank(" ", "x")
    assert ei.value.code is C.REF_BLANK_FIELD
    with pytest.raises(ContractError) as ei:
        _canon.require_str_tuple(["a"], "x")
    assert ei.value.code is C.REF_BLANK_FIELD


def test_no_private_name_is_imported_from_any_other_distribution():
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module != "__future__":
                assert not any(seg.startswith("_") for seg in node.module.split(".")), f"{path.name} imports private module {node.module}"
                for alias in node.names:
                    assert not alias.name.startswith("_"), f"{path.name} imports private name {alias.name} from {node.module}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(seg.startswith("_") for seg in alias.name.split(".")), f"{path.name} imports {alias.name}"
