"""NON-NORMATIVE diagnostics — observations, never the v1 compatibility contract.

These values (``float``, ``-0.0``, ``set``, ``frozenset``, ``bool``, ``None``) are
accepted by both canonicalizers but are **not** structurally reachable through
``workflow_ir.v1``. Per the ADR §9 classification ruling they are therefore not v1
capabilities and create no cross-component obligation.

**They are deliberately not golden-anchored and are not part of the v1 gate.** The
ratchet job runs this file as a non-blocking step: an incidental out-of-domain
behaviour change must surface as information, never as a v1 contract break. Test
coverage is not contract scope.

What is still worth knowing: whether the two implementations currently agree here.
A divergence is a fact to record, not a regression to fail on.
"""
from __future__ import annotations

import pytest

from . import _ir_v1_compat_vectors as V

pytest.importorskip("ugence_policy_workflow_compiler")

from ugence_agent_workforce_composer import canonical as _awc                    # noqa: E402
from ugence_policy_workflow_compiler.serialization import canonical_json as _cj  # noqa: E402


@pytest.mark.parametrize("vector_id,value", V.diagnostic_vectors())
def test_out_of_domain_values_currently_agree(vector_id, value):
    """Informational. Failure here means the two implementations diverged on a value
    v1 cannot express -- worth a look, but not a v1 compatibility break."""
    assert _cj.dumps(value) == _awc.canonical_json(value), (
        f"{vector_id}: out-of-domain divergence (NOT a v1 contract break)")


def test_diagnostics_are_absent_from_the_normative_golden():
    """The structural reason these cannot fail the v1 gate."""
    import json
    import pathlib

    golden = json.loads(
        (pathlib.Path(__file__).resolve().parent / "fixtures" /
         "workflow_ir_v1_canonical_golden.json").read_text(encoding="utf-8"))
    for vector_id, _ in V.diagnostic_vectors():
        assert vector_id not in golden["vectors"], (
            f"{vector_id} is diagnostic but anchored in the normative golden")
