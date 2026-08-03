"""Compatibility-facade tests — ``ai_hiring`` maps to the canonical package.

These verify the wheel-shipped ``ai_hiring`` legacy namespace re-exports the SAME
objects as ``ugence_ai_hiring`` (object identity preserved), including deep
submodule paths, so existing ``import ai_hiring...`` consumers keep working
against the independent distribution.
"""

from __future__ import annotations

import pathlib

import pytest

import ai_hiring
import ugence_ai_hiring

# In a source checkout the monorepo's original ``ai_hiring`` package shadows the
# wheel-shipped compatibility facade, so ``import ai_hiring`` resolves to the
# historical implementation rather than the re-export facade. The facade's
# behavior is then exercised by the isolated-distribution CI job (clean wheel
# install, where only the facade exists). Detect which one we have and skip the
# facade-specific assertions when the original shadows it.
_IS_PACKAGED_FACADE = "import ugence_ai_hiring" in pathlib.Path(
    ai_hiring.__file__
).read_text()

pytestmark = pytest.mark.skipif(
    not _IS_PACKAGED_FACADE,
    reason="`ai_hiring` resolves to the monorepo original in this source checkout; "
    "the wheel facade is verified by the isolated-distribution CI job",
)


def test_version_preserved():
    assert ai_hiring.__version__ == ugence_ai_hiring.__version__
    assert ai_hiring.PRODUCT_VERSION == ugence_ai_hiring.PRODUCT_VERSION


def test_top_level_entry_points_are_identical():
    assert ai_hiring.build_in_memory_platform is ugence_ai_hiring.build_in_memory_platform
    assert ai_hiring.HiringPlatform is ugence_ai_hiring.HiringPlatform


def test_deep_submodule_object_identity():
    import ai_hiring.domain.evaluation as legacy_eval
    import ugence_ai_hiring.domain.evaluation as canon_eval

    assert legacy_eval is canon_eval
    assert legacy_eval.CandidateEvaluation is canon_eval.CandidateEvaluation


def test_from_import_preserves_class_identity():
    from ai_hiring.domain.enums import EvaluationStatus as LegacyStatus
    from ugence_ai_hiring.domain.enums import EvaluationStatus as CanonStatus

    assert LegacyStatus is CanonStatus


def test_facade_contains_no_product_logic():
    """The facade module file is a thin re-export, not an implementation."""
    import pathlib

    text = pathlib.Path(ai_hiring.__file__).read_text()
    # No class/function *definitions* of product logic beyond the module hook.
    assert "class " not in text
    # It re-exports from the canonical package.
    assert "import ugence_ai_hiring" in text


def test_build_platform_via_facade_is_functional():
    platform = ai_hiring.build_in_memory_platform()
    assert type(platform).__name__ == "HiringPlatform"
