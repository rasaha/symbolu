#!/usr/bin/env python3
"""
Test script for Inverted Curriculum Evolution components (V9.9.1).

Tests:
1. PerLayerPhaseController - Per-layer phase weight management
2. InvertedLayerCurriculumController - Full curriculum orchestration

Usage:
    python scripts/test_inverted_curriculum.py
"""

import sys
from typing import Dict, List, Tuple, Optional

# Try to import torch, fall back to mock if not available
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# =============================================================================
# MOCK IMPLEMENTATIONS FOR TESTING
# =============================================================================

class MockParameter:
    """Mock nn.Parameter for environments without torch."""

    def __init__(self, value: float):
        self._value = value
        self.data = self

    def fill_(self, value: float):
        self._value = value

    def item(self) -> float:
        return self._value


class MockHybridAttentionLayer:
    """Mock HybridAttentionLayer for testing per-layer phase control."""

    def __init__(self, layer_idx: int = -1):
        self.layer_idx = layer_idx
        self.alpha_phase = MockParameter(0.5)
        self.alpha_local = MockParameter(0.5)


class MockHybridModel:
    """Mock model with 12 layers for testing."""

    def __init__(self, num_layers: int = 12):
        self.layers = [MockHybridAttentionLayer(layer_idx=i) for i in range(num_layers)]
        self._modules = {'layers': self.layers}

    def modules(self):
        """Yield all modules (layers) for iteration."""
        yield self
        for layer in self.layers:
            yield layer


# =============================================================================
# COPY OF CONTROLLER CLASSES FOR STANDALONE TESTING
# =============================================================================

class PerLayerPhaseController:
    """
    V9.9.1: Manages per-layer phase weights for fine-grained control.
    """

    def __init__(
        self,
        num_layers: int = 12,
        initial_weights: Optional[List[float]] = None,
        local_layers: int = 4,
    ):
        self.num_layers = num_layers
        self.local_layers = local_layers

        if initial_weights is not None:
            if len(initial_weights) != num_layers:
                raise ValueError(f"initial_weights must have {num_layers} elements, got {len(initial_weights)}")
            self.weights = list(initial_weights)
        else:
            self.weights = [0.0] * num_layers

        self.transitions = {}
        self.transition_history = []

    def _format_weights(self) -> str:
        hybrid_weights = self.weights[self.local_layers:]
        return "[" + ", ".join(f"{w:.2f}" for w in hybrid_weights) + "]"

    def get_weight(self, layer_idx: int) -> float:
        if layer_idx < 0 or layer_idx >= self.num_layers:
            return 0.0
        return self.weights[layer_idx]

    def set_weight(self, layer_idx: int, weight: float):
        if 0 <= layer_idx < self.num_layers:
            self.weights[layer_idx] = max(0.0, min(1.0, weight))

    def set_weights(self, weights: List[float]):
        if len(weights) != self.num_layers:
            raise ValueError(f"weights must have {self.num_layers} elements, got {len(weights)}")
        self.weights = [max(0.0, min(1.0, w)) for w in weights]

    def start_transition(
        self,
        layer_idx: int,
        target_weight: float,
        duration_steps: int,
        current_step: int,
    ):
        if layer_idx < self.local_layers:
            return

        current_weight = self.weights[layer_idx]
        self.transitions[layer_idx] = {
            'start_step': current_step,
            'end_step': current_step + duration_steps,
            'start_val': current_weight,
            'end_val': target_weight,
        }

    def update(self, current_step: int) -> Dict[str, any]:
        completed = []

        for layer_idx, trans in list(self.transitions.items()):
            start_step = trans['start_step']
            end_step = trans['end_step']
            start_val = trans['start_val']
            end_val = trans['end_val']

            if current_step >= end_step:
                self.weights[layer_idx] = end_val
                completed.append(layer_idx)
                self.transition_history.append({
                    'layer_idx': layer_idx,
                    'completed_step': current_step,
                    'final_weight': end_val,
                })
                del self.transitions[layer_idx]
            else:
                progress = (current_step - start_step) / (end_step - start_step)
                self.weights[layer_idx] = start_val + progress * (end_val - start_val)

        return {
            'weights': self.weights.copy(),
            'active_transitions': len(self.transitions),
            'completed': completed,
        }

    def apply_to_model(self, model):
        for module in model.modules():
            if hasattr(module, 'alpha_phase') and hasattr(module, 'layer_idx'):
                layer_idx = module.layer_idx
                if 0 <= layer_idx < self.num_layers:
                    weight = self.weights[layer_idx]
                    module.alpha_phase.data.fill_(weight)
                    if hasattr(module, 'alpha_local'):
                        module.alpha_local.data.fill_(1.0 - weight)

    def get_status(self) -> Dict[str, any]:
        authority_count = sum(1 for w in self.weights[self.local_layers:] if w >= 0.9)
        sensory_count = sum(1 for w in self.weights[self.local_layers:] if w <= 0.1)
        transitioning_count = len(self.weights[self.local_layers:]) - authority_count - sensory_count

        return {
            'weights': self.weights.copy(),
            'local_layers': self.local_layers,
            'authority_count': authority_count,
            'sensory_count': sensory_count,
            'transitioning_count': transitioning_count,
            'active_transitions': len(self.transitions),
            'completed_transitions': len(self.transition_history),
        }


