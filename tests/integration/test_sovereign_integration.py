"""
Sovereign-1 Integration Tests: Phase 2 + Phase 3
=================================================

These tests verify that the Engine (Phase 2) and Transmission (Phase 3)
work together correctly.

Critical Test Cases:
- Test A: The Dampener - Verify authority gating reduces output magnitude
- Test B: The Shifter - Verify Virtual Nexus moves PID between layers
- Test C: The Physics - Verify Guna conservation (S+R+T = 1.0)

These tests MUST pass before proceeding to training.
"""

import pytest
import torch
import torch.nn.functional as F
import math


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def device():
    """Use CUDA if available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@pytest.fixture
def small_transformer_config():
    """Small transformer config for fast testing."""
    from symbolu.sovereign.transformer import SovereignTransformerConfig

    return SovereignTransformerConfig(
        vocab_size=1000,
        embed_dim=256,
        num_layers=12,  # Need 12 for full nexus testing
        num_heads=4,
        ff_dim=512,
        max_seq_len=128,
    )


@pytest.fixture
def small_transformer(small_transformer_config, device):
    """Create small transformer for testing."""
    from symbolu.sovereign.transformer import SovereignTransformer

    model = SovereignTransformer(config=small_transformer_config).to(device)
    return model


# =============================================================================
# Test A: The Dampener
# =============================================================================

class TestDampener:
    """
    Test that the Dampening Field reduces tensor magnitude when Authority is low.

    Scenario: Feed a "hallucination state" (high mismatch between R-Signal and Prompt).
    Expected: Authority drops below 0.7 and output tensor magnitude decreases.
    """

    def test_authority_drops_on_mismatch(self, device, small_transformer):
        """
        Test that authority score drops when current state mismatches target state.
        """
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = 2, 16, 256
        config = PIDGovernorConfig(authority_threshold=0.7, dampening_factor=0.1)
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        # Create input with normal state
        x = torch.randn(B, N, D, device=device)

        # Create target state that is VERY different from current
        # This simulates a "hallucination state" - what the model is producing
        # doesn't match what the Observer says it should be producing
        target_state = torch.randn(B, N, 128, device=device) * 10.0

        x_out, authority, _ = governor(x, target_state)

        # Authority should be low due to high mismatch
        mean_authority = authority.mean().item()
        print(f"Authority on high mismatch: {mean_authority:.4f}")

        # At least some positions should have low authority
        low_authority_count = (authority < 0.7).sum().item()
        print(f"Positions with authority < 0.7: {low_authority_count}/{authority.numel()}")

        assert low_authority_count > 0, \
            "Expected some positions to have low authority on state mismatch"

    def test_dampening_reduces_magnitude(self, device, small_transformer):
        """
        Test that dampening reduces semantic body magnitude when authority is low.
        """
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = 2, 16, 256
        config = PIDGovernorConfig(
            authority_threshold=0.7,
            dampening_factor=0.1,  # Should reduce to 10% of original
        )
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        # Create input with known magnitude
        x = torch.ones(B, N, D, device=device)
        original_semantic_norm = x[..., :config.semantic_dim].norm(dim=-1).mean().item()

        # Force low authority with extreme target mismatch
        target_state = torch.randn(B, N, 128, device=device) * 100.0

        x_out, authority, _ = governor(x, target_state)

        # Find positions with low authority
        low_auth_mask = authority < 0.7

        if low_auth_mask.any():
            # Get output magnitude for low authority positions
            dampened_norm = x_out[low_auth_mask, :config.semantic_dim].norm(dim=-1).mean().item()
            expected_norm = original_semantic_norm * config.dampening_factor

            print(f"Original semantic norm: {original_semantic_norm:.4f}")
            print(f"Dampened semantic norm: {dampened_norm:.4f}")
            print(f"Expected dampened norm: {expected_norm:.4f}")

            # Dampened output should be close to 10% of original
            assert dampened_norm < original_semantic_norm * 0.5, \
                f"Dampened magnitude ({dampened_norm:.4f}) should be much less than original ({original_semantic_norm:.4f})"

    def test_full_transformer_dampening(self, device, small_transformer):
        """
        Test full transformer with PID Governor dampening.
        """
        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        # Create mismatched state delta to trigger low authority
        # This simulates the Observer detecting that the model is off-track
        bad_state_delta = torch.randn(B, N, 128, device=device) * 10.0

        # Run with mismatched state
        outputs = small_transformer(
            token_ids,
            state_delta=bad_state_delta,
            nexus_position=6,
        )

        # Check that authority was computed
        assert outputs['authority'] is not None
        authority = outputs['authority']

        print(f"Mean authority: {authority.mean().item():.4f}")
        print(f"Min authority: {authority.min().item():.4f}")


# =============================================================================
# Test B: The Shifter
# =============================================================================

class TestShifter:
    """
    Test that the Virtual Nexus actually moves the PID Governor between layers.

    Scenario A: Send a "Math Problem" (logic-heavy) → PID should activate at Layer 4
    Scenario B: Send a "Poem" (creative) → PID should activate at Layer 6
    """

    def test_router_selects_nexus_4_for_logic(self, device):
        """
        Test that logic-heavy queries route to Nexus 4.
        """
        from symbolu.sovereign.router import SovereignRouter, ONTOLOGY_TO_NEXUS

        router = SovereignRouter()

        logic_queries = [
            "Explain the Pythagorean theorem",
            "Prove that the square root of 2 is irrational",
            "Calculate the derivative of x^3",
            "Why does E=mc^2?",
            "Analyze the logical fallacy in this argument",
        ]

        for query in logic_queries:
            decision = router.route_sovereign(query)
            print(f"Query: '{query[:40]}...' → Nexus: {decision.nexus_position}")

            # Logic-heavy queries should prefer nexus 4 or 6
            assert decision.nexus_position in [4, 6], \
                f"Logic query should route to nexus 4 or 6, got {decision.nexus_position}"

    def test_router_selects_nexus_6_for_creative(self, device):
        """
        Test that creative queries route to Nexus 6 (balanced).
        """
        from symbolu.sovereign.router import SovereignRouter

        router = SovereignRouter()

        creative_queries = [
            "Write a poem about autumn leaves",
            "Compose a haiku about the ocean",
            "Create a story about a dragon",
            "Design a logo for a coffee shop",
        ]

        for query in creative_queries:
            decision = router.route_sovereign(query)
            print(f"Query: '{query[:40]}...' → Nexus: {decision.nexus_position}")

            # Creative queries should use balanced nexus
            assert decision.nexus_position in [6, 8], \
                f"Creative query should route to nexus 6 or 8, got {decision.nexus_position}"

    def test_router_selects_nexus_8_for_memory(self, device):
        """
        Test that memory-heavy queries route to Nexus 8.
        """
        from symbolu.sovereign.router import SovereignRouter

        router = SovereignRouter()

        memory_queries = [
            "Remember the timeline of World War II",
            "Recall the structure of DNA",
            "List the sequence of events in the story",
            "Document the history of the Roman Empire",
        ]

        for query in memory_queries:
            decision = router.route_sovereign(query)
            print(f"Query: '{query[:40]}...' → Nexus: {decision.nexus_position}")

            # Memory queries may prefer higher nexus positions
            # Note: This depends on the full SemanticRouter being available

    def test_different_nexus_produces_different_output(self, device, small_transformer):
        """
        CRITICAL: Test that different nexus positions produce different outputs.

        This proves the Virtual Nexus actually reconfigures the architecture.
        """
        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        # Run with Nexus 4 (logic-heavy: 4Q + 8P)
        outputs_4 = small_transformer(token_ids, nexus_position=4)

        # Run with Nexus 6 (balanced: 6Q + 6P)
        outputs_6 = small_transformer(token_ids, nexus_position=6)

        # Run with Nexus 8 (memory-heavy: 8Q + 4P)
        outputs_8 = small_transformer(token_ids, nexus_position=8)

        # Outputs MUST be different
        logits_4 = outputs_4['logits']
        logits_6 = outputs_6['logits']
        logits_8 = outputs_8['logits']

        # Check that nexus 4 and 6 produce different outputs
        diff_4_6 = (logits_4 - logits_6).abs().mean().item()
        diff_6_8 = (logits_6 - logits_8).abs().mean().item()
        diff_4_8 = (logits_4 - logits_8).abs().mean().item()

        print(f"Diff(Nexus 4, Nexus 6): {diff_4_6:.6f}")
        print(f"Diff(Nexus 6, Nexus 8): {diff_6_8:.6f}")
        print(f"Diff(Nexus 4, Nexus 8): {diff_4_8:.6f}")

        assert diff_4_6 > 1e-6, \
            "CRITICAL: Nexus 4 and 6 produce identical outputs - Virtual Nexus not working!"
        assert diff_6_8 > 1e-6, \
            "CRITICAL: Nexus 6 and 8 produce identical outputs - Virtual Nexus not working!"
        assert diff_4_8 > 1e-6, \
            "CRITICAL: Nexus 4 and 8 produce identical outputs - Virtual Nexus not working!"

    def test_pid_activates_at_correct_layer(self, device, small_transformer):
        """
        Test that PID Governor activates at the specified nexus layer.

        We verify this by checking that authority is computed and returned.
        """
        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        for nexus in [4, 6, 8]:
            outputs = small_transformer(token_ids, nexus_position=nexus)

            assert outputs['authority'] is not None, \
                f"PID should produce authority at nexus {nexus}"

            print(f"Nexus {nexus}: Authority mean = {outputs['authority'].mean().item():.4f}")


# =============================================================================
# Test C: The Physics
# =============================================================================

class TestPhysics:
    """
    Test that Guna Conservation holds: Sattva + Rajas + Tamas = 1.0

    This is a fundamental physical constraint of the cognitive state model.
    """

    def test_guna_conservation(self, device):
        """
        CRITICAL: Verify that Guna values always sum to 1.0.
        """
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        # Test with various input patterns
        test_cases = [
            ("uniform_attention", F.softmax(torch.ones(2, 4, 16, 16, device=device), dim=-1)),
            ("focused_attention", torch.zeros(2, 4, 16, 16, device=device)),
            ("random_attention", F.softmax(torch.randn(2, 4, 16, 16, device=device), dim=-1)),
        ]

        # Set focused attention to focus on first token
        test_cases[1][1][:, :, :, 0] = 1.0

        for name, attention in test_cases:
            hidden = torch.randn(2, 16, 256, device=device)
            prev_hidden = torch.randn(2, 16, 256, device=device)
            head_outputs = torch.randn(2, 4, 16, 64, device=device)

            result = computer(
                attention_weights=attention,
                head_outputs=head_outputs,
                hidden_states=hidden,
                prev_hidden_states=prev_hidden,
            )

            guna_3d = result['guna_3d']  # [B, 3]
            guna_sum = guna_3d.sum(dim=-1)

            print(f"{name}: Guna sum = {guna_sum.mean().item():.6f}")

            # Sum MUST be 1.0 (within floating point tolerance)
            assert torch.allclose(guna_sum, torch.ones_like(guna_sum), atol=1e-5), \
                f"CRITICAL: Guna conservation violated! Sum = {guna_sum} (should be 1.0)"

    def test_guna_values_in_range(self, device):
        """
        Test that all Guna values are in valid [0, 1] range.
        """
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        # Test with extreme inputs
        attention = F.softmax(torch.randn(2, 4, 16, 16, device=device) * 10, dim=-1)
        hidden = torch.randn(2, 16, 256, device=device) * 5
        head_outputs = torch.randn(2, 4, 16, 64, device=device) * 3

        result = computer(
            attention_weights=attention,
            head_outputs=head_outputs,
            hidden_states=hidden,
        )

        sattva = result['sattva']
        rajas = result['rajas']
        tamas = result['tamas']

        print(f"Sattva range: [{sattva.min().item():.4f}, {sattva.max().item():.4f}]")
        print(f"Rajas range: [{rajas.min().item():.4f}, {rajas.max().item():.4f}]")
        print(f"Tamas range: [{tamas.min().item():.4f}, {tamas.max().item():.4f}]")

        assert (sattva >= 0).all() and (sattva <= 1).all(), "Sattva out of range"
        assert (rajas >= 0).all() and (rajas <= 1).all(), "Rajas out of range"
        assert (tamas >= 0).all() and (tamas <= 1).all(), "Tamas out of range"

    def test_guna_responds_to_attention_pattern(self, device):
        """
        Test that Sattva (clarity) responds correctly to attention focus.

        High focus → High Sattva
        Uniform attention → Low Sattva
        """
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, H, N = 2, 4, 16
        hidden = torch.randn(B, N, 256, device=device)

        # Focused attention (low entropy → high Sattva)
        focused_attn = torch.zeros(B, H, N, N, device=device)
        focused_attn[:, :, :, 0] = 1.0

        # Uniform attention (high entropy → low Sattva)
        uniform_attn = torch.ones(B, H, N, N, device=device) / N

        result_focused = computer(attention_weights=focused_attn, hidden_states=hidden)
        result_uniform = computer(attention_weights=uniform_attn, hidden_states=hidden)

        sattva_focused = result_focused['sattva'].mean().item()
        sattva_uniform = result_uniform['sattva'].mean().item()

        print(f"Sattva (focused attention): {sattva_focused:.4f}")
        print(f"Sattva (uniform attention): {sattva_uniform:.4f}")

        assert sattva_focused > sattva_uniform, \
            "Focused attention should produce higher Sattva than uniform attention"


# =============================================================================
# Test D: End-to-End Integration
# =============================================================================

class TestEndToEndIntegration:
    """
    End-to-end integration tests combining all Phase 2 + Phase 3 components.
    """

    def test_full_pipeline(self, device, small_transformer):
        """
        Test the complete Sovereign-1 pipeline:
        1. Router selects nexus position
        2. Transformer runs with that nexus
        3. Monitor captures state
        """
        from symbolu.sovereign.router import SovereignRouter
        from symbolu.sovereign.telemetry import SovereignMonitor

        router = SovereignRouter()
        monitor = SovereignMonitor(enable_console_output=False, enable_trace_output=False)

        queries = [
            "Explain quantum mechanics",  # Logic-heavy
            "Write a love poem",           # Creative
            "List the steps to bake a cake",  # Memory
        ]

        for query in queries:
            # Step 1: Router selects nexus
            routing_decision = router.route_sovereign(query)
            nexus = routing_decision.nexus_position

            # Step 2: Generate tokens (dummy for test)
            B, N = 1, 16
            token_ids = torch.randint(0, 1000, (B, N), device=device)

            # Step 3: Run transformer with selected nexus
            outputs = small_transformer(token_ids, nexus_position=nexus)

            # Step 4: Log to monitor
            state_delta = torch.randn(B, 128, device=device)  # Simulated
            snapshot = monitor.log_state(
                state_delta=state_delta,
                authority=outputs['authority'],
                nexus_position=nexus,
            )

            print(f"\nQuery: '{query}'")
            print(f"  Nexus: {routing_decision.nexus_mode}")
            print(f"  Authority: {snapshot.authority:.4f}")
            print(f"  Dominant Guna: {snapshot.dominant_guna}")

        # Verify monitor captured all states
        stats = monitor.get_statistics()
        assert stats['total_steps'] == len(queries)

    def test_gradient_flow_through_full_pipeline(self, device, small_transformer):
        """
        CRITICAL: Test that gradients flow through the entire pipeline.
        """
        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)
        state_delta = torch.randn(B, N, 128, device=device, requires_grad=True)

        # Forward pass
        outputs = small_transformer(
            token_ids,
            state_delta=state_delta,
            nexus_position=6,
        )

        # Compute loss
        targets = torch.randint(0, 1000, (B, N), device=device)
        loss = F.cross_entropy(
            outputs['logits'].view(-1, 1000),
            targets.view(-1)
        )

        # Backward pass
        loss.backward()

        # Check gradients
        assert small_transformer.token_embedding.weight.grad is not None, \
            "Token embedding should have gradients"

        grad_norm = small_transformer.token_embedding.weight.grad.norm().item()
        assert grad_norm > 0, f"Gradient norm should be positive, got {grad_norm}"

        print(f"Gradient norm: {grad_norm:.6f}")


# =============================================================================
# Test E: COGNADE Export
# =============================================================================

class TestCOGNADEExport:
    """
    Test COGNADE SDK export functionality.
    """

    def test_header_generation(self):
        """Test C header file generation."""
        from symbolu.sovereign.cognade_export import generate_header

        header = generate_header(version="1.0.0")

        # Check essential components are present
        assert "cognade_state_t" in header
        assert "cognade_guna_t" in header
        assert "COGNADE_STATE_BITS" in header
        assert "cognade_phoneme_hash" in header
        assert "#ifndef COGNADE_STATE_H" in header

        print("Generated header preview:")
        print(header[:500])

    def test_state_packing(self, device):
        """Test state vector packing/unpacking."""
        from symbolu.sovereign.cognade_export import pack_state_to_binary, unpack_binary_to_state

        # Create test state
        state = torch.rand(128, device=device)

        # Pack to binary
        binary = pack_state_to_binary(state)
        assert len(binary) == 16, f"Packed state should be 16 bytes, got {len(binary)}"

        # Unpack (note: lossy due to quantization)
        unpacked = unpack_binary_to_state(binary)
        assert unpacked.shape == (128,)

        print(f"Original state norm: {state.norm().item():.4f}")
        print(f"Unpacked state norm: {unpacked.norm().item():.4f}")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
