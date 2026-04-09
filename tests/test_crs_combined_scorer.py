"""
Unit tests for CRSCombinedScorer (Phase 2).

Tests:
  1. Semantic suppression — high C, high R, low S → strongly suppressed
  2. Semantic survival — moderate C, moderate R, high S → viable
  3. Flag-off compatibility — CRS disabled produces legacy T shape
  4. Cache refresh — S_tok populated when CRS enabled, no-op when disabled
  5. Top-1 divergence — semantic gating changes ranking vs pure R
"""

import pytest
import torch
import torch.nn as nn

from symbolu_training.training.conscious_generation.primitives.csr_scorer import CSRTokenScorer
from symbolu_training.training.conscious_generation.primitives.crs_combined_scorer import CRSCombinedScorer
from symbolu_training.training.conscious_generation.token_ontology import TokenOntologyProjector
from symbolu_training.training.conscious_generation.token_cache import TokenPrimitiveCache


EMBED_DIM = 64
STATE_DIM = 32
VOCAB_SIZE = 128
K = 8  # shortlist size


def _make_csr_scorer():
    return CSRTokenScorer(
        embed_dim=EMBED_DIM,
        state_dim=STATE_DIM,
        csr_dim=16,
        use_low_rank=True,
        rank=4,
    )


def _make_crs_scorer(csr_scorer=None, **kwargs):
    if csr_scorer is None:
        csr_scorer = _make_csr_scorer()
    defaults = dict(
        csr_scorer=csr_scorer,
        embed_dim=EMBED_DIM,
        semantic_dim=16,
        w_c=0.2,
        w_r=0.2,
        w_s=0.6,
        s_threshold=0.45,
        k_s=10.0,
        alpha_base=0.5,
    )
    defaults.update(kwargs)
    return CRSCombinedScorer(**defaults)


def _make_forward_inputs(batch=2, seq=4):
    """Create synthetic inputs for CRSCombinedScorer.forward()."""
    return dict(
        v_ctx=torch.softmax(torch.randn(batch, seq, 5), dim=-1),
        kosha_ctx=torch.softmax(torch.randn(batch, seq, 5), dim=-1),
        V_cand=torch.softmax(torch.randn(batch, seq, K, 5), dim=-1),
        Kosha_cand=torch.softmax(torch.randn(batch, seq, K, 5), dim=-1),
        r_ctx=torch.randn(batch, seq, 16),
        R_cand=torch.randn(batch, seq, K, 16),
        hidden=torch.randn(batch, seq, EMBED_DIM),
        o_ctx=torch.randn(batch, seq, STATE_DIM),
        S_cand=torch.randn(batch, seq, K, 16),
        base_logits_cand=torch.randn(batch, seq, K),
    )


# ---------------------------------------------------------------
# Test 1: Semantic suppression
# ---------------------------------------------------------------

class TestSemanticSuppression:
    """High C + high R + low S must produce strongly suppressed CRS
    relative to a high-S candidate in the same candidate set."""

    def test_low_S_is_crushed(self):
        crs = _make_crs_scorer()

        # 4 candidates: first two have low S, last two have high S
        # Center-normalization operates across candidates (last dim),
        # so we need a mix of high and low S in one set.
        C_raw = torch.tensor([1.5, 1.5, 0.5, 0.5])
        R_raw = torch.tensor([1.8, 1.8, 0.3, 0.3])
        S_raw = torch.tensor([-1.0, -2.0, 1.0, 1.5])  # low, very low, high, high

        result = crs.combine_crs(C_raw, R_raw, S_raw)
        crs_score = result['crs_score']
        S_gate = result['S_gate']

        # Low-S candidates (idx 0, 1) should have lower S_gate than high-S (idx 2, 3)
        assert S_gate[0].item() < S_gate[2].item(), \
            f"Low-S gate ({S_gate[0].item():.3f}) should be < high-S gate ({S_gate[2].item():.3f})"
        assert S_gate[1].item() < S_gate[0].item(), \
            f"Very-low-S gate ({S_gate[1].item():.3f}) should be < low-S gate ({S_gate[0].item():.3f})"

        # Low-S CRS score should be much smaller than high-S CRS score
        assert abs(crs_score[1].item()) < abs(crs_score[3].item()), \
            f"Very-low-S CRS ({crs_score[1].item():.4f}) should be smaller than high-S CRS ({crs_score[3].item():.4f})"