class InvertedLayerCurriculumController:
    """
    V9.9.1: Orchestrates the full Inverted Layer Curriculum Evolution.
    """

    def __init__(
        self,
        stages: List[Tuple[Tuple[int, int], int]],
        ppl_triggers: List[float],
        local_layers: int = 4,
        transition_steps: int = 500,
    ):
        self.stages = stages
        self.ppl_triggers = ppl_triggers
        self.local_layers = local_layers
        self.transition_steps = transition_steps

        self.current_stage_idx = 0
        self.current_split = stages[0][0]
        self.current_seq_len = stages[0][1]

        initial_weights = self._split_to_weights(self.current_split)
        self.phase_controller = PerLayerPhaseController(
            num_layers=12,
            initial_weights=initial_weights,
            local_layers=local_layers,
        )

        self.ppl_history: List[float] = []
        self.ppl_window = 10
        self.stage_history: List[Dict] = []
        self.last_stage_change_step = 0

    def _split_to_weights(self, split: Tuple[int, int]) -> List[float]:
        authority_layers, sensory_layers = split
        weights = [0.0] * 12

        for i in range(12):
            if i < authority_layers:
                weights[i] = 1.0
            else:
                weights[i] = 0.0

        return weights

    def update(
        self,
        step: int,
        current_ppl: Optional[float] = None,
    ) -> Dict[str, any]:
        split_changed = False
        seq_len_changed = False
        old_split = self.current_split
        old_seq_len = self.current_seq_len

        if current_ppl is not None:
            self.ppl_history.append(current_ppl)
            if len(self.ppl_history) > self.ppl_window:
                self.ppl_history.pop(0)

        if self.current_stage_idx < len(self.stages) - 1 and current_ppl is not None:
            smoothed_ppl = sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else current_ppl
            next_trigger = self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else float('inf')

            if smoothed_ppl < next_trigger:
                self.current_stage_idx += 1
                new_split, new_seq_len = self.stages[self.current_stage_idx]

                if new_split != old_split:
                    split_changed = True
                    self._transition_to_split(new_split, step)

                if new_seq_len != old_seq_len:
                    seq_len_changed = True
                    self.current_seq_len = new_seq_len

                self.stage_history.append({
                    'stage': self.current_stage_idx,
                    'step': step,
                    'ppl': smoothed_ppl,
                    'split': new_split,
                    'seq_len': new_seq_len,
                })
                self.last_stage_change_step = step

        phase_result = self.phase_controller.update(step)

        return {
            'current_stage': self.current_stage_idx,
            'current_split': self.current_split,
            'current_seq_len': self.current_seq_len,
            'split_changed': split_changed,
            'seq_len_changed': seq_len_changed,
            'transitioning_layers': phase_result['active_transitions'],
            'layer_weights': phase_result['weights'],
        }

    def _transition_to_split(self, new_split: Tuple[int, int], step: int):
        old_auth, old_sens = self.current_split
        new_auth, new_sens = new_split

        if new_auth > old_auth:
            for layer_idx in range(old_auth, new_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=1.0,
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )
        else:
            for layer_idx in range(new_auth, old_auth):
                if layer_idx >= self.local_layers:
                    self.phase_controller.start_transition(
                        layer_idx=layer_idx,
                        target_weight=0.0,
                        duration_steps=self.transition_steps,
                        current_step=step,
                    )

        self.current_split = new_split

    def apply_to_model(self, model):
        self.phase_controller.apply_to_model(model)

    def get_status(self) -> Dict[str, any]:
        return {
            'stage': self.current_stage_idx,
            'total_stages': len(self.stages),
            'split': f"{self.current_split[0]}:{self.current_split[1]}",
            'seq_len': self.current_seq_len,
            'smoothed_ppl': sum(self.ppl_history) / len(self.ppl_history) if self.ppl_history else None,
            'next_trigger': self.ppl_triggers[self.current_stage_idx] if self.current_stage_idx < len(self.ppl_triggers) else None,
            'transitioning_layers': len(self.phase_controller.transitions),
            'layer_weights': self.phase_controller.weights[self.local_layers:],
        }


