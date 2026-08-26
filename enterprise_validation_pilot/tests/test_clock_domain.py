"""The pilot replays scenarios in one time domain — the frozen scenario clock.

A replayed scenario issues its CER on ``composition.determinism.make_clock``
(2026-01-01T00:00:00Z, so ``expires_at`` is 2026-01-01T01:00:00Z). If the
control-plane adapter is left on its default wall clock, CER expiry and
authorization validity are computed against two different instants: the
authorization it mints is stamped ``now_wall``, and ``ExecutionService`` then
compares that stamp against the scenario clock. Whenever the two disagree in the
wrong direction the whole pilot collapses with ``AuthorizationExpiredError``,
and whether it does depends on the date the suite happens to run.

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

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.runners.workflow import run_scenario

_ADAPTER = "ActionGovernanceControlPlaneAdapter"
_TREE = Path(__file__).resolve().parents[1]

# Deliberately on the far side of the frozen scenario clock: an adapter that
# reads this instead of the scenario clock mints an already-expired authorization.
_SKEW = datetime(2025, 6, 1, tzinfo=timezone.utc)


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


def test_no_adapter_is_constructed_on_the_default_wall_clock():
    offenders = _adapter_calls_missing_a_clock(_TREE)
    assert not offenders, (
        "these sites build a control-plane adapter on the default wall clock while the "
        f"CER is issued on the frozen scenario clock: {offenders}")


def _stable(run):
    """A run's substantive fields — minus the kernel-opaque, permitted-volatile
    ``authorization_id`` (same exclusion the reproducibility test makes)."""
    volatile = {"authorization_id"}
    d = {k: v for k, v in dataclasses.asdict(run).items() if k not in volatile}
    d["trace"] = {k: v for k, v in d["trace"].items() if k not in volatile}
    return d


def test_replay_outcomes_do_not_move_when_the_wall_clock_moves():
    scenarios = list(build().ordered())
    baseline = [_stable(run_scenario(s)) for s in scenarios]
    with _wall_clock_at(_SKEW):
        skewed = [_stable(run_scenario(s)) for s in scenarios]
    differing = [s.scenario_id for s, b, k in zip(scenarios, baseline, skewed) if b != k]
    assert not differing, (
        "these scenarios replayed differently once the wall clock moved, so the pilot is "
        f"still reading it somewhere: {differing}")