# ---------------------------------------------------------------
# Test 2: Semantic survival
# ---------------------------------------------------------------

class TestSemanticSurvival:
    """Within a candidate set, high-S candidates must rank above low-S candidates."""

    def test_high_S_passes(self):
        crs = _make_crs_scorer()

        # Candidate set: one high-S, one low-S
        C_raw = torch.tensor([0.5, 0.5])
        R_raw = torch.tensor([0.3, 0.3])
        S_raw = torch.tensor([1.5, -1.0])

        result = crs.combine_crs(C_raw, R_raw, S_raw)
        crs_score = result['crs_score']
        S_gate = result['S_gate']

        # High-S candidate (idx 0) should have higher gate and score
        assert S_gate[0].item() > S_gate[1].item(), \
            f"High-S gate ({S_gate[0].item():.3f}) should be > low-S gate ({S_gate[1].item():.3f})"
        assert crs_score[0].item() > crs_score[1].item(), \
            f"High-S CRS ({crs_score[0].item():.4f}) should be > low-S CRS ({crs_score[1].item():.4f})"

    def test_suppression_ratio(self):
        """Low-S candidate must score much lower than high-S candidate
        when both are in the same candidate set."""
        crs = _make_crs_scorer()

        # 4 candidates: bad (high C+R, low S) vs good (mod C+R, high S)
        C_raw = torch.tensor([1.5, 0.5, 0.5, 0.3])
        R_raw = torch.tensor([1.8, 0.3, 0.3, 0.2])
        S_raw = torch.tensor([-0.5, 1.5, 0.5, -1.0])  # bad, good, ok, terrible

        result = crs.combine_crs(C_raw, R_raw, S_raw)
        crs_score = result['crs_score']

        bad_score = crs_score[0].item()   # high C+R, low S
        good_score = crs_score[1].item()  # mod C+R, high S

        # Good (high S) must beat bad (low S) despite bad having better C+R
        assert good_score > bad_score, (
            f"Semantic authority failed: good={good_score:.4f} should be > bad={bad_score:.4f}"
        )


# ---------------------------------------------------------------
# Test 3: Flag-off compatibility
# ---------------------------------------------------------------

class TestFlagOffCompatibility:
    """With CRS disabled, TokenPrimitiveCache and TET must work as before."""

    def test_cache_without_crs(self):
        projector = TokenOntologyProjector(embed_dim=EMBED_DIM, state_dim=STATE_DIM)
        cache = TokenPrimitiveCache(
            projector=projector,
            vocab_size=VOCAB_SIZE,
            state_dim=STATE_DIM,
            semantic_dim=0,  # CRS disabled
        )
        # S_tok should exist but be (V, 0)
        assert hasattr(cache, 'S_tok')
        assert cache.S_tok.shape == (VOCAB_SIZE, 0)
        assert cache.semantic_dim == 0

    def test_cache_refresh_without_semantic_scorer(self):
        projector = TokenOntologyProjector(embed_dim=EMBED_DIM, state_dim=STATE_DIM)
        cache = TokenPrimitiveCache(
            projector=projector,
            vocab_size=VOCAB_SIZE,
            state_dim=STATE_DIM,
            semantic_dim=0,
        )
        # Refresh should work without semantic scorer
        fake_embeddings = torch.randn(VOCAB_SIZE, EMBED_DIM)
        cache.refresh(fake_embeddings)
        assert cache._is_initialized


