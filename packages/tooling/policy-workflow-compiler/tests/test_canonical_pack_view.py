"""One canonical pack view, two callers (policy_pack.v2 step one).

The approval digest and the compiled release's pack payload must mean exactly the
same thing by "the pack's logical content". They were two independent
implementations that happened to agree; a divergence would silently invalidate every
approval bound to every existing pack. These tests hold them to one definition, and
pin every digest the extraction must not move.
"""

from __future__ import annotations

import pathlib
import re

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import compute_pack_digest
from ugence_policy_workflow_compiler.compiler.release import _pack_logical
from ugence_policy_workflow_compiler.models.pack_view import canonical_pack_view
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.serialization import hashing

PINNED_PACK_DIGEST = "sha256:28eedf60892bc1b3e9f8c15c56d43b0aa353659c8158a793f94168a81de98b14"
PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


def _pack():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def test_both_callers_produce_an_identical_view():
    pack, _ = _pack()
    assert _pack_logical(pack) == canonical_pack_view(pack)
    assert compute_pack_digest(pack) == hashing.digest(canonical_pack_view(pack))


def test_the_view_is_status_independent():
    # A pack keeps one identity across the APPROVED -> COMPILED transition.
    from ugence_policy_workflow_compiler.models.common import PolicyPackStatus

    pack, _ = _pack()
    compiled = pack.model_copy(update={"status": PolicyPackStatus.COMPILED})
    assert canonical_pack_view(pack) == canonical_pack_view(compiled)
    assert compute_pack_digest(pack) == compute_pack_digest(compiled)
    assert "status" not in canonical_pack_view(pack)


def test_the_view_is_a_fresh_mapping_per_call():
    # Callers add their own framing keys; one caller must not affect another.
    pack, _ = _pack()
    first = canonical_pack_view(pack)
    first["injected_by_a_caller"] = True
    assert "injected_by_a_caller" not in canonical_pack_view(pack)
    assert compute_pack_digest(pack) == PINNED_PACK_DIGEST


def test_nothing_else_reconstructs_the_view():
    # The whole point of the extraction: exactly one place drops `status`.
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "ugence_policy_workflow_compiler"
    pattern = re.compile(r'pop\(\s*["\']status["\']')
    offenders = [
        str(module.relative_to(root))
        for module in root.rglob("*.py")
        if pattern.search(module.read_text()) and module.name != "pack_view.py"
    ]
    assert offenders == [], offenders


def test_extraction_moves_no_digest():
    pack, approval = _pack()
    assert compute_pack_digest(pack) == PINNED_PACK_DIGEST
    result = api.compile_policy_pack(pack, approval)
    assert result.success
    assert result.logical_digest == PINNED_V1_RELEASE_DIGEST
    assert result.workflow_ir.logical_digest() == PINNED_V1_IR_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_the_existing_approval_still_binds():
    # The regression this extraction exists to prevent, stated directly.
    pack, approval = _pack()
    assert approval.policy_pack_digest == compute_pack_digest(pack)
    assert api.compile_policy_pack(pack, approval).success
