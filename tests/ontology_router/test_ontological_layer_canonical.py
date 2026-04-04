"""
Test OntologicalLayer Canonicalization (O1)
============================================

Verifies that OntologicalLayer has a single canonical source and that
all modules that previously defined their own copy now import from
the canonical source.

O1 Invariants:
    - Single source of truth: symbolu.ontology.layers.ontology_layer
    - All import paths resolve to the SAME class object
    - Exactly 12 members with correct names and values
    - No independent/duplicate OntologicalLayer definitions in
      projection/api_models or router/ontological_router_r1
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# =============================================================================
# Canonical Source Tests
# =============================================================================

class TestCanonicalSource:
    """OntologicalLayer is defined in exactly one place."""

    def test_canonical_import(self) -> None:
        """The canonical source is symbolu.ontology.layers.ontology_layer."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer
        assert OntologicalLayer is not None
        assert len(OntologicalLayer) == 12

    def test_canonical_values(self) -> None:
        """All 12 layers have correct names and integer values."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        expected = {
            "POTENTIAL": 1, "IDENTITY": 2, "EXECUTION": 3, "STRUCTURE": 4,
            "COGNITION": 5, "AGENCY": 6, "REASONING": 7, "PURPOSE": 8,
            "WITNESSES": 9, "UNIFYING": 10, "INTEGRATION": 11, "ABSOLVING": 12,
        }
        for name, value in expected.items():
            member = OntologicalLayer[name]
            assert member.value == value, f"{name} should be {value}, got {member.value}"

    def test_canonical_repr(self) -> None:
        """Canonical OntologicalLayer has clean repr."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer
        assert repr(OntologicalLayer.POTENTIAL) == "OntologicalLayer.POTENTIAL"

    def test_all_layers_tuple(self) -> None:
        """ALL_LAYERS is a tuple of all 12 layers in order."""
        from symbolu.ontology.layers.ontology_layer import ALL_LAYERS, OntologicalLayer
        assert isinstance(ALL_LAYERS, tuple)
        assert len(ALL_LAYERS) == 12
        assert ALL_LAYERS == tuple(OntologicalLayer)

    def test_gated_layers_frozenset(self) -> None:
        """GATED_LAYERS contains only ABSOLVING."""
        from symbolu.ontology.layers.ontology_layer import GATED_LAYERS, OntologicalLayer
        assert isinstance(GATED_LAYERS, frozenset)
        assert GATED_LAYERS == frozenset({OntologicalLayer.ABSOLVING})


# =============================================================================
# Identity Tests — All Import Paths Resolve to Same Class
# =============================================================================

class TestIdentityAcrossModules:
    """All modules that expose OntologicalLayer resolve to the same class."""

    def test_projection_api_models_uses_canonical(self) -> None:
        """projection.api_models.OntologicalLayer IS the canonical class."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.projection.api_models import OntologicalLayer as FromProjection
        assert FromProjection is Canonical

    def test_router_r1_uses_canonical(self) -> None:
        """router.ontological_router_r1.OntologicalLayer IS the canonical class."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer as FromRouter
        assert FromRouter is Canonical

    def test_layers_package_init_uses_canonical(self) -> None:
        """layers.__init__.OntologicalLayer IS the canonical class."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.layers import OntologicalLayer as FromInit
        assert FromInit is Canonical

    def test_projection_init_uses_canonical(self) -> None:
        """projection.__init__.OntologicalLayer IS the canonical class."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.projection import OntologicalLayer as FromProjectionInit
        assert FromProjectionInit is Canonical

    def test_cross_module_enum_equality(self) -> None:
        """Enum members from different import paths are identical objects."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer as FromRouter
        from symbolu.ontology.projection.api_models import OntologicalLayer as FromProjection

        for member in Canonical:
            assert FromRouter[member.name] is member
            assert FromProjection[member.name] is member

    def test_isinstance_across_modules(self) -> None:
        """isinstance works across all import paths."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer as Canonical
        from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer as FromRouter

        layer = FromRouter.COGNITION
        assert isinstance(layer, Canonical)

        layer2 = Canonical.AGENCY
        assert isinstance(layer2, FromRouter)


# =============================================================================
# No Independent Definitions — AST Verification
# =============================================================================