# ---------------------------------------------------------------
# Test 4: Cache refresh with CRS
# ---------------------------------------------------------------

class TestCacheRefreshCRS:
    """S_tok should be populated when CRS is enabled."""

    def test_s_tok_populated(self):
        csr = _make_csr_scorer()
        crs = _make_crs_scorer(csr)

        projector = TokenOntologyProjector(embed_dim=EMBED_DIM, state_dim=STATE_DIM)
        cache = TokenPrimitiveCache(
            projector=projector,
            vocab_size=VOCAB_SIZE,
            state_dim=STATE_DIM,
            semantic_dim=16,
        )
        cache.set_scorers(semantic_scorer=crs)

        fake_embeddings = torch.randn(VOCAB_SIZE, EMBED_DIM)
        cache.refresh(fake_embeddings)

        # S_tok should be non-zero after refresh
        assert cache.S_tok.shape == (VOCAB_SIZE, 16)
        assert cache.S_tok.abs().sum().item() > 0, "S_tok should be non-zero after refresh"


# ---------------------------------------------------------------
# Test 5: Top-1 divergence
# ---------------------------------------------------------------

class TestTop1Divergence:
    """Semantic gating should change top-1 ranking vs pure R."""

    def test_semantic_gating_changes_ranking(self):
        crs = _make_crs_scorer()

        # 4 candidates: candidate 0 has best R but worst S
        C_raw = torch.tensor([[0.5, 0.5, 0.5, 0.5]])
        R_raw = torch.tensor([[2.0, 0.5, 0.3, 0.1]])  # candidate 0 dominates R
        S_raw = torch.tensor([[-2.0, 1.0, 1.2, 0.8]])  # candidate 0 has terrible S

        result = crs.combine_crs(C_raw, R_raw, S_raw)
        crs_score = result['crs_score']

        # Pure R would pick candidate 0 (R=2.0)
        r_top1 = R_raw.argmax(dim=-1).item()
        assert r_top1 == 0

        # CRS should NOT pick candidate 0 (S is terrible)
        crs_top1 = crs_score.argmax(dim=-1).item()
        assert crs_top1 != 0, (
            f"Semantic gating failed: CRS still picked candidate 0 "
            f"(scores: {crs_score.tolist()})"
        )


# ---------------------------------------------------------------
# Test: Full forward pass
# ---------------------------------------------------------------

class TestForwardPass:
    """CRSCombinedScorer.forward() produces correct output shape and keys."""

    def test_forward_shapes(self):
        crs = _make_crs_scorer()
        inputs = _make_forward_inputs()
        result = crs(**inputs)

        assert 'crs_score' in result
        assert 'C' in result
        assert 'R' in result
        assert 'S' in result
        assert 'S_prob' in result
        assert 'S_gate' in result

        B, T = 2, 4
        assert result['crs_score'].shape == (B, T, K)
        assert result['C'].shape == (B, T, K)
        assert result['R'].shape == (B, T, K)
        assert result['S'].shape == (B, T, K)
        assert result['S_prob'].shape == (B, T, K)
        assert result['S_gate'].shape == (B, T, K)

    def test_gradients_flow(self):
        """Verify gradients flow through all three branches."""
        crs = _make_crs_scorer()
        inputs = _make_forward_inputs()
        # Make inputs require grad
        for k, v in inputs.items():
            if v.is_floating_point():
                inputs[k] = v.requires_grad_(True)

        result = crs(**inputs)
        loss = result['crs_score'].sum()
        loss.backward()

        # Check that CRS parameters received gradients
        assert crs.A_C.grad is not None, "C bilinear should have gradient"
        assert crs.A_S.grad is not None, "S bilinear should have gradient"
        # R delegates to csr_scorer — check its params
        assert crs.csr_scorer.A.grad is not None, "R (CSR) bilinear should have gradient"
