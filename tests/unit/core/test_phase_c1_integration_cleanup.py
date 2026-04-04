"""
Phase C1: Core Integration Foundation Cleanup Tests
====================================================

Tests verifying the Phase C1 cleanup:
1. core/models.py importability and GOVERNANCE_SAFE_TYPES correctness
2. core/constants.py importability and GOVERNANCE_SAFE_CONSTANTS correctness
3. Dead placeholder modules are clearly marked (NotImplementedError behavior)
4. Legacy wrapper (StitchingObjective) deprecation warning fires
5. Exports remain consistent — no regressions in existing imports
"""

import warnings

import pytest


# =============================================================================
# 1. core/models.py — shared type contract
# =============================================================================


class TestModelsGovernanceContract:
    """Verify core/models.py is the clean shared type-contract source."""

    def test_models_importable(self):
        """core.models should be importable without error."""
        import agentic.core.models  # noqa: F401

    def test_governance_safe_types_exists(self):
        """GOVERNANCE_SAFE_TYPES should be exported."""
        from agentic.core.models import GOVERNANCE_SAFE_TYPES
        assert isinstance(GOVERNANCE_SAFE_TYPES, tuple)
        assert len(GOVERNANCE_SAFE_TYPES) > 0

    def test_governance_safe_types_contents(self):
        """GOVERNANCE_SAFE_TYPES should contain the expected types."""
        from agentic.core.models import GOVERNANCE_SAFE_TYPES
        expected = {"EntropyState", "BhavaState", "SMIResult", "AnalysisResult", "DeliveryMode"}
        assert set(GOVERNANCE_SAFE_TYPES) == expected

    def test_governance_safe_types_are_importable(self):
        """Every name in GOVERNANCE_SAFE_TYPES must be importable from models."""
        import agentic.core.models as m
        for name in m.GOVERNANCE_SAFE_TYPES:
            assert hasattr(m, name), f"{name} listed in GOVERNANCE_SAFE_TYPES but not in models"

    def test_all_exports_match(self):
        """__all__ should include GOVERNANCE_SAFE_TYPES."""
        from agentic.core.models import __all__ as exports, GOVERNANCE_SAFE_TYPES
        for name in GOVERNANCE_SAFE_TYPES:
            assert name in exports, f"{name} in GOVERNANCE_SAFE_TYPES but missing from __all__"

    def test_pipeline_internal_types_still_importable(self):
        """Pipeline-internal types should remain importable."""
        from agentic.core.models import SyllableAnalysis, WordAnalysis, RecursionState, CandidateResponse
        assert SyllableAnalysis is not None
        assert WordAnalysis is not None
        assert RecursionState is not None
        assert CandidateResponse is not None

    def test_core_package_reexports_all_models(self):
        """agentic.core should re-export all model types."""
        from agentic.core import (
            SyllableAnalysis, WordAnalysis, EntropyState, BhavaState,
            RecursionState, CandidateResponse, SMIResult, DeliveryMode, AnalysisResult,
        )
        for obj in [SyllableAnalysis, WordAnalysis, EntropyState, BhavaState,
                    RecursionState, CandidateResponse, SMIResult, DeliveryMode, AnalysisResult]:
            assert obj is not None


# =============================================================================
# 2. core/constants.py — governance-relevant constants
# =============================================================================


class TestConstantsGovernanceContract:
    """Verify core/constants.py exposes governance-safe constants."""

    def test_constants_importable(self):
        """core.constants should be importable without error."""
        import agentic.core.constants  # noqa: F401

    def test_governance_safe_constants_exists(self):
        """GOVERNANCE_SAFE_CONSTANTS should be exported."""
        from agentic.core.constants import GOVERNANCE_SAFE_CONSTANTS
        assert isinstance(GOVERNANCE_SAFE_CONSTANTS, tuple)
        assert len(GOVERNANCE_SAFE_CONSTANTS) > 0

    def test_governance_safe_constants_contents(self):
        """GOVERNANCE_SAFE_CONSTANTS should contain the expected names."""
        from agentic.core.constants import GOVERNANCE_SAFE_CONSTANTS
        expected = {"SMI_THRESHOLDS", "DHA_TONES", "CANONICAL_KOSHA_LAYERS", "ONTOLOGICAL_LAYERS"}
        assert set(GOVERNANCE_SAFE_CONSTANTS) == expected

    def test_governance_safe_constants_are_importable(self):
        """Every name in GOVERNANCE_SAFE_CONSTANTS must be importable."""
        import agentic.core.constants as c
        for name in c.GOVERNANCE_SAFE_CONSTANTS:
            assert hasattr(c, name), f"{name} listed in GOVERNANCE_SAFE_CONSTANTS but not in constants"

    def test_pipeline_internal_constants_still_importable(self):
        """Pipeline-internal constants should remain importable."""
        from agentic.core.constants import CONSONANT_TO_KOSHA_MAP, V26_STITCHING_WEIGHTS
        assert CONSONANT_TO_KOSHA_MAP is not None
        assert V26_STITCHING_WEIGHTS is not None


# =============================================================================
# 3. Dead placeholder modules — clearly marked, raise NotImplementedError
# =============================================================================


