"""Honest coexistence checks (P0-3).

The legacy runtime and the kernel are DIFFERENT implementations. These tests prove
that honestly, rather than asserting invented same-package aliases.

Tests that import the actual legacy path are skipped when ``agent_runtime_migration``
is not importable (e.g. when this suite runs from the installed wheel outside the
monorepo). In the monorepo (and in the scoped CI job) they run and assert coexistence.
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime import api, compat


def test_migration_map_targets_are_honest():  # check 12
    # Every mapped "new" target (when present) points into the kernel package; entries
    # with no kernel equivalent are classified as excluded / legacy-integration-only.
    for legacy, entry in compat.MIGRATION_MAP.items():
        new = entry["new"]
        if new is None:
            assert entry["classification"] in (
                "INTENTIONALLY_EXCLUDED",
                "LEGACY_INTEGRATION_ONLY",
                "PRESENT_CHANGED",
            )
        else:
            assert str(new).startswith("ugence_agent_runtime.")


def test_classification_accessible():
    assert compat.classify("agent_runtime_migration.runtime.runtime.AgentRuntime") == "PRESENT_CHANGED"
    assert compat.classify("agent_runtime_migration.planning") == "INTENTIONALLY_EXCLUDED"
    assert compat.new_target("agent_runtime_migration.planning") is None


def test_no_invented_legacy_identity_aliases():  # check 11 (negative)
    # The compat module must NOT re-export a `Runtime`/`Workflow` alias that pretends
    # the kernel object is the legacy object.
    for banned in ("Runtime", "Workflow", "WorkflowRun", "Task", "resolve"):
        assert not hasattr(compat, banned), f"compat should not expose {banned!r}"


def test_legacy_and_kernel_runtimes_are_distinct_implementations():  # check 11, 12
    # Import the ACTUAL legacy path. Skip cleanly when the legacy package (or its heavy
    # transitive deps) is absent — e.g. the isolated-wheel run, or a minimal CI image.
    legacy_mod = pytest.importorskip("agent_runtime_migration.runtime.runtime")
    LegacyRuntime = legacy_mod.AgentRuntime

    kernel_runtime = api.AgentRuntime
    # They are genuinely different classes/implementations — not the same object.
    assert LegacyRuntime is not kernel_runtime
    assert LegacyRuntime.__module__ != kernel_runtime.__module__
    # And their constructor contracts differ (legacy requires an executor keyword).
    import inspect

    legacy_params = set(inspect.signature(LegacyRuntime.__init__).parameters)
    kernel_params = set(inspect.signature(kernel_runtime.__init__).parameters)
    assert "executor" in legacy_params
    assert "executor" not in kernel_params
    assert "config" in kernel_params


def test_legacy_runtime_still_importable_and_untouched():
    # The legacy package remains present (not deleted). Skip when unavailable.
    legacy_mod = pytest.importorskip("agent_runtime_migration.runtime.runtime")
    assert hasattr(legacy_mod, "AgentRuntime")
