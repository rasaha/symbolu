"""
Repository Refactoring Smoke Test

This test verifies that key imports are intact after the repository
normalization refactoring. It tests both the new canonical paths and
backward-compatibility shims.

Run with:
    pytest tests/test_repo_refactor_smoke.py -v
"""

import pytest
import warnings


class TestNewCanonicalImports:
    """Tests for imports from new canonical paths."""

    def test_p15_authority_guard_import(self):
        """P15 authority guard imports from new canonical path."""
        from symbolu.mechanical.pipeline.p15_authority_guard import (
            P15AuthoritySnapshot,
            P15RegressionViolation,
            P15RegressionViolationError,
            ViolationType,
            P15RegressionGuard,
            capture_p15_snapshot,
            enforce_p15_regression_guard,
            get_p15_snapshot,
            has_p15_snapshot,
        )

        # Verify classes exist
        assert P15AuthoritySnapshot is not None
        assert P15RegressionViolation is not None
        assert P15RegressionViolationError is not None
        assert ViolationType is not None
        assert P15RegressionGuard is not None

        # Verify functions exist
        assert callable(capture_p15_snapshot)
        assert callable(enforce_p15_regression_guard)
        assert callable(get_p15_snapshot)
        assert callable(has_p15_snapshot)

    def test_p15_authority_guard_submodules(self):
        """P15 authority guard submodule imports work."""
        from symbolu.mechanical.pipeline.p15_authority_guard.p15_regression_schema import (
            P15AuthoritySnapshot,
            ViolationType,
        )
        from symbolu.mechanical.pipeline.p15_authority_guard.p15_regression_guard import (
            P15RegressionGuard,
        )
        from symbolu.mechanical.pipeline.p15_authority_guard.p15_integration import (
            capture_p15_snapshot,
        )

        assert P15AuthoritySnapshot is not None
        assert ViolationType is not None
        assert P15RegressionGuard is not None
        assert callable(capture_p15_snapshot)


class TestBackwardCompatibilityShims:
    """Tests for backward-compatibility shim imports."""

    def test_phase15_regression_guard_shim_import(self):
        """Deprecated phase15_regression_guard shim still works."""
        # Suppress the deprecation warning for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            from symbolu.mechanical.pipeline.phase15_regression_guard import (
                P15AuthoritySnapshot,
                P15RegressionViolation,
                P15RegressionViolationError,
                ViolationType,
                P15RegressionGuard,
                capture_p15_snapshot,
                enforce_p15_regression_guard,
                get_p15_snapshot,
                has_p15_snapshot,
            )

            # Verify all exports work
            assert P15AuthoritySnapshot is not None
            assert P15RegressionGuard is not None
            assert callable(capture_p15_snapshot)

    def test_phase15_shim_emits_deprecation_warning(self):
        """Deprecated shim emits DeprecationWarning."""
        # Clear any cached imports
        import sys

        if "symbolu.mechanical.pipeline.phase15_regression_guard" in sys.modules:
            del sys.modules["symbolu.mechanical.pipeline.phase15_regression_guard"]

        with pytest.warns(DeprecationWarning, match="phase15_regression_guard.*deprecated"):
            import symbolu.mechanical.pipeline.phase15_regression_guard  # noqa: F401


