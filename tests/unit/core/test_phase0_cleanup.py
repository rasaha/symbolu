"""
Phase 0: Signal Cleanup and Canonical Authority Tests
=====================================================

Tests verifying the Phase 0 cleanup:
1. Dead core facades (interface.py, pipeline.py) are removed
2. core/__init__.py exports active data models (not dead facades)
3. core/entropy/ stub is removed (real entropy lives in agentic/entropy/)
4. CoreBridge deprecation shim works correctly
5. Canonical runtime vritti authority docstrings are in place
6. Canonical runtime guna authority docstrings are in place
7. Backward compatibility: core data models remain importable
"""

import pytest
import warnings
import importlib
import os

# Some modules require numpy/torch which may not be in all test environments
try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import torch  # noqa: F401
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# =============================================================================
# TASK 1: Dead core facade removal
# =============================================================================


class TestDeadFacadeRemoval:
    """Verify dead CoreInterface and CorePipeline facades are removed."""

    def test_core_interface_module_removed(self):
        """core/interface.py should no longer exist as a module."""
        with pytest.raises(ImportError):
            import agentic.core.interface  # noqa: F401

    def test_core_pipeline_module_removed(self):
        """core/pipeline.py should no longer exist as a module."""
        with pytest.raises(ImportError):
            import agentic.core.pipeline  # noqa: F401

    def test_core_init_no_longer_exports_dead_facades(self):
        """core/__init__.py should not export CoreInterface or CorePipeline."""
        import agentic.core as core
        assert not hasattr(core, "CoreInterface")
        assert not hasattr(core, "CorePipeline")


# =============================================================================
# TASK 2: Dead core/entropy/ removal
# =============================================================================


class TestDeadEntropyRemoval:
    """Verify dead core/entropy/ stub is removed."""

    def test_core_entropy_module_removed(self):
        """core/entropy/ should no longer exist as a module."""
        with pytest.raises(ImportError):
            import agentic.core.entropy  # noqa: F401

    def test_core_entropy_engine_removed(self):
        """core/entropy/entropy_engine.py should no longer exist."""
        with pytest.raises(ImportError):
            import agentic.core.entropy.entropy_engine  # noqa: F401

    def test_real_entropy_module_exists(self):
        """The real entropy module at agentic/entropy/ should still exist."""
        import agentic.entropy  # noqa: F401


# =============================================================================
# TASK 1+2: core/__init__.py exports active symbols
# =============================================================================


class TestCoreExportsActiveSymbols:
    """Verify core/__init__.py exports correct active data models."""

    def test_core_exports_smi_result(self):
        from agentic.core import SMIResult
        assert SMIResult is not None

    def test_core_exports_bhava_state(self):
        from agentic.core import BhavaState
        assert BhavaState is not None

    def test_core_exports_entropy_state(self):
        from agentic.core import EntropyState
        assert EntropyState is not None

    def test_core_exports_analysis_result(self):
        from agentic.core import AnalysisResult
        assert AnalysisResult is not None

    def test_core_exports_candidate_response(self):
        from agentic.core import CandidateResponse
        assert CandidateResponse is not None

    def test_core_exports_delivery_mode(self):
        from agentic.core import DeliveryMode
        assert DeliveryMode is not None

    def test_core_exports_syllable_analysis(self):
        from agentic.core import SyllableAnalysis
        assert SyllableAnalysis is not None

    def test_core_exports_word_analysis(self):
        from agentic.core import WordAnalysis
        assert WordAnalysis is not None

    def test_core_exports_recursion_state(self):
        from agentic.core import RecursionState
        assert RecursionState is not None

    def test_core_models_still_importable_directly(self):
        """Data models should still be importable from core.models."""
        from agentic.core.models import SMIResult, BhavaState, EntropyState
        assert SMIResult is not None
        assert BhavaState is not None
        assert EntropyState is not None

    def test_active_subpackages_importable(self):
        """Active subpackages should still be importable."""
        from agentic.core import smi  # noqa: F401
        from agentic.core import stitching  # noqa: F401


# =============================================================================
# TASK 1: CoreBridge deprecation shim
# =============================================================================


class TestCoreBridgeDeprecation:
    """Verify CoreBridge deprecation shim works."""

    def test_core_bridge_import_succeeds(self):
        """CoreBridge should still be importable (shim)."""
        from symbolu_core.mechanical.core_bridge import CoreBridge
        assert CoreBridge is not None

    def test_core_bridge_instantiation_warns(self):
        """CoreBridge() should emit DeprecationWarning."""
        from symbolu_core.mechanical.core_bridge import CoreBridge
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bridge = CoreBridge()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    def test_core_bridge_analyze_raises(self):
        """CoreBridge.analyze() should raise NotImplementedError with migration info."""
        from symbolu_core.mechanical.core_bridge import CoreBridge
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            bridge = CoreBridge()
        with pytest.raises(NotImplementedError, match="deprecated"):
            bridge.analyze("test")

    def test_core_bridge_get_smi_raises(self):
        """CoreBridge.get_smi() should raise NotImplementedError with migration info."""
        from symbolu_core.mechanical.core_bridge import CoreBridge
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            bridge = CoreBridge()
        with pytest.raises(NotImplementedError, match="deprecated"):
            bridge.get_smi("test")


