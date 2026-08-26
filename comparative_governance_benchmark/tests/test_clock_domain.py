"""The benchmark replays scenarios in one time domain — the frozen scenario clock.

``runners.determinism.make_clock`` pins every run to 2026-01-01T00:00:00Z, so a
scenario's CER expires at 2026-01-01T01:00:00Z. A control-plane adapter left on
its default wall clock stamps the authorization it mints with ``now_wall``
instead, and ``ExecutionService`` then compares that stamp against the scenario
clock — an ``AuthorizationExpiredError`` whose occurrence depends on the date the
suite happens to run.

These two tests pin the decision recorded in
``Project_documentation/repository/docs/audits/actiongate_vnext/RATIFIED_DECISIONS.md``
(decision D1): for a replayed scenario the scenario clock is authoritative,
and no wall clock may be read.
"""
from __future__ import annotations

import ast
import dataclasses
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy

_ADAPTER = "ActionGovernanceControlPlaneAdapter"
_TREE = Path(__file__).resolve().parents[1]

# Deliberately on the far side of the frozen scenario clock: an adapter that
# reads this instead of the scenario clock mints an already-expired authorization.
_SKEW = datetime(2025, 6, 1, tzinfo=timezone.utc)

# kernel-opaque ids are permitted volatile fields; every substantive field is stable
_VOLATILE = {"authorization_id"}


@contextmanager
def _wall_clock_at(instant: datetime):
    """Make the adapter's *default* (wall) clock read ``instant``.

    ``ActionGovernanceControlPlaneAdapter`` binds its default clock as a
    parameter default, and that default resolves ``utc_now`` through the module's
    lazily built kernel cache — so replacing the cached entry is the one seam
    that reaches every adapter left on the default clock.
    """
    from ugence_governance_provider_framework.adapters import action_to_control_plane as a2cp

    a2cp._kernel()                                   # force the cache to exist
    original = a2cp._KERNEL["utc_now"]
    a2cp._KERNEL["utc_now"] = lambda *a, **k: instant
    try:
        yield
    finally:
        a2cp._KERNEL["utc_now"] = original


def _adapter_calls_missing_a_clock(tree: Path):
    """Every ``ActionGovernanceControlPlaneAdapter(...)`` site under ``tree``
    that does not inject a clock, as ``path:line``."""
    offenders = []
    for path in sorted(tree.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name != _ADAPTER:
                continue
            if not any(kw.arg == "clock" for kw in node.keywords):
                offenders.append(f"{path.relative_to(tree)}:{node.lineno}")
    return offenders


def _stable(result):
    d = {k: v for k, v in dataclasses.asdict(result).items() if k not in _VOLATILE}
    d["trace"] = {k: v for k, v in d["trace"].items() if k not in _VOLATILE}
    return d


def test_no_adapter_is_constructed_on_the_default_wall_clock():
    offenders = _adapter_calls_missing_a_clock(_TREE)
    assert not offenders, (
        "these sites build a control-plane adapter on the default wall clock while the "
        f"CER is issued on the frozen scenario clock: {offenders}")


def test_strategy_outcomes_do_not_move_when_the_wall_clock_moves():
    scenarios = list(load_frozen_dataset().ordered())
    # the authorizing strategies — the ones that reach the control-plane adapter
    strategies = {sid: build_strategy(sid) for sid in ("action_only", "full_governance")}
    baseline = {(sid, s.scenario_id): _stable(st.run(s))
                for sid, st in strategies.items() for s in scenarios}
    with _wall_clock_at(_SKEW):
        skewed = {(sid, s.scenario_id): _stable(st.run(s))
                  for sid, st in strategies.items() for s in scenarios}
    differing = [k for k in baseline if baseline[k] != skewed[k]]
    assert not differing, (
        "these (strategy, scenario) pairs replayed differently once the wall clock moved, "
        f"so the benchmark is still reading it somewhere: {differing}")