class TestKeyPipelinePhaseImports:
    """Tests for key pipeline phase imports."""

    def test_phase_zero_import(self):
        """phase_zero imports work."""
        from symbolu.mechanical.pipeline.phase_zero import (
            phase_zero_schema,
            phase_zero_resolver,
        )

        assert phase_zero_schema is not None
        assert phase_zero_resolver is not None

    def test_phase_one_import(self):
        """phase_one imports work."""
        from symbolu.mechanical.pipeline.phase_one import (
            phase_one_schema,
            phase_one_resolver,
        )

        assert phase_one_schema is not None
        assert phase_one_resolver is not None

    def test_p15_interaction_import(self):
        """p15_interaction imports work."""
        from symbolu.mechanical.pipeline.p15_interaction import (
            InteractionMode,
            InteractionDirective,
            P15InteractionResolver,
            maybe_run_p15,
        )

        assert InteractionMode is not None
        assert InteractionDirective is not None
        assert P15InteractionResolver is not None
        assert callable(maybe_run_p15)

    def test_p16_regression_guard_import(self):
        """p16_regression_guard imports work."""
        from symbolu.mechanical.pipeline.p16_regression_guard import (
            P16RegressionGuard,
            maybe_run_p16_guard_pre,
            maybe_run_p16_guard_post,
        )

        assert P16RegressionGuard is not None
        assert callable(maybe_run_p16_guard_pre)
        assert callable(maybe_run_p16_guard_post)

    def test_p7_discourse_import(self):
        """p7_discourse imports work."""
        from symbolu.mechanical.pipeline.p7_discourse import (
            p7_discourse_schema,
        )

        assert p7_discourse_schema is not None

    def test_p8_semantics_import(self):
        """p8_semantics imports work."""
        from symbolu.mechanical.pipeline.p8_semantics import (
            p8_semantic_schema,
        )

        assert p8_semantic_schema is not None

    def test_grounding_import(self):
        """grounding phase imports work."""
        from symbolu.mechanical.pipeline.grounding import (
            phase_minus_one_schema,
        )

        assert phase_minus_one_schema is not None


class TestCoreModuleImports:
    """Tests for core module imports."""

    def test_coherence_engine_import(self):
        """coherence engine imports work."""
        from symbolu.core.coherence import coherence_engine

        assert coherence_engine is not None

    def test_coherence_state_import(self):
        """coherence state imports work."""
        from symbolu.core.coherence import coherence_state

        assert coherence_state is not None


class TestFormulaModuleImports:
    """Tests for formula module imports (protected modules)."""

    def test_acoustic_unit_mapper_import(self):
        """acoustic_unit_mapper imports work (protected module)."""
        from symbolu.formulas import acoustic_unit_mapper

        assert acoustic_unit_mapper is not None

    def test_vritti_mapper_import(self):
        """vritti_mapper imports work (protected module)."""
        from symbolu.formulas import vritti_mapper

        assert vritti_mapper is not None

    def test_phase1_snapshot_import(self):
        """phase1_snapshot imports work (protected module)."""
        from symbolu.formulas import phase1_snapshot

        assert phase1_snapshot is not None

    def test_resonance_formulas_import(self):
        """resonance_formulas imports work (protected module)."""
        from symbolu.formulas import resonance_formulas

        assert resonance_formulas is not None


class TestPipelineOrchestratorImport:
    """Tests for pipeline orchestrator import."""

    def test_orchestrator_import(self):
        """Pipeline orchestrator imports work."""
        from symbolu.mechanical.pipeline import orchestrator

        assert orchestrator is not None

    def test_models_import(self):
        """Pipeline models imports work."""
        from symbolu.mechanical.pipeline import models

        assert models is not None


class TestNoNamingConflicts:
    """Tests to verify naming conflicts are resolved."""

    def test_p15_interaction_and_authority_guard_are_distinct(self):
        """p15_interaction and p15_authority_guard are distinct modules."""
        from symbolu.mechanical.pipeline import p15_interaction
        from symbolu.mechanical.pipeline import p15_authority_guard

        # They should be different modules
        assert p15_interaction is not p15_authority_guard

        # p15_interaction has InteractionMode
        assert hasattr(p15_interaction, "InteractionMode")

        # p15_authority_guard has P15RegressionGuard
        assert hasattr(p15_authority_guard, "P15RegressionGuard")

        # Neither should have the other's main class
        assert not hasattr(p15_interaction, "P15RegressionGuard")
        assert not hasattr(p15_authority_guard, "InteractionMode")