class TestDeadPlaceholderBhava:
    """Verify bhava/ placeholder modules are marked and non-functional."""

    def test_bhava_geometry_importable(self):
        from agentic.core.bhava.bhava_geometry import BhavaGeometry
        assert BhavaGeometry is not None

    def test_bhava_geometry_methods_raise(self):
        from agentic.core.bhava.bhava_geometry import BhavaGeometry
        bg = BhavaGeometry()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            bg.compute_distance(None, None)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            bg.interpolate(None, None, 0.5)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            bg.project_to_kosha(None)

    def test_bhava_geometry_docstring_marked(self):
        import agentic.core.bhava.bhava_geometry as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_temporal_bhava_importable(self):
        from agentic.core.bhava.temporal_bhava import TemporalBhava
        assert TemporalBhava is not None

    def test_temporal_bhava_methods_raise(self):
        from agentic.core.bhava.temporal_bhava import TemporalBhava
        tb = TemporalBhava()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            tb.update(None)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            tb.get_trend()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            tb.detect_shift()

    def test_temporal_bhava_docstring_marked(self):
        import agentic.core.bhava.temporal_bhava as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_bhava_init_docstring_marked(self):
        import agentic.core.bhava as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__


class TestDeadPlaceholderEnergy:
    """Verify energy/ placeholder modules are marked and non-functional."""

    def test_energy_words_importable(self):
        from agentic.core.energy.energy_words import EnergyWordDetector
        assert EnergyWordDetector is not None

    def test_energy_words_methods_raise(self):
        from agentic.core.energy.energy_words import EnergyWordDetector
        ew = EnergyWordDetector()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            ew.detect(["test"])
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            ew.get_energy_score("test")

    def test_energy_words_docstring_marked(self):
        import agentic.core.energy.energy_words as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_energy_init_docstring_marked(self):
        import agentic.core.energy as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__


class TestDeadPlaceholderRegulators:
    """Verify regulators/ placeholder modules are marked and non-functional."""

    def test_fallback_methods_raise(self):
        from agentic.core.regulators.fallback import FallbackRegulator
        fb = FallbackRegulator()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            fb.check_safety(None)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            fb.get_fallback_mode("test")

    def test_fallback_docstring_marked(self):
        import agentic.core.regulators.fallback as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_mirror_time_methods_raise(self):
        from agentic.core.regulators.mirror_time import MirrorTime
        mt = MirrorTime()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            mt.should_defer(0.5, 0.3)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            mt.compute_readiness(0.1, 0.2, 0.3, 1.0)

    def test_mirror_time_docstring_marked(self):
        import agentic.core.regulators.mirror_time as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_ladder_methods_raise(self):
        from agentic.core.regulators.ladder import LadderRegulator
        lr = LadderRegulator()
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            lr.compute_pressure(1.0)
        with pytest.raises(NotImplementedError, match="Symbol-U formula"):
            lr.should_surface(0.5, 0.7)

    def test_ladder_docstring_marked(self):
        import agentic.core.regulators.ladder as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__

    def test_regulators_init_docstring_marked(self):
        import agentic.core.regulators as mod
        assert "PLACEHOLDER" in mod.__doc__
        assert "NOT IMPLEMENTED" in mod.__doc__


# =============================================================================
# 4. Legacy wrapper — StitchingObjective deprecation
# =============================================================================


class TestStitchingObjectiveLegacy:
    """Verify StitchingObjective emits DeprecationWarning."""

    def test_stitching_objective_importable(self):
        """StitchingObjective should still be importable."""
        from agentic.core.stitching.objective import StitchingObjective
        assert StitchingObjective is not None

    def test_stitching_objective_deprecation_warning(self):
        """Instantiating StitchingObjective should emit DeprecationWarning."""
        from agentic.core.stitching.objective import StitchingObjective
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            StitchingObjective()
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "deprecated" in str(dep_warnings[0].message).lower()
            assert "StitchingEngine" in str(dep_warnings[0].message)

    def test_stitching_objective_module_docstring_marked(self):
        """objective.py module docstring should be marked as deprecated."""
        import agentic.core.stitching.objective as mod
        assert "DEPRECATED" in mod.__doc__
        assert "LEGACY" in mod.__doc__

    def test_stitching_init_marks_objective_as_legacy(self):
        """stitching/__init__.py __all__ should note StitchingObjective as deprecated."""
        import inspect
        import agentic.core.stitching as mod
        source = inspect.getsource(mod)
        assert "DEPRECATED" in source


# =============================================================================
# 5. No regressions — existing imports still work
# =============================================================================


class TestNoRegressions:
    """Verify no regressions in existing import paths."""

    def test_core_smi_importable(self):
        from agentic.core import smi  # noqa: F401

    def test_core_stitching_importable(self):
        from agentic.core import stitching  # noqa: F401

    def test_stitching_engine_importable(self):
        from agentic.core.stitching import StitchingEngine
        assert StitchingEngine is not None

    def test_stitching_all_exports_importable(self):
        """Every name in stitching.__all__ should be importable."""
        import agentic.core.stitching as st
        for name in st.__all__:
            assert hasattr(st, name), f"{name} in stitching.__all__ but not importable"

    def test_core_all_exports_importable(self):
        """Every name in core.__all__ should be importable."""
        import agentic.core as core
        for name in core.__all__:
            assert hasattr(core, name), f"{name} in core.__all__ but not importable"

    def test_constants_all_exports_importable(self):
        """Every name in constants.__all__ should be importable."""
        import agentic.core.constants as c
        for name in c.__all__:
            assert hasattr(c, name), f"{name} in constants.__all__ but not importable"
