"""
Binding Evaluation Harness
===========================

Evaluates binding heads on synthetic datasets with:
  - Overall accuracy (% correct role resolution)
  - Failure type classification (role swap, nearest-name bias, etc.)
  - Per-template-type breakdown
  - Distance-binned accuracy
  - Distractor-count-binned accuracy
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor

from resonant_model.dataset import (
    BindingDataset,
    BindingExample,
    FailureType,
    TemplateType,
)
from resonant_model.heads import (
    CharTokenizer,
    HeadConfig,
    build_name_masks,
)


@dataclass
class PredictionRecord:
    """Record of a single prediction."""
    example_id: int
    template_type: TemplateType
    correct_answer: str
    predicted_answer: str
    is_correct: bool
    failure_type: FailureType
    num_distractors: int
    separation_distance: int
    nesting_depth: int
    confidence: float  # softmax probability of predicted answer


@dataclass
class EvaluationResult:
    """Aggregated evaluation results for a model."""
    model_name: str
    total_examples: int
    correct: int
    accuracy: float
    predictions: List[PredictionRecord] = field(default_factory=list)

    # Failure type counts
    failure_counts: Dict[str, int] = field(default_factory=dict)

    # Per-template accuracy
    template_accuracy: Dict[str, float] = field(default_factory=dict)
    template_counts: Dict[str, int] = field(default_factory=dict)

    # Accuracy by distractor count (binned)
    distractor_accuracy: Dict[int, float] = field(default_factory=dict)

    # Accuracy by separation distance (binned)
    distance_accuracy: Dict[str, float] = field(default_factory=dict)

    # Accuracy by nesting depth
    nesting_accuracy: Dict[int, float] = field(default_factory=dict)


def _classify_failure(
    example: BindingExample,
    predicted: str,
) -> FailureType:
    """
    Classify the type of binding failure.

    Args:
        example: The binding example.
        predicted: The predicted answer.

    Returns:
        FailureType indicating what went wrong.
    """
    if predicted == example.correct_answer:
        return FailureType.CORRECT

    # Check for role swap: predicted is another role-holder
    role_names = set(example.role_assignments.values())
    if predicted in role_names:
        return FailureType.ROLE_SWAP

    # Check for nearest-name bias: predicted is the name closest to the question
    passage_question = example.passage + " " + example.question
    question_start = len(example.passage)
    best_dist = float("inf")
    nearest_name = ""
    for name in example.all_names:
        pos = passage_question.rfind(name, 0, question_start)
        if pos >= 0:
            dist = question_start - pos
            if dist < best_dist:
                best_dist = dist
                nearest_name = name

    if predicted == nearest_name and nearest_name != example.correct_answer:
        return FailureType.NEAREST_NAME_BIAS

    # Check for object confusion (wrong object association)
    if example.all_objects and predicted in example.all_names:
        # The model picked a name that's in the example but not a role-holder
        # and not the nearest name — likely confused by object associations
        if predicted not in role_names:
            return FailureType.OBJECT_CONFUSION

    return FailureType.RANDOM_GUESS


def _bin_distance(distance: int) -> str:
    """Bin separation distance into categories."""
    if distance < 20:
        return "short_0_19"
    elif distance < 40:
        return "medium_20_39"
    elif distance < 60:
        return "long_40_59"
    else:
        return "very_long_60+"


class BindingEvaluator:
    """
    Evaluates a binding head on a dataset.

    Runs greedy decoding (argmax over name logits) and tracks
    accuracy, failure types, and performance across conditions.
    """

    def __init__(
        self,
        config: Optional[HeadConfig] = None,
        device: Optional[torch.device] = None,
    ):
        self.config = config or HeadConfig()
        self.device = device or torch.device("cpu")
        self.tokenizer = CharTokenizer(self.config.vocab_size)

    @torch.no_grad()
    def evaluate(
        self,
        model: nn.Module,
        dataset: BindingDataset,
        model_name: str = "model",
    ) -> EvaluationResult:
        """
        Evaluate a model on the binding dataset.

        Args:
            model: A binding head (SoftmaxBindingHead or ResonanceBindingHead).
            dataset: The binding dataset.
            model_name: Name for this model in results.

        Returns:
            EvaluationResult with all metrics.
        """
        model.eval()
        model = model.to(self.device)

        predictions: List[PredictionRecord] = []
        correct_count = 0

        # Counters for per-condition accuracy
        template_correct: Dict[str, int] = {}
        template_total: Dict[str, int] = {}
        distractor_correct: Dict[int, int] = {}
        distractor_total: Dict[int, int] = {}
        distance_correct: Dict[str, int] = {}
        distance_total: Dict[str, int] = {}
        nesting_correct: Dict[int, int] = {}
        nesting_total: Dict[int, int] = {}
        failure_counts: Dict[str, int] = {ft.value: 0 for ft in FailureType}

        for example in dataset:
            # Tokenize
            token_ids = self.tokenizer.encode(
                example.passage, example.question, self.config.max_seq_len,
            ).unsqueeze(0).to(self.device)

            # Build name masks
            name_masks, padded_names = build_name_masks(
                self.tokenizer,
                example.passage,
                example.question,
                example.all_names,
                self.config.max_seq_len,
                self.config.max_names,
            )
            name_masks = name_masks.to(self.device)

            # Forward pass
            logits = model(token_ids, name_masks)  # [1, max_names]

            # Greedy decode: pick highest logit among valid names
            num_valid = len(example.all_names)
            valid_logits = logits[0, :num_valid]
            probs = torch.softmax(valid_logits, dim=0)
            pred_idx = valid_logits.argmax().item()
            predicted_name = example.all_names[pred_idx]
            confidence = probs[pred_idx].item()

            # Check correctness
            is_correct = predicted_name == example.correct_answer
            if is_correct:
                correct_count += 1

            # Classify failure
            failure = _classify_failure(example, predicted_name)
            failure_counts[failure.value] += 1

            # Record prediction
            predictions.append(PredictionRecord(
                example_id=example.example_id,
                template_type=example.template_type,
                correct_answer=example.correct_answer,
                predicted_answer=predicted_name,
                is_correct=is_correct,
                failure_type=failure,
                num_distractors=example.num_distractors,
                separation_distance=example.separation_distance,
                nesting_depth=example.nesting_depth,
                confidence=confidence,
            ))

            # Update per-condition counters
            tpl = example.template_type.name
            template_total[tpl] = template_total.get(tpl, 0) + 1
            template_correct[tpl] = template_correct.get(tpl, 0) + (1 if is_correct else 0)

            nd = example.num_distractors
            distractor_total[nd] = distractor_total.get(nd, 0) + 1
            distractor_correct[nd] = distractor_correct.get(nd, 0) + (1 if is_correct else 0)

            dist_bin = _bin_distance(example.separation_distance)
            distance_total[dist_bin] = distance_total.get(dist_bin, 0) + 1
            distance_correct[dist_bin] = distance_correct.get(dist_bin, 0) + (1 if is_correct else 0)

            depth = example.nesting_depth
            nesting_total[depth] = nesting_total.get(depth, 0) + 1
            nesting_correct[depth] = nesting_correct.get(depth, 0) + (1 if is_correct else 0)

        # Compute accuracies
        total = len(dataset)
        accuracy = correct_count / total if total > 0 else 0.0

        template_accuracy = {
            k: template_correct.get(k, 0) / v
            for k, v in template_total.items() if v > 0
        }

        distractor_accuracy = {
            k: distractor_correct.get(k, 0) / v
            for k, v in distractor_total.items() if v > 0
        }

        distance_accuracy = {
            k: distance_correct.get(k, 0) / v
            for k, v in distance_total.items() if v > 0
        }

        nesting_accuracy = {
            k: nesting_correct.get(k, 0) / v
            for k, v in nesting_total.items() if v > 0
        }

        return EvaluationResult(
            model_name=model_name,
            total_examples=total,
            correct=correct_count,
            accuracy=accuracy,
            predictions=predictions,
            failure_counts=failure_counts,
            template_accuracy=template_accuracy,
            template_counts=dict(template_total),
            distractor_accuracy=distractor_accuracy,
            distance_accuracy=distance_accuracy,
            nesting_accuracy=nesting_accuracy,
        )


def train_and_evaluate(
    model: nn.Module,
    dataset: BindingDataset,
    model_name: str = "model",
    epochs: int = 10,
    lr: float = 1e-3,
    device: Optional[torch.device] = None,
    config: Optional[HeadConfig] = None,
    gate_entropy_weight: float = 0.0,
    gate_variance_weight: float = 0.0,
    gate_lr_multiplier: float = 1.0,
    warmup_epochs: int = 0,
) -> EvaluationResult:
    """
    Train a binding head on the dataset (supervised) then evaluate.

    Uses the correct answer as the training signal (cross-entropy loss
    on name logits). After training, evaluates with greedy decoding.

    Args:
        model: A binding head.
        dataset: The binding dataset.
        model_name: Name for results.
        epochs: Training epochs.
        lr: Learning rate.
        device: Torch device.
        config: Head config.
        gate_entropy_weight: Weight for gate entropy regularization
            (prevents degenerate g near 0 or 1). Only applies to
            ResonanceBindingHead.
        gate_variance_weight: Weight for gate variance encouragement
            (prevents constant gate across tokens). Only applies to
            ResonanceBindingHead.
        gate_lr_multiplier: Learning rate multiplier for gate parameters
            relative to base lr. Values > 1 give gate faster training.
            Only applies to ResonanceBindingHead.
        warmup_epochs: Number of initial epochs where amplitude projections
            are frozen, forcing the gate to learn dynamic modulation before
            projections can collapse the signal. Only applies to
            ResonanceBindingHead.

    Returns:
        EvaluationResult after training.
    """
    config = config or HeadConfig()
    device = device or torch.device("cpu")
    model = model.to(device)
    tokenizer = CharTokenizer(config.vocab_size)

    # Use duck typing: check for methods rather than specific classes
    has_gate_reg = hasattr(model, "compute_gate_regularization") and (
        gate_entropy_weight > 0 or gate_variance_weight > 0
    )
    has_warmup = hasattr(model, "get_amplitude_parameters") and warmup_epochs > 0
    has_gate_lr = hasattr(model, "get_gate_parameters") and gate_lr_multiplier != 1.0

    # Build optimizer with optional separate gate LR
    if has_gate_lr:
        gate_params = model.get_gate_parameters()
        other_params = model.get_non_gate_parameters()
        optimizer = torch.optim.Adam([
            {"params": other_params, "lr": lr},
            {"params": gate_params, "lr": lr * gate_lr_multiplier},
        ])
    else:
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Track amplitude params for warmup freezing
    amp_params = None
    if has_warmup:
        amp_params = model.get_amplitude_parameters()

    model.train()
    for epoch in range(epochs):
        # Warmup: freeze amplitude projections for first N epochs
        in_warmup = has_warmup and epoch < warmup_epochs
        if in_warmup and amp_params:
            for p in amp_params:
                p.requires_grad = False
        elif has_warmup and epoch == warmup_epochs and amp_params:
            # Unfreeze at end of warmup
            for p in amp_params:
                p.requires_grad = True

        total_loss = 0.0
        for example in dataset:
            optimizer.zero_grad()

            token_ids = tokenizer.encode(
                example.passage, example.question, config.max_seq_len,
            ).unsqueeze(0).to(device)

            name_masks, padded_names = build_name_masks(
                tokenizer,
                example.passage,
                example.question,
                example.all_names,
                config.max_seq_len,
                config.max_names,
            )
            name_masks = name_masks.to(device)

            logits = model(token_ids, name_masks)  # [1, max_names]

            # Target: index of correct answer in all_names
            try:
                target_idx = example.all_names.index(example.correct_answer)
            except ValueError:
                continue

            target = torch.tensor([target_idx], dtype=torch.long, device=device)

            # Only compute loss over valid name positions
            num_valid = len(example.all_names)
            loss = torch.nn.functional.cross_entropy(
                logits[:, :num_valid], target,
            )

            # Gate regularization (only for ResonanceBindingHead)
            if has_gate_reg:
                gate_loss = model.compute_gate_regularization(
                    entropy_weight=gate_entropy_weight,
                    variance_weight=gate_variance_weight,
                )
                loss = loss + gate_loss

            loss.backward()
            optimizer.step()
            total_loss += loss.item()

    # Evaluate
    evaluator = BindingEvaluator(config=config, device=device)
    return evaluator.evaluate(model, dataset, model_name)