class TestNoIndependentDefinitions:
    """
    Verify via AST that projection/api_models.py and router/ontological_router_r1.py
    do NOT define their own OntologicalLayer class.
    """

    @staticmethod
    def _get_class_names(filepath: Path) -> set:
        """Extract all class definition names from a Python file."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }

    def test_projection_api_models_no_local_enum(self) -> None:
        """projection/api_models.py does not define OntologicalLayer."""
        filepath = Path(__file__).parent.parent.parent / "symbolu" / "ontology" / "projection" / "api_models.py"
        class_names = self._get_class_names(filepath)
        assert "OntologicalLayer" not in class_names, (
            "projection/api_models.py must not define its own OntologicalLayer — "
            "it should import from symbolu.ontology.layers.ontology_layer"
        )

    def test_router_r1_no_local_enum(self) -> None:
        """router/ontological_router_r1.py does not define OntologicalLayer."""
        filepath = Path(__file__).parent.parent.parent / "symbolu" / "ontology" / "router" / "ontological_router_r1.py"
        class_names = self._get_class_names(filepath)
        assert "OntologicalLayer" not in class_names, (
            "router/ontological_router_r1.py must not define its own OntologicalLayer — "
            "it should import from symbolu.ontology.layers.ontology_layer"
        )

    def test_canonical_source_defines_enum(self) -> None:
        """layers/ontology_layer.py DOES define OntologicalLayer (it's the source)."""
        filepath = Path(__file__).parent.parent.parent / "symbolu" / "ontology" / "layers" / "ontology_layer.py"
        class_names = self._get_class_names(filepath)
        assert "OntologicalLayer" in class_names, (
            "layers/ontology_layer.py must define OntologicalLayer — it is the canonical source"
        )


# =============================================================================
# Behavioral Compatibility — Router Still Works
# =============================================================================

class TestRouterCompatibility:
    """Router behavior is unchanged after canonicalization."""

    def test_router_creates_valid_response(self) -> None:
        """R1 router produces valid ProjectionResponse with canonical enum."""
        from symbolu.ontology.router.ontological_router_r1 import (
            OntologicalLayerRouter,
            ProjectionRequest,
            OntologicalLayer,
        )
        router = OntologicalLayerRouter()
        req = ProjectionRequest(
            artifact_id="test_artifact_001",
            phase_id="5",
            artifact_hash="abc123def456",
        )
        resp = router.project(req)
        assert resp.projected_layers == (OntologicalLayer.COGNITION,)
        assert resp.router_version == "R1.0"

    def test_router_hint_uses_canonical_enum(self) -> None:
        """Declared projection hints work with canonical enum members."""
        from symbolu.ontology.router.ontological_router_r1 import (
            OntologicalLayerRouter,
            ProjectionRequest,
        )
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        router = OntologicalLayerRouter()
        req = ProjectionRequest(
            artifact_id="test_artifact_002",
            phase_id="5",
            artifact_hash="abc123def456",
            declared_projection_hint=OntologicalLayer.UNIFYING,
        )
        resp = router.project(req)
        assert resp.projected_layers == (OntologicalLayer.UNIFYING,)

    def test_router_absolving_gate_still_enforced(self) -> None:
        """ABSOLVING gate remains enforced with canonical enum."""
        from symbolu.ontology.router.ontological_router_r1 import (
            OntologicalLayerRouter,
            ProjectionBlockedError,
            ProjectionRequest,
            BlockedReason,
        )
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        router = OntologicalLayerRouter(explicit_absolving_opt_in=False)
        req = ProjectionRequest(
            artifact_id="test_artifact_003",
            phase_id="9",
            artifact_hash="abc123def456",
            declared_projection_hint=OntologicalLayer.ABSOLVING,
        )
        with pytest.raises(ProjectionBlockedError) as exc_info:
            router.project(req)
        assert exc_info.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST


# =============================================================================
# Projection Compatibility — Projection Models Still Work
# =============================================================================

class TestProjectionCompatibility:
    """Projection models work with canonical enum."""

    def test_projection_request_accepts_canonical_layer(self) -> None:
        """ProjectionRequest accepts canonical OntologicalLayer."""
        from symbolu.ontology.projection.api_models import (
            InputRef,
            InputRefKind,
            ProjectionRequest,
        )
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        req = ProjectionRequest(
            snapshot_id="snap_001",
            layer=OntologicalLayer.COGNITION,
            input_ref=InputRef(kind=InputRefKind.GENERIC, object_id="obj_001"),
        )
        assert req.layer is OntologicalLayer.COGNITION
        assert req.layer.value == 5

    def test_projection_response_round_trip(self) -> None:
        """ProjectionResponse stores and returns canonical enum."""
        from symbolu.ontology.projection.api_models import (
            InputRef,
            InputRefKind,
            ProjectionResponse,
        )
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        resp = ProjectionResponse(
            projection_id="proj_001",
            snapshot_id="snap_001",
            layer=OntologicalLayer.WITNESSES,
            input_ref=InputRef(kind=InputRefKind.GENERIC, object_id="obj_001"),
        )
        assert resp.layer is OntologicalLayer.WITNESSES
        assert resp.layer.value == 9
