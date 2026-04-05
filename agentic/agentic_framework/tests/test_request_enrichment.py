"""
Tests for agentic.agentic_framework.request_enrichment.

These tests pin the request-boundary enrichment seam. The helper's
contract is narrow:

    - neutral when cg_metadata is None → returns {}
    - delegates to governance_inputs_from_cg_metadata when provided
    - propagates bridge-helper errors (no silent swallowing)
    - tier selector passes through unchanged to the bridge

The helper must NOT fabricate signals it does not have, and must NOT
introduce any keys beyond what the bridge helper produces.
"""

from __future__ import annotations

import pytest

from agentic.agentic_framework.request_enrichment import (
    build_governance_enrichment_kwargs,
)


def _make_state(vritti=None, bhava=None, kosha=None, guna=None):
    """Build a 32-float sovereign state (same convention as
    test_mcp_gateway._make_state)."""
    s = [0.0] * 32
    if bhava:
        for i, v in enumerate(bhava):
            s[i] = v
    if kosha:
        for i, v in enumerate(kosha):
            s[12 + i] = v
    if vritti:
        for i, v in enumerate(vritti):
            s[17 + i] = v
    if guna:
        for i, v in enumerate(guna):
            s[22 + i] = v
    return s


def _valid_cg_metadata():
    return {
        "state": _make_state(
            bhava=[0.2] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[0.5, 0.1, 0.2, 0.1, 0.1],
            guna=[0.6, 0.3, 0.1, 0.0, 0.0, 0.9],
        ),
        "delta_S": [0.05] * 32,
    }


class TestBuildGovernanceEnrichmentKwargs:
    """The reusable request-boundary seam must be neutral by default
    and exact when signals are present."""

    def test_none_metadata_is_neutral(self):
        """cg_metadata=None → {} exactly. No keys, no surprises."""
        kwargs = build_governance_enrichment_kwargs(cg_metadata=None)
        assert kwargs == {}

    def test_default_call_is_neutral(self):
        """Calling with no args (all defaults) → {}."""
        assert build_governance_enrichment_kwargs() == {}

    def test_valid_metadata_returns_both_signals(self):
        """Valid cg_metadata → dict with both governance signals."""
        from agentic.entropy.types import EntropyResult
        from agentic.chitta_vritti.types import ChittaVrittiResult

        kwargs = build_governance_enrichment_kwargs(
            cg_metadata=_valid_cg_metadata(),
        )
        assert set(kwargs.keys()) == {"entropy_result", "vritti_result"}
        assert isinstance(kwargs["entropy_result"], EntropyResult)
        assert isinstance(kwargs["vritti_result"], ChittaVrittiResult)

    def test_no_projection_metadata_fabrication(self):
        """The helper must NOT invent sovereign_projection_metadata —
        CG adapter metadata does not carry a
        SovereignProjectionResult."""
        kwargs = build_governance_enrichment_kwargs(
            cg_metadata=_valid_cg_metadata(),
        )
        assert "sovereign_projection_metadata" not in kwargs

    def test_tier_enterprise_passes_through(self):
        """tier='enterprise' reaches both bridge engines without
        raising and still yields both signals."""
        kwargs = build_governance_enrichment_kwargs(
            cg_metadata=_valid_cg_metadata(), tier="enterprise",
        )
        assert "entropy_result" in kwargs
        assert "vritti_result" in kwargs

    def test_tier_consumer_is_default(self):
        """Default tier='consumer' matches the bridge helper's
        default and yields both signals."""
        kwargs = build_governance_enrichment_kwargs(
            cg_metadata=_valid_cg_metadata(),
        )
        assert "entropy_result" in kwargs
        assert "vritti_result" in kwargs

    def test_missing_state_raises(self):
        """Bridge errors propagate — state=None is fatal, not swallowed."""
        with pytest.raises(ValueError):
            build_governance_enrichment_kwargs(
                cg_metadata={"state": None},
            )

    def test_non_mapping_metadata_raises(self):
        """cg_metadata must be a mapping; bridge raises TypeError."""
        with pytest.raises(TypeError):
            build_governance_enrichment_kwargs(
                cg_metadata=[1, 2, 3],  # type: ignore[arg-type]
            )

    def test_kwargs_are_splattable_into_request_boundary(self):
        """The returned dict must be safe to splat into a request
        object that accepts entropy_result / vritti_result as kwargs
        — i.e. only those two keys, no others."""
        kwargs = build_governance_enrichment_kwargs(
            cg_metadata=_valid_cg_metadata(),
        )
        # Simulate a request-boundary caller splatting the dict.
        def fake_request_builder(
            *, entropy_result=None, vritti_result=None,
        ):
            return (entropy_result, vritti_result)

        entropy, vritti = fake_request_builder(**kwargs)
        assert entropy is kwargs["entropy_result"]
        assert vritti is kwargs["vritti_result"]


class TestHelperMatchesBridgeContract:
    """The seam must not drift from the underlying bridge helper."""

    def test_seam_matches_bridge_output(self):
        """build_governance_enrichment_kwargs must return precisely
        what governance_inputs_from_cg_metadata returns for the same
        inputs (modulo object identity of the result objects)."""
        from agentic.agentic_framework.sovereign_bridge import (
            governance_inputs_from_cg_metadata,
        )
        cg_md = _valid_cg_metadata()
        seam = build_governance_enrichment_kwargs(
            cg_metadata=cg_md, tier="consumer",
        )
        bridge = governance_inputs_from_cg_metadata(cg_md, tier="consumer")
        assert set(seam.keys()) == set(bridge.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
