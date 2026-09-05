"""No destructive retention path exists (round PR-B scope guard, DEC-PR-3).

The ratified amendment keeps destructive purging UNIMPLEMENTED until the
remaining gates pass. A behavioural test cannot prove the absence of a code
path, so this pins the source itself: the retention module must expose no
delete/purge operation, and no route may reach one.
"""

from __future__ import annotations

import inspect
import pathlib
import re

from ugence_dilchat.services import retention as retention_module


def test_retention_service_exposes_no_destructive_operation():
    public = {
        name
        for name, _ in inspect.getmembers(
            retention_module.RetentionPurgeService, inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert public == {"report_only"}, f"unexpected public operation(s): {public}"


def test_retention_source_issues_no_delete_and_no_state_mutation():
    source = pathlib.Path(inspect.getfile(retention_module)).read_text()
    # Strip the module docstring: it legitimately DESCRIBES deletion policy.
    body = source.split('"""', 2)[-1]
    forbidden = [
        r"\bsa\.delete\b",
        r"\bsession\.delete\b",
        r"\bDELETE\s+FROM\b",
        r"\bsa\.update\b",
        r"\bsession\.commit\b",
        r"\bTRUNCATE\b",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, body, re.IGNORECASE), f"destructive/mutating: {pattern}"


def test_purge_flag_default_stays_off_in_the_committed_configuration():
    config_source = pathlib.Path(
        inspect.getfile(retention_module)
    ).parent.parent.joinpath("config.py").read_text()
    assert "retention_purge_enabled: bool = False" in config_source


def test_no_api_route_imports_the_retention_service():
    """The report is worker-posture infrastructure, never a user-facing surface."""
    routes_dir = pathlib.Path(inspect.getfile(retention_module)).parent.parent / "api"
    hits = [
        path.name
        for path in routes_dir.rglob("*.py")
        if "services.retention" in path.read_text() or "RetentionPurgeService" in path.read_text()
    ]
    assert hits == [], f"retention service reachable from the API surface: {hits}"
