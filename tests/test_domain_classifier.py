"""
Unit tests for DomainClassifier (Phase 5 MVP).

Tests:
  1. Forward shape — outputs correct shapes
  2. Softmax sums to 1
  3. Flag-off preserves old behavior (no domain_classifier in modules)
  4. Flag-on emits 8D distribution
  5. Loss computation with soft targets
  6. Loss computation with hard targets
"""

import torch
import torch.nn as nn

from symbolu_training.training.conscious_generation.governance.domain_classifier import (
    DomainClassifier,
    NUM_DOMAINS,
    DOMAIN_NAMES,
)


EMBED_DIM = 64
STATE_DIM = 32
BATCH = 4
SEQ = 8


def _make_classifier(**kwargs):
    defaults = dict(embed_dim=EMBED_DIM, state_dim=STATE_DIM)
    defaults.update(kwargs)
    return DomainClassifier(**defaults)


class TestForwardShape:
    """DomainClassifier forward produces correct shapes and keys."""

    def test_output_keys(self):
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        o = torch.randn(BATCH, STATE_DIM)
        result = dc(h, o)
        assert 'domain' in result
        assert 'logits' in result
        assert 'entropy' in result

    def test_domain_shape(self):
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        o = torch.randn(BATCH, STATE_DIM)
        result = dc(h, o)
        assert result['domain'].shape == (BATCH, NUM_DOMAINS)
        assert result['logits'].shape == (BATCH, NUM_DOMAINS)
        assert result['entropy'].shape == (BATCH,)

    def test_2d_hidden(self):
        """Accept pre-pooled 2D hidden states."""
        dc = _make_classifier()
        h = torch.randn(BATCH, EMBED_DIM)  # already pooled
        o = torch.randn(BATCH, STATE_DIM)
        result = dc(h, o)
        assert result['domain'].shape == (BATCH, NUM_DOMAINS)

    def test_no_sovereign_state(self):
        """Works without sovereign state (zeros used)."""
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        result = dc(h, o_ctx=None)
        assert result['domain'].shape == (BATCH, NUM_DOMAINS)

    def test_zero_state_dim(self):
        """Classifier with state_dim=0 ignores sovereign state."""
        dc = _make_classifier(state_dim=0)
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        result = dc(h)
        assert result['domain'].shape == (BATCH, NUM_DOMAINS)


class TestSoftmax:
    """Domain distribution sums to 1."""

    def test_sums_to_one(self):
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        o = torch.randn(BATCH, STATE_DIM)
        result = dc(h, o)
        sums = result['domain'].sum(dim=-1)
        assert torch.allclose(sums, torch.ones(BATCH), atol=1e-5), \
            f"Domain distribution should sum to 1, got {sums}"

    def test_all_positive(self):
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        result = dc(h)
        assert (result['domain'] >= 0).all(), "Domain probs should be non-negative"


class TestLoss:
    """Domain classification loss computation."""

    def test_soft_target_loss(self):
        dc = _make_classifier()
        logits = torch.randn(BATCH, NUM_DOMAINS)
        # Soft target: uniform distribution
        target = torch.ones(BATCH, NUM_DOMAINS) / NUM_DOMAINS
        loss = dc.compute_loss(logits, target, soft_target=True)
        assert loss.shape == (), f"Loss should be scalar, got {loss.shape}"
        assert loss.item() >= 0, "KL loss should be non-negative"
        assert torch.isfinite(loss), "Loss should be finite"

    def test_hard_target_loss(self):
        dc = _make_classifier()
        logits = torch.randn(BATCH, NUM_DOMAINS)
        target = torch.randint(0, NUM_DOMAINS, (BATCH,))
        loss = dc.compute_loss(logits, target, soft_target=False)
        assert loss.shape == ()
        assert loss.item() >= 0
        assert torch.isfinite(loss)

    def test_gradients_flow(self):
        dc = _make_classifier()
        h = torch.randn(BATCH, SEQ, EMBED_DIM)
        o = torch.randn(BATCH, STATE_DIM)
        result = dc(h, o)
        target = torch.ones(BATCH, NUM_DOMAINS) / NUM_DOMAINS
        loss = dc.compute_loss(result['logits'], target, soft_target=True)
        loss.backward()
        # Check classifier parameters got gradients
        has_grad = any(p.grad is not None and p.grad.abs().sum() > 0
                      for p in dc.parameters())
        assert has_grad, "Classifier should receive gradients"


class TestDomainNames:
    """Domain taxonomy is correct."""

    def test_eight_domains(self):
        assert NUM_DOMAINS == 8
        assert len(DOMAIN_NAMES) == 8

    def test_expected_names(self):
        expected = ["code", "math", "factual", "chat",
                   "emotional", "narrative", "planning", "retrieval"]
        assert DOMAIN_NAMES == expected