# =============================================================================
# TASK 3: Canonical runtime vritti authority
# =============================================================================


class TestCanonicalVrittiAuthority:
    """Verify chitta_vritti is marked as canonical runtime vritti authority."""

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
    def test_chitta_vritti_importable(self):
        """chitta_vritti module should be importable."""
        import agentic.chitta_vritti as cv
        assert hasattr(cv, "ChittaVrittiEngine")
        assert hasattr(cv, "ChittaVrittiInputs")
        assert hasattr(cv, "ChittaVrittiResult")

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
    def test_chitta_vritti_docstring_declares_authority(self):
        """chitta_vritti docstring should declare canonical authority."""
        import agentic.chitta_vritti as cv
        assert "CANONICAL RUNTIME VRITTI AUTHORITY" in cv.__doc__

    def test_chitta_vritti_init_file_has_authority_marker(self):
        """chitta_vritti/__init__.py source should contain authority marker."""
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "chitta_vritti", "__init__.py"
        )
        with open(init_path) as f:
            content = f.read()
        assert "CANONICAL RUNTIME VRITTI AUTHORITY" in content

    def test_vritti_mapping_docstring_declares_complementary(self):
        """vritti_mapping docstring should declare itself as complementary."""
        import agentic.core.smi.vritti_mapping as vm
        assert "complementary" in vm.__doc__.lower()
        assert "canonical runtime vritti authority" in vm.__doc__.lower()

    def test_vritti_mapping_still_functional(self):
        """VrittiMapper should still work (not broken by cleanup)."""
        from agentic.core.smi.vritti_mapping import VrittiMapper
        mapper = VrittiMapper()
        dist = mapper.map_syllable_to_vritti("ka")
        assert len(dist) == 5
        assert abs(sum(dist) - 1.0) < 1e-6


# =============================================================================
# TASK 4: Canonical runtime guna authority
# =============================================================================


class TestCanonicalGunaAuthority:
    """Verify guna_modulation is marked as canonical runtime guna authority."""

    def test_guna_modulation_importable(self):
        """guna_modulation module should be importable."""
        import agentic.guna_modulation as gm
        assert hasattr(gm, "derive_guna_vector")
        assert hasattr(gm, "derive_guna_from_values")

    def test_guna_modulation_docstring_declares_authority(self):
        """guna_modulation docstring should declare canonical authority."""
        import agentic.guna_modulation as gm
        assert "CANONICAL RUNTIME GUNA AUTHORITY" in gm.__doc__

    def test_guna_derivation_docstring_declares_canonical(self):
        """guna_derivation docstring should declare canonical derivation."""
        import agentic.guna_modulation.guna_derivation as gd
        assert "CANONICAL RUNTIME GUNA DERIVATION" in gd.__doc__

    def test_guna_derivation_still_functional(self):
        """derive_guna_from_values should still work."""
        from agentic.guna_modulation import derive_guna_from_values
        guna = derive_guna_from_values(C_s=0.7, M=0.5, H=0.3)
        assert abs(guna.sattva + guna.rajas + guna.tamas - 1.0) < 1e-6
        assert guna.sattva >= 0.0
        assert guna.rajas >= 0.0
        assert guna.tamas >= 0.0

    @pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
    def test_inference_guna_docstring_declares_complementary(self):
        """inference/guna_inference.py docstring should declare complementary."""
        import agentic.inference.guna_inference as gi
        assert "complementary" in gi.__doc__.lower()
        assert "canonical runtime guna authority" in gi.__doc__.lower()

    def test_inference_guna_file_has_complementary_marker(self):
        """inference/guna_inference.py source should contain complementary marker."""
        gi_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "inference", "guna_inference.py"
        )
        with open(gi_path) as f:
            content = f.read()
        assert "complementary" in content.lower()
        assert "canonical runtime guna authority" in content.lower()


# =============================================================================
# TASK 5: No competing entropy authorities
# =============================================================================


class TestNoCompetingEntropy:
    """Verify there is no competing entropy authority in core/."""

    def test_no_core_entropy_directory(self):
        """core/entropy/ directory should not exist."""
        import os
        core_entropy_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "core", "entropy"
        )
        assert not os.path.exists(core_entropy_path), (
            f"core/entropy/ still exists at {core_entropy_path}"
        )
