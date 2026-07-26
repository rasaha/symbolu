"""Dataset identity + strategy isolation (Tasks 4, 5, 15/B2, B5-B7)."""
from __future__ import annotations

import ast
import dataclasses
import pathlib

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset, verify_identity
from comparative_governance_benchmark.strategies import STRATEGY_ORDER, build_strategy

PKG = pathlib.Path(__file__).resolve().parents[1]


def _imports(path):
    mods = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module)
    return mods


def test_frozen_dataset_identity():
    ident = verify_identity(load_frozen_dataset())
    assert ident.ok
    assert ident.version == "enterprise_pilot_v1"
    assert ident.content_hash.startswith("4d6de429")
    assert ident.scenario_count == 90 and ident.domain_count == 3


def test_no_governance_imports_no_provider():
    mods = _imports(PKG / "strategies" / "no_governance.py")
    assert not any(m.split(".")[0] in ("tap_provider", "actiongate_provider") for m in mods)


def test_action_only_never_imports_tap():
    mods = _imports(PKG / "strategies" / "action_only.py")
    assert not any(m.split(".")[0] == "tap_provider" for m in mods)


def test_assertion_only_never_imports_actiongate():
    mods = _imports(PKG / "strategies" / "assertion_only.py")
    assert not any(m.split(".")[0] == "actiongate_provider" for m in mods)


def test_no_strategy_module_reads_expected_labels():
    for p in (PKG / "strategies").glob("*.py"):
        assert ".expected" not in p.read_text(), p.name


def test_mutating_expected_does_not_change_strategy_output():
    from comparative_governance_benchmark.benchmark import _substantive
    from enterprise_validation_pilot.schemas.scenario import ExpectedOutcome as EO
    ds = load_frozen_dataset()
    for sid in STRATEGY_ORDER:
        strat = build_strategy(sid)
        for scid in ("procurement-001", "procurement-013", "procurement-017"):
            s = ds.by_id(scid)
            m = dataclasses.replace(s, expected=EO(tap_outcome="WRONG",
                                                   actiongate_outcome="WRONG",
                                                   dispatched=not s.expected.dispatched))
            assert _substantive(strat.run(s)) == _substantive(strat.run(m))
