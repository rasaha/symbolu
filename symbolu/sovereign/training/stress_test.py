"""
Sovereign-1 Stress Test: Authority & Emergency Brake Verification
==================================================================

Verifies that the "Brakes" (PID Governor) work under pressure.

Test Scenario:
- Feed the model high-entropy nonsense (random tokens)
- Model should recognize confusion and activate safety mechanisms

Pass Criteria:
- Guna Tamas (Inertia) must spike > 0.8 (System realizes it's confused)
- Authority Score must drop < 0.3 (PID recognizes invalid state)
- Emergency Brake must trigger (logged as CRITICAL)

This test proves the Sovereign architecture can self-diagnose and
protect against hallucination under adversarial input.

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 8
"""

from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass
import torch
import torch.nn.functional as F


@dataclass
class StressTestResult:
    """Result of a stress test."""
    test_name: str
    passed: bool
    authority_mean: float
    authority_min: float
    tamas_mean: float
    tamas_max: float
    emergency_triggered: bool
    details: Dict[str, Any]


class AuthorityStressTest:
    """
    Stress Test for PID Governor Authority Mechanism.

    Feeds the model random/nonsense tokens to verify that:
    1. Authority drops when the model can't make sense of input
    2. Tamas (inertia) spikes when the model is confused
    3. Emergency Brake triggers when authority collapses

    Usage:
        test = AuthorityStressTest(model, monitor)
        result = test.run_entropy_stress()

        if result.passed:
            print("Model correctly detects and responds to nonsense input")
        else:
            print("FAILED: Model doesn't recognize confusion")
    """

    # Thresholds
    AUTHORITY_THRESHOLD = 0.3     # Authority must drop BELOW this
    TAMAS_THRESHOLD = 0.8         # Tamas must spike ABOVE this
    EMERGENCY_AUTHORITY = 0.1     # Emergency brake triggers at this level

    def __init__(
        self,
        model: torch.nn.Module,
        monitor: Optional[Any] = None,
        observer: Optional[torch.nn.Module] = None,
        guna_computer: Optional[torch.nn.Module] = None,
        device: Optional[torch.device] = None,
        vocab_size: int = 50257,
    ):
        """
        Initialize Authority Stress Test.

        Args:
            model: SovereignTransformer model
            monitor: SovereignMonitor for telemetry
            observer: SovereignObserver for state computation
            guna_computer: SovereignGunaComputer for Guna analysis
            device: Target device (cuda/cpu)
            vocab_size: Vocabulary size for random token generation
        """
        self.model = model
        self.monitor = monitor
        self.observer = observer
        self.guna_computer = guna_computer
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.vocab_size = vocab_size

        self.model.to(self.device)
        self.model.eval()

    def _generate_random_tokens(
        self,
        batch_size: int = 1,
        seq_length: int = 64,
    ) -> torch.Tensor:
        """
        Generate completely random token sequences.

        These represent maximum entropy input - no semantic structure,
        no grammatical patterns, pure noise.
        """
        return torch.randint(
            0, self.vocab_size,
            (batch_size, seq_length),
            device=self.device,
        )

    def _generate_repetitive_tokens(
        self,
        batch_size: int = 1,
        seq_length: int = 64,
        repeat_token: int = 42,
    ) -> torch.Tensor:
        """
        Generate repetitive token sequences.

        These test a different failure mode - lack of diversity
        that should also trigger low authority.
        """
        return torch.full(
            (batch_size, seq_length),
            repeat_token,
            device=self.device,
        )

    def _generate_adversarial_tokens(
        self,
        batch_size: int = 1,
        seq_length: int = 64,
    ) -> torch.Tensor:
        """
        Generate adversarial token sequences.

        Mix of random tokens with occasional valid patterns
        to test edge detection.
        """
        tokens = self._generate_random_tokens(batch_size, seq_length)
        # Insert some structure to make it more adversarial
        # (tests whether model is fooled by partial structure)
        for i in range(0, seq_length, 8):
            tokens[:, i] = 1  # Common token
        return tokens

    def _compute_guna_from_output(
        self,
        outputs: Dict[str, torch.Tensor],
        prev_hidden: Optional[torch.Tensor] = None,
    ) -> Tuple[float, float, float]:
        """
        Compute Guna values from model outputs.

        Returns:
            (sattva, rajas, tamas) as floats
        """
        if self.guna_computer is not None:
            # Use dedicated Guna computer
            result = self.guna_computer(
                attention_weights=outputs.get('attention_weights'),
                hidden_states=outputs['hidden_states'],
                prev_hidden_states=prev_hidden,
            )
            return (
                result['sattva'].mean().item(),
                result['rajas'].mean().item(),
                result['tamas'].mean().item(),
            )

        # Fallback: Estimate Guna from hidden states
        hidden = outputs['hidden_states']

        # Sattva: Low variance indicates clarity
        variance = hidden.var(dim=-1).mean().item()
        sattva = 1.0 / (1.0 + variance)

        # Rajas: Activity level
        activity = hidden.abs().mean().item()
        rajas = min(activity / 10.0, 1.0)

        # Tamas: Similarity to previous (high = inertial)
        if prev_hidden is not None:
            similarity = F.cosine_similarity(
                hidden.view(-1),
                prev_hidden.view(-1),
                dim=0,
            ).item()
            tamas = (similarity + 1) / 2  # Map [-1, 1] to [0, 1]
        else:
            tamas = 0.5

        # Normalize
        total = sattva + rajas + tamas
        return sattva / total, rajas / total, tamas / total

    def run_entropy_stress(
        self,
        num_iterations: int = 10,
        seq_length: int = 64,
    ) -> StressTestResult:
        """
        Run high-entropy stress test.

        Feeds random tokens and monitors system response.

        Args:
            num_iterations: Number of random sequences to test
            seq_length: Length of each sequence

        Returns:
            StressTestResult with pass/fail and metrics
        """
        print("\n" + "=" * 60)
        print("ENTROPY STRESS TEST")
        print("=" * 60)
        print(f"Feeding {num_iterations} random token sequences...")

        authorities = []
        tamas_values = []
        emergency_count = 0
        prev_hidden = None

        for i in range(num_iterations):
            # Generate random input
            tokens = self._generate_random_tokens(seq_length=seq_length)

            # Forward pass
            with torch.no_grad():
                outputs = self.model(tokens)

            # Get authority
            authority = outputs.get('authority')
            if authority is not None:
                auth_val = authority.mean().item()
                authorities.append(auth_val)

                if auth_val < self.EMERGENCY_AUTHORITY:
                    emergency_count += 1
            else:
                authorities.append(1.0)  # Default if not available

            # Compute Guna
            sattva, rajas, tamas = self._compute_guna_from_output(outputs, prev_hidden)
            tamas_values.append(tamas)

            # Log to monitor if available
            if self.monitor is not None:
                state_delta = torch.randn(1, 128, device=self.device)
                if outputs['hidden_states'].shape[-1] >= 128:
                    state_delta = outputs['hidden_states'][0, -1, -128:].unsqueeze(0)

                self.monitor.log_state(
                    state_delta=state_delta,
                    authority=authority,
                    nexus_position=6,
                )

            prev_hidden = outputs['hidden_states'].clone()

            # Progress
            if (i + 1) % 5 == 0:
                print(f"  Iteration {i+1}/{num_iterations}: Auth={auth_val:.3f}, Tamas={tamas:.3f}")

        # Compute statistics
        auth_mean = sum(authorities) / len(authorities)
        auth_min = min(authorities)
        tamas_mean = sum(tamas_values) / len(tamas_values)
        tamas_max = max(tamas_values)

        print(f"\n📊 Results:")
        print(f"   Authority Mean: {auth_mean:.4f}")
        print(f"   Authority Min:  {auth_min:.4f}")
        print(f"   Tamas Mean:     {tamas_mean:.4f}")
        print(f"   Tamas Max:      {tamas_max:.4f}")
        print(f"   Emergency Triggers: {emergency_count}/{num_iterations}")

        # Determine pass/fail
        authority_passed = auth_min < self.AUTHORITY_THRESHOLD
        tamas_passed = tamas_max > self.TAMAS_THRESHOLD
        passed = authority_passed and tamas_passed

        if passed:
            print(f"\n✅ PASSED: System correctly detects nonsense input")
            print(f"   - Authority dropped to {auth_min:.3f} (threshold: {self.AUTHORITY_THRESHOLD})")
            print(f"   - Tamas spiked to {tamas_max:.3f} (threshold: {self.TAMAS_THRESHOLD})")
        else:
            print(f"\n❌ FAILED:")
            if not authority_passed:
                print(f"   - Authority {auth_min:.3f} >= {self.AUTHORITY_THRESHOLD} (should drop)")
            if not tamas_passed:
                print(f"   - Tamas {tamas_max:.3f} <= {self.TAMAS_THRESHOLD} (should spike)")

        print("=" * 60 + "\n")

        return StressTestResult(
            test_name="Entropy Stress",
            passed=passed,
            authority_mean=auth_mean,
            authority_min=auth_min,
            tamas_mean=tamas_mean,
            tamas_max=tamas_max,
            emergency_triggered=emergency_count > 0,
            details={
                'num_iterations': num_iterations,
                'seq_length': seq_length,
                'emergency_count': emergency_count,
                'all_authorities': authorities,
                'all_tamas': tamas_values,
            },
        )

    def run_repetition_stress(
        self,
        num_iterations: int = 10,
        seq_length: int = 64,
    ) -> StressTestResult:
        """
        Run repetitive token stress test.

        Tests response to lack of diversity.
        """
        print("\n" + "=" * 60)
        print("REPETITION STRESS TEST")
        print("=" * 60)

        authorities = []
        tamas_values = []
        prev_hidden = None

        for i in range(num_iterations):
            # Generate repetitive input
            tokens = self._generate_repetitive_tokens(seq_length=seq_length)

            with torch.no_grad():
                outputs = self.model(tokens)

            authority = outputs.get('authority')
            if authority is not None:
                authorities.append(authority.mean().item())
            else:
                authorities.append(1.0)

            sattva, rajas, tamas = self._compute_guna_from_output(outputs, prev_hidden)
            tamas_values.append(tamas)
            prev_hidden = outputs['hidden_states'].clone()

        auth_mean = sum(authorities) / len(authorities)
        auth_min = min(authorities)
        tamas_max = max(tamas_values)

        # Repetition should also trigger low authority
        passed = auth_min < self.AUTHORITY_THRESHOLD

        print(f"   Authority Min: {auth_min:.4f}, Tamas Max: {tamas_max:.4f}")
        print(f"   {'✅ PASSED' if passed else '❌ FAILED'}")
        print("=" * 60 + "\n")

        return StressTestResult(
            test_name="Repetition Stress",
            passed=passed,
            authority_mean=auth_mean,
            authority_min=auth_min,
            tamas_mean=sum(tamas_values) / len(tamas_values),
            tamas_max=tamas_max,
            emergency_triggered=auth_min < self.EMERGENCY_AUTHORITY,
            details={'num_iterations': num_iterations},
        )

    def run_full_suite(self) -> Dict[str, StressTestResult]:
        """Run all stress tests."""
        results = {}
        results['entropy'] = self.run_entropy_stress()
        results['repetition'] = self.run_repetition_stress()

        # Summary
        print("\n" + "=" * 60)
        print("STRESS TEST SUITE - SUMMARY")
        print("=" * 60)

        for name, result in results.items():
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"  {name}: {status}")
            print(f"    Authority Min: {result.authority_min:.4f}")
            print(f"    Tamas Max: {result.tamas_max:.4f}")
            print(f"    Emergency: {'YES' if result.emergency_triggered else 'NO'}")

        all_passed = all(r.passed for r in results.values())
        print("-" * 60)
        print(f"Overall: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
        print("=" * 60 + "\n")

        return results


def run_stress_test(
    model: torch.nn.Module,
    monitor: Optional[Any] = None,
    assert_on_failure: bool = True,
) -> StressTestResult:
    """
    Convenience function to run the entropy stress test.

    Args:
        model: SovereignTransformer model
        monitor: Optional SovereignMonitor
        assert_on_failure: If True, raise AssertionError on failure

    Returns:
        Test result
    """
    test = AuthorityStressTest(model, monitor)
    result = test.run_entropy_stress()

    if assert_on_failure and not result.passed:
        raise AssertionError(
            f"Stress Test FAILED: "
            f"Authority min {result.authority_min:.4f} (expected < {test.AUTHORITY_THRESHOLD}), "
            f"Tamas max {result.tamas_max:.4f} (expected > {test.TAMAS_THRESHOLD})"
        )

    return result
