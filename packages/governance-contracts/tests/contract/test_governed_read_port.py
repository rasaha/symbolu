"""The governed-read port (Stage 1 item 3.5): a declared contract, implemented nowhere.

Two properties are load-bearing and both are structural: the answer is never a bare
boolean, and it carries the authorization digest it was computed under.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts.api import (
    GovernedReadPort,
    GovernedReadRequest,
    ProviderProtocolError,
    ReadEligibility,
    ReadEligibilityStatus,
    ReadIneligibilityReason,
    ReadPurpose,
)

MODULE = pathlib.Path(g.__file__).resolve().parent / "contracts" / "governed_read.py"


def _request(**kw) -> GovernedReadRequest:
    args = dict(tenant_id="t-1", consumer_id="m3", purpose=ReadPurpose.DECISION_INPUT,
                target_id="threshold.fraud", target_version="7")
    args.update(kw)
    return GovernedReadRequest(**args)


def _eligible(**kw) -> ReadEligibility:
    args = dict(status=ReadEligibilityStatus.ELIGIBLE, tenant_id="t-1", consumer_id="m3",
                purpose=ReadPurpose.DECISION_INPUT, target_id="threshold.fraud",
                target_version="7", authorization_digest="a" * 64)
    args.update(kw)
    return ReadEligibility(**args)


def test_a_determination_has_no_truth_value():
    """``if eligibility:`` would treat INDETERMINATE as permission and survive revocation."""

    with pytest.raises(ProviderProtocolError):
        bool(_eligible())
    with pytest.raises(ProviderProtocolError):
        if _eligible():  # pragma: no cover - the raise is the assertion
            pass


def test_an_eligible_determination_names_the_authorization_it_rests_on():
    assert _eligible().authorization_digest == "a" * 64
    with pytest.raises(ProviderProtocolError):
        _eligible(authorization_digest="")


def test_a_refusal_must_say_why_and_an_eligibility_must_not():
    assert _eligible(
        status=ReadEligibilityStatus.INELIGIBLE,
        reason=ReadIneligibilityReason.AUTHORIZATION_REVOKED).reason is not None
    with pytest.raises(ProviderProtocolError):
        _eligible(status=ReadEligibilityStatus.INELIGIBLE)
    with pytest.raises(ProviderProtocolError):
        _eligible(reason=ReadIneligibilityReason.NOT_APPLIED)


def test_indeterminate_is_available_and_is_not_permission():
    determination = _eligible(
        status=ReadEligibilityStatus.INDETERMINATE,
        reason=ReadIneligibilityReason.DETERMINATION_UNAVAILABLE)
    assert determination.status is not ReadEligibilityStatus.ELIGIBLE
    with pytest.raises(ProviderProtocolError):
        bool(determination)


def test_a_determination_answers_one_question_and_is_not_transferable():
    determination = _eligible()
    assert determination.answers(_request())
    assert not determination.answers(_request(purpose=ReadPurpose.AUDIT))
    assert not determination.answers(_request(target_version="8"))
    assert not determination.answers(_request(consumer_id="m11"))
    assert not determination.answers(_request(tenant_id="t-2"))


def test_the_request_refuses_blank_coordinates_and_an_untyped_purpose():
    for field in ("tenant_id", "consumer_id", "target_id", "target_version"):
        with pytest.raises(ProviderProtocolError):
            _request(**{field: "  "})
    with pytest.raises(ProviderProtocolError):
        _request(purpose="DECISION_INPUT")


def test_the_port_is_a_protocol_with_one_method_and_no_implementation():
    assert getattr(GovernedReadPort, "_is_protocol", False)
    assert [n for n in dir(GovernedReadPort) if not n.startswith("_")] == ["determine"]


def test_the_protocol_method_has_no_body():
    """A port that could answer would be an implementation; there is none.

    Checked on the AST rather than on words in the prose: the docstring says the module
    caches nothing, and a substring ban would have been satisfied by deleting the
    sentence that says so.
    """

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    port = [n for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and n.name == "GovernedReadPort"]
    assert len(port) == 1
    methods = [n for n in port[0].body if isinstance(n, ast.FunctionDef)]
    assert [m.name for m in methods] == ["determine"]
    for stmt in methods[0].body:
        assert isinstance(stmt, ast.Expr), "a Protocol method's body is `...` and nothing else"
        assert isinstance(stmt.value, (ast.Constant, ast.Ellipsis))


def test_the_module_holds_no_state_and_memoizes_nothing():
    """No module-level mutable state, no attribute assignment, no caching decorator."""

    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            assert not isinstance(value, (ast.Dict, ast.List, ast.Set, ast.DictComp,
                                          ast.ListComp, ast.SetComp)), ast.dump(node)[:80]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for deco in node.decorator_list:
                name = getattr(deco, "attr", None) or getattr(deco, "id", None)
                assert name not in ("cache", "lru_cache", "cached_property"), node.name
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            raise AssertionError(f"the module assigns an attribute: {node.attr}")


def test_the_module_imports_no_store_clock_or_network():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    for forbidden in ("sqlite3", "redis", "requests", "httpx", "time", "datetime",
                      "functools", "threading"):
        assert forbidden not in imported, forbidden


def test_the_port_does_not_depend_on_the_classifier():
    """A read port that depended on the producer would make every reader its dependent."""

    source = MODULE.read_text(encoding="utf-8")
    assert "change_effect" not in source.replace(
        "ugence_change_effect_records``", "")  # the docstring may name it as an exclusion
    tree = ast.parse(source, filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "change_effect" not in node.module
        if isinstance(node, ast.Import):
            assert not any("change_effect" in a.name for a in node.names)
