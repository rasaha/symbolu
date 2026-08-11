"""Pytest fixtures for the RA-5 trusted-evidence-runtime suite.

The reusable scenario helpers live in the uniquely-named ``ra5_scenario`` module
(imported by the test files as ``import ra5_scenario as C``) so that running this
package's tests alongside other packages' test roots in a single pytest process
never collides on a shared ``conftest`` module name. The imports below are lazy
(inside the fixtures) so this conftest loads before pytest has inserted this
directory onto ``sys.path`` in a multi-root run.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def runtime():
    import ra5_scenario as C

    return C.build_runtime()


@pytest.fixture
def UNSUPPORTED_RULE():
    from ugence_tap_provider.api import TapOutcome, TapRule

    return TapRule(outcome=TapOutcome.UNSUPPORTED, evidence_coverage=1.0)
