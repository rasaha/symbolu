"""Compatibility checks (section 24, checks 47-50)."""
from __future__ import annotations

import warnings

import pytest

from ugence_agent_runtime import api
from ugence_agent_runtime import compat


def test_supported_old_aliases_still_work():  # check 47
    for alias in ("Runtime", "Workflow", "Task", "Result", "Registry"):
        obj = compat.resolve(alias)
        assert obj is not None


def test_compat_aliases_reference_new_implementation():  # check 48
    assert compat.resolve("Runtime") is api.AgentRuntime
    assert compat.resolve("Workflow") is api.WorkflowDefinition
    assert compat.resolve("WorkflowRun") is api.WorkflowInstance
    assert compat.resolve("Task") is api.TaskDefinition
    assert compat.resolve("WorkflowCheckpoint") is api.Checkpoint
    assert compat.resolve("Registry") is api.ProviderRegistry
    assert compat.resolve("Result") is api.RuntimeResult


def test_no_duplicate_runtime_implementation():  # check 49
    # Every compatibility alias IS the canonical object (identity), so the compat
    # layer holds no second implementation of the runtime.
    from ugence_agent_runtime.compat import _DEPRECATED

    for alias, canonical in _DEPRECATED.items():
        assert compat.resolve(alias) is getattr(api, canonical)


def test_deprecation_warning_emitted():  # check 50
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = compat.Workflow  # triggers module __getattr__
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_compatibility_map_points_at_canonical_targets():
    for old, new in compat.COMPATIBILITY_MAP.items():
        assert new.startswith("ugence_agent_runtime.")