# =============================================================================
# TEST CASES
# =============================================================================

class TestResult:
    """Simple test result tracker."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name: str, passed: bool, message: str = ""):
        if passed:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.failures.append((name, message))
            print(f"  [FAIL] {name}: {message}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"RESULTS: {self.passed}/{total} tests passed")
        if self.failures:
            print(f"\nFailures:")
            for name, msg in self.failures:
                print(f"  - {name}: {msg}")
        print(f"{'='*70}")
        return self.failed == 0


def test_per_layer_phase_controller():
    """Test PerLayerPhaseController functionality."""
    print("\n" + "="*70)
    print("TEST: PerLayerPhaseController")
    print("="*70)

    results = TestResult()

    # Test 1: Initialization with defaults
    print("\n1. Testing initialization with defaults...")
    controller = PerLayerPhaseController(num_layers=12, local_layers=4)
    results.record(
        "Default initialization",
        controller.num_layers == 12 and controller.local_layers == 4,
        f"num_layers={controller.num_layers}, local_layers={controller.local_layers}"
    )
    results.record(
        "Default weights all zero",
        all(w == 0.0 for w in controller.weights),
        f"weights={controller.weights}"
    )

    # Test 2: Initialization with custom weights
    print("\n2. Testing initialization with custom weights...")
    custom_weights = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    controller = PerLayerPhaseController(num_layers=12, initial_weights=custom_weights, local_layers=4)
    results.record(
        "Custom weights initialization",
        controller.weights == custom_weights,
        f"weights={controller.weights}"
    )

    # Test 3: Invalid weights length
    print("\n3. Testing invalid weights length...")
    try:
        controller = PerLayerPhaseController(num_layers=12, initial_weights=[0.0] * 10)
        results.record("Invalid weights raises error", False, "No exception raised")
    except ValueError as e:
        results.record("Invalid weights raises error", True)

    # Test 4: Weight clamping
    print("\n4. Testing weight clamping...")
    controller = PerLayerPhaseController(num_layers=12)
    controller.set_weight(5, 1.5)  # Above max
    results.record(
        "Weight clamped to max 1.0",
        controller.get_weight(5) == 1.0,
        f"weight={controller.get_weight(5)}"
    )
    controller.set_weight(5, -0.5)  # Below min
    results.record(
        "Weight clamped to min 0.0",
        controller.get_weight(5) == 0.0,
        f"weight={controller.get_weight(5)}"
    )

    # Test 5: Soft transition
    print("\n5. Testing soft transition...")
    controller = PerLayerPhaseController(num_layers=12, local_layers=4)
    controller.start_transition(layer_idx=6, target_weight=1.0, duration_steps=100, current_step=0)
    results.record(
        "Transition started",
        6 in controller.transitions,
        f"transitions={list(controller.transitions.keys())}"
    )

    # At step 50 (halfway)
    result = controller.update(50)
    mid_weight = controller.get_weight(6)
    results.record(
        "Transition at 50%",
        0.45 <= mid_weight <= 0.55,
        f"weight at step 50: {mid_weight:.2f}"
    )

    # At step 100 (complete)
    result = controller.update(100)
    final_weight = controller.get_weight(6)
    results.record(
        "Transition complete at step 100",
        final_weight == 1.0 and 6 in result['completed'],
        f"weight={final_weight}, completed={result['completed']}"
    )

    # Test 6: Local layer transition (should be ignored)
    print("\n6. Testing local layer transition (should be ignored)...")
    controller = PerLayerPhaseController(num_layers=12, local_layers=4)
    controller.start_transition(layer_idx=2, target_weight=1.0, duration_steps=100, current_step=0)
    results.record(
        "Local layer transition ignored",
        2 not in controller.transitions,
        f"transitions={list(controller.transitions.keys())}"
    )

    # Test 7: Apply to model
    print("\n7. Testing apply to model...")
    model = MockHybridModel(num_layers=12)
    controller = PerLayerPhaseController(num_layers=12, local_layers=4)
    controller.set_weights([1.0 if i < 6 else 0.0 for i in range(12)])  # 6:6 split
    controller.apply_to_model(model)

    # Check layer weights
    layer_5_alpha = model.layers[5].alpha_phase.item()
    layer_6_alpha = model.layers[6].alpha_phase.item()
    results.record(
        "Model layer 5 alpha_phase = 1.0",
        abs(layer_5_alpha - 1.0) < 0.01,
        f"layer 5 alpha_phase={layer_5_alpha}"
    )
    results.record(
        "Model layer 6 alpha_phase = 0.0",
        abs(layer_6_alpha - 0.0) < 0.01,
        f"layer 6 alpha_phase={layer_6_alpha}"
    )

    # Test 8: Status reporting
    print("\n8. Testing status reporting...")
    controller = PerLayerPhaseController(num_layers=12, local_layers=4)
    controller.set_weights([1.0] * 6 + [0.0] * 6)  # 6:6 split
    status = controller.get_status()
    results.record(
        "Status authority count",
        status['authority_count'] == 2,  # layers 4, 5 (hybrid layers with weight 1.0)
        f"authority_count={status['authority_count']}"
    )
    results.record(
        "Status sensory count",
        status['sensory_count'] == 6,  # layers 6-11 (hybrid layers with weight 0.0)
        f"sensory_count={status['sensory_count']}"
    )

    return results


def test_inverted_layer_curriculum_controller():
    """Test InvertedLayerCurriculumController functionality."""
    print("\n" + "="*70)
    print("TEST: InvertedLayerCurriculumController")
    print("="*70)

    results = TestResult()

    # Define test curriculum
    stages = [
        ((3, 9), 256),   # Stage 0: Heavy Sensory, short seq
        ((4, 8), 256),   # Stage 1
        ((5, 7), 512),   # Stage 2: Grow seq
        ((6, 6), 768),   # Stage 3: Balanced
    ]
    ppl_triggers = [300, 200, 100]  # PPL thresholds for stages 0->1, 1->2, 2->3

    # Test 1: Initialization
    print("\n1. Testing initialization...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=100,
    )
    results.record(
        "Initial stage is 0",
        controller.current_stage_idx == 0,
        f"stage={controller.current_stage_idx}"
    )
    results.record(
        "Initial split is 3:9",
        controller.current_split == (3, 9),
        f"split={controller.current_split}"
    )
    results.record(
        "Initial seq_len is 256",
        controller.current_seq_len == 256,
        f"seq_len={controller.current_seq_len}"
    )

    # Test 2: Split to weights conversion
    print("\n2. Testing split to weights conversion...")
    weights_3_9 = controller._split_to_weights((3, 9))
    expected_3_9 = [1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    results.record(
        "3:9 split weights",
        weights_3_9 == expected_3_9,
        f"weights={weights_3_9}"
    )

    weights_6_6 = controller._split_to_weights((6, 6))
    expected_6_6 = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    results.record(
        "6:6 split weights",
        weights_6_6 == expected_6_6,
        f"weights={weights_6_6}"
    )

    # Test 3: PPL-triggered stage advancement
    print("\n3. Testing PPL-triggered stage advancement...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=100,
    )

    # Simulate PPL above threshold (no advancement)
    result = controller.update(step=100, current_ppl=350)
    results.record(
        "No advancement with PPL=350 > 300",
        controller.current_stage_idx == 0 and not result['split_changed'],
        f"stage={controller.current_stage_idx}, split_changed={result['split_changed']}"
    )

    # Simulate PPL below threshold (advance to stage 1)
    # Need multiple calls to fill the PPL history window for smoothing
    for i in range(10):
        controller.update(step=200 + i, current_ppl=250)
    result = controller.update(step=210, current_ppl=250)
    results.record(
        "Advance to stage 1 with smoothed PPL < 300",
        controller.current_stage_idx == 1,
        f"stage={controller.current_stage_idx}"
    )
    results.record(
        "Split changed to 4:8",
        controller.current_split == (4, 8),
        f"split={controller.current_split}"
    )

    # Test 4: Sequence length change
    print("\n4. Testing sequence length change...")
    # Continue to stage 2 (PPL < 200, seq_len changes to 512)
    for i in range(15):  # Fill PPL window with low PPL
        controller.update(step=300 + i, current_ppl=150)
    results.record(
        "Advance to stage 2 with PPL < 200",
        controller.current_stage_idx == 2,
        f"stage={controller.current_stage_idx}"
    )
    results.record(
        "Seq len changed to 512",
        controller.current_seq_len == 512,
        f"seq_len={controller.current_seq_len}"
    )

    # Test 5: Soft layer transitions
    print("\n5. Testing soft layer transitions...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=100,
    )

    # Advance to stage 1 (3:9 -> 4:8)
    result = controller.update(step=0, current_ppl=250)
    results.record(
        "Transition started for layer 3",
        result['transitioning_layers'] == 0,  # Layer 3 is local, so no hybrid transition
        f"transitioning_layers={result['transitioning_layers']}"
    )

    # Test 6: Model application
    print("\n6. Testing model application...")
    model = MockHybridModel(num_layers=12)
    controller = InvertedLayerCurriculumController(
        stages=[((6, 6), 512)],
        ppl_triggers=[],
        local_layers=4,
        transition_steps=100,
    )
    controller.apply_to_model(model)

    # Check that layers 4, 5 have alpha_phase = 1.0 (Authority)
    # and layers 6-11 have alpha_phase = 0.0 (Sensory)
    layer_5_alpha = model.layers[5].alpha_phase.item()
    layer_6_alpha = model.layers[6].alpha_phase.item()
    results.record(
        "Model layer 5 (Authority) alpha_phase = 1.0",
        abs(layer_5_alpha - 1.0) < 0.01,
        f"layer 5 alpha_phase={layer_5_alpha}"
    )
    results.record(
        "Model layer 6 (Sensory) alpha_phase = 0.0",
        abs(layer_6_alpha - 0.0) < 0.01,
        f"layer 6 alpha_phase={layer_6_alpha}"
    )

    # Test 7: Status reporting
    print("\n7. Testing status reporting...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=100,
    )
    status = controller.get_status()
    results.record(
        "Status stage correct",
        status['stage'] == 0,
        f"stage={status['stage']}"
    )
    results.record(
        "Status split correct",
        status['split'] == "3:9",
        f"split={status['split']}"
    )
    results.record(
        "Status seq_len correct",
        status['seq_len'] == 256,
        f"seq_len={status['seq_len']}"
    )

    # Test 8: PPL smoothing
    print("\n8. Testing PPL smoothing...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=100,
    )
    # Add high PPL values
    for i in range(5):
        controller.update(step=i, current_ppl=400)
    # Add low PPL value (should not trigger due to smoothing)
    result = controller.update(step=5, current_ppl=200)
    smoothed = sum(controller.ppl_history) / len(controller.ppl_history)
    results.record(
        "PPL smoothing prevents premature advancement",
        controller.current_stage_idx == 0 and smoothed > 300,
        f"stage={controller.current_stage_idx}, smoothed_ppl={smoothed:.2f}"
    )

    # Test 9: Full curriculum progression
    print("\n9. Testing full curriculum progression...")
    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=10,  # Fast transitions for testing
    )

    step = 0
    # Stage 0 -> 1
    for _ in range(15):
        controller.update(step, current_ppl=250)
        step += 1
    results.record(
        "Reached stage 1",
        controller.current_stage_idx == 1,
        f"stage={controller.current_stage_idx}"
    )

    # Stage 1 -> 2
    for _ in range(15):
        controller.update(step, current_ppl=150)
        step += 1
    results.record(
        "Reached stage 2",
        controller.current_stage_idx == 2,
        f"stage={controller.current_stage_idx}"
    )

    # Stage 2 -> 3
    for _ in range(15):
        controller.update(step, current_ppl=80)
        step += 1
    results.record(
        "Reached stage 3 (final)",
        controller.current_stage_idx == 3,
        f"stage={controller.current_stage_idx}"
    )
    results.record(
        "Final split is 6:6",
        controller.current_split == (6, 6),
        f"split={controller.current_split}"
    )
    results.record(
        "Final seq_len is 768",
        controller.current_seq_len == 768,
        f"seq_len={controller.current_seq_len}"
    )

    return results


def test_integration():
    """Test integration of controllers with model."""
    print("\n" + "="*70)
    print("TEST: Integration")
    print("="*70)

    results = TestResult()

    # Test 1: Full training loop simulation
    print("\n1. Simulating full training loop...")
    model = MockHybridModel(num_layers=12)

    stages = [
        ((3, 9), 256),
        ((6, 6), 512),
        ((9, 3), 1024),
    ]
    ppl_triggers = [200, 50]

    controller = InvertedLayerCurriculumController(
        stages=stages,
        ppl_triggers=ppl_triggers,
        local_layers=4,
        transition_steps=50,
    )

    # Initial state
    controller.apply_to_model(model)
    initial_layer_8 = model.layers[8].alpha_phase.item()
    results.record(
        "Initial layer 8 is Sensory (alpha=0)",
        abs(initial_layer_8 - 0.0) < 0.01,
        f"layer 8 alpha_phase={initial_layer_8}"
    )

    # Simulate PPL dropping
    ppl_values = [500, 400, 300, 250, 180, 150, 100, 80, 60, 45, 35, 25]
    step = 0
    seq_len_changes = []
    split_changes = []

    for ppl in ppl_values:
        for _ in range(20):  # 20 steps per PPL level
            result = controller.update(step, current_ppl=ppl)
            controller.apply_to_model(model)

            if result['seq_len_changed']:
                seq_len_changes.append((step, result['current_seq_len']))
            if result['split_changed']:
                split_changes.append((step, result['current_split']))

            step += 1

    results.record(
        "Reached final stage",
        controller.current_stage_idx == 2,
        f"stage={controller.current_stage_idx}"
    )
    results.record(
        "Split changed to 9:3",
        controller.current_split == (9, 3),
        f"split={controller.current_split}"
    )
    results.record(
        "Seq len grew to 1024",
        controller.current_seq_len == 1024,
        f"seq_len={controller.current_seq_len}"
    )

    # Check final model state
    final_layer_8 = model.layers[8].alpha_phase.item()
    results.record(
        "Final layer 8 is Authority (alpha=1)",
        abs(final_layer_8 - 1.0) < 0.01,
        f"layer 8 alpha_phase={final_layer_8}"
    )

    print(f"\n   Split changes: {split_changes}")
    print(f"   Seq len changes: {seq_len_changes}")

    return results


def main():
    """Run all tests."""
    print("="*70)
    print("INVERTED CURRICULUM EVOLUTION TESTS (V9.9.1)")
    print("="*70)

    all_results = []

    # Run test suites
    all_results.append(test_per_layer_phase_controller())
    all_results.append(test_inverted_layer_curriculum_controller())
    all_results.append(test_integration())

    # Aggregate results
    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total = total_passed + total_failed

    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print(f"Total: {total_passed}/{total} tests passed")

    if total_failed > 0:
        print(f"\nFailed tests:")
        for r in all_results:
            for name, msg in r.failures:
                print(f"  - {name}: {msg}")
        print("\n[FAIL] Some tests failed!")
        return 1
    else:
        print("\n[PASS] All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
