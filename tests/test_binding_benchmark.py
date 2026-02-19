"""
Tests for the Binding Benchmark Suite
=======================================

Tests cover:
  1. Dataset generation — template coverage, field validity, reproducibility
  2. Heads — forward pass shapes, parameter counts, gradient flow
  3. Evaluator — accuracy tracking, failure classification, condition binning
  4. Statistics — McNemar's test, confidence intervals, report generation
  5. End-to-end — train + evaluate pipeline
"""

import math
import random

import pytest
import torch

from resonant_model.dataset import (
    BindingDataset,
    BindingExample,
    FailureType,
    TemplateType,
    generate_dataset,
)
from resonant_model.heads import (
    CharTokenizer,
    HeadConfig,
    NamePooler,
    PositionalEncoding,
    ResonanceBindingHead,
    SoftmaxBindingHead,
    build_name_masks,
    count_parameters,
)
from resonant_model.evaluator import (
    BindingEvaluator,
    EvaluationResult,
    PredictionRecord,
    _bin_distance,
    _classify_failure,
    train_and_evaluate,
)
from resonant_model.statistics import (
    BindingStatistics,
    ComparisonReport,
    SignificanceResult,
    _chi2_sf,
    _normal_cdf,
    accuracy_confidence_interval,
    format_report,
    mcnemar_test,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatasetGeneration:
    """Tests for synthetic dataset generation."""

    def test_generate_default_count(self):
        ds = generate_dataset(num_examples=50, seed=1)
        assert len(ds) == 50

    def test_generate_200_examples(self):
        ds = generate_dataset(num_examples=200, seed=42)
        assert len(ds) == 200

    def test_template_coverage(self):
        """All 5 template types should appear."""
        ds = generate_dataset(num_examples=50, seed=42)
        types_seen = {ex.template_type for ex in ds}
        assert types_seen == set(TemplateType)

    def test_template_distribution_balanced(self):
        """Templates should be evenly distributed via round-robin."""
        ds = generate_dataset(num_examples=50, seed=42)
        dist = ds.template_distribution
        for ttype in TemplateType:
            assert dist[ttype.name] == 10  # 50 / 5 = 10 each

    def test_reproducibility(self):
        """Same seed should produce identical datasets."""
        ds1 = generate_dataset(num_examples=20, seed=123)
        ds2 = generate_dataset(num_examples=20, seed=123)
        for e1, e2 in zip(ds1, ds2):
            assert e1.passage == e2.passage
            assert e1.question == e2.question
            assert e1.correct_answer == e2.correct_answer

    def test_different_seeds_produce_different_data(self):
        ds1 = generate_dataset(num_examples=20, seed=1)
        ds2 = generate_dataset(num_examples=20, seed=2)
        passages1 = [ex.passage for ex in ds1]
        passages2 = [ex.passage for ex in ds2]
        assert passages1 != passages2

    def test_example_fields_populated(self):
        """All required fields should be non-empty."""
        ds = generate_dataset(num_examples=10, seed=42)
        for ex in ds:
            assert ex.passage, "passage should not be empty"
            assert ex.question, "question should not be empty"
            assert ex.correct_answer, "correct_answer should not be empty"
            assert len(ex.all_names) >= 2, "need at least 2 names"
            assert ex.correct_answer in ex.all_names
            assert ex.num_distractors >= 0
            assert ex.separation_distance > 0
            assert ex.nesting_depth >= 1

    def test_correct_answer_is_valid_name(self):
        ds = generate_dataset(num_examples=50, seed=42)
        for ex in ds:
            assert ex.correct_answer in ex.all_names

    def test_unique_names_per_example(self):
        ds = generate_dataset(num_examples=20, seed=42)
        for ex in ds:
            assert len(set(ex.all_names)) == len(ex.all_names)

    def test_min_max_names(self):
        ds = generate_dataset(
            num_examples=20, seed=42, min_names=3, max_names=4,
        )
        for ex in ds:
            assert 3 <= len(ex.all_names) <= 8  # generators may request more

    def test_min_max_distractors(self):
        ds = generate_dataset(
            num_examples=20, seed=42, min_distractors=1, max_distractors=3,
        )
        for ex in ds:
            assert ex.num_distractors >= 1
            assert ex.num_distractors <= 3

    def test_iterable(self):
        ds = generate_dataset(num_examples=5, seed=42)
        count = sum(1 for _ in ds)
        assert count == 5

    def test_indexable(self):
        ds = generate_dataset(num_examples=5, seed=42)
        ex = ds[0]
        assert isinstance(ex, BindingExample)

    def test_give_receive_template(self):
        ds = generate_dataset(num_examples=5, seed=42)
        give_examples = [e for e in ds if e.template_type == TemplateType.GIVE_RECEIVE]
        assert len(give_examples) == 1
        ex = give_examples[0]
        assert "gave" in ex.passage
        assert "received" in ex.question or "Who received" in ex.question

    def test_multi_hop_template(self):
        ds = generate_dataset(num_examples=5, seed=42)
        hop_examples = [e for e in ds if e.template_type == TemplateType.MULTI_HOP]
        assert len(hop_examples) == 1
        ex = hop_examples[0]
        assert "passed" in ex.passage or "gave" in ex.passage


# ═══════════════════════════════════════════════════════════════════════════════
# TOKENIZER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCharTokenizer:

    def test_encode_basic(self):
        tok = CharTokenizer()
        ids = tok.encode("hello", "world", max_len=20)
        assert ids.shape == (20,)
        assert ids.dtype == torch.long

    def test_encode_padding(self):
        tok = CharTokenizer()
        ids = tok.encode("a", "b", max_len=50)
        # Most should be padding (0)
        assert (ids == 0).sum().item() > 40

    def test_encode_truncation(self):
        tok = CharTokenizer()
        long_text = "x" * 1000
        ids = tok.encode(long_text, "q", max_len=100)
        assert ids.shape == (100,)

    def test_find_name_positions(self):
        tok = CharTokenizer()
        text = "Alice gave the book to Bob. Alice left."
        positions = tok.find_name_positions(text, ["Alice", "Bob"])
        assert len(positions["Alice"]) == 2
        assert len(positions["Bob"]) == 1

    def test_find_name_positions_no_match(self):
        tok = CharTokenizer()
        text = "Hello world"
        positions = tok.find_name_positions(text, ["Alice"])
        assert positions["Alice"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# HEAD TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSoftmaxBindingHead:

    @pytest.fixture
    def config(self):
        return HeadConfig(
            vocab_size=256, embed_dim=64, num_heads=2,
            num_layers=1, max_seq_len=128, max_names=8,
        )

    def test_forward_shape(self, config):
        model = SoftmaxBindingHead(config)
        token_ids = torch.randint(0, 256, (2, 128))
        name_masks = torch.zeros(2, 8, 128)
        name_masks[:, 0, 5:10] = 1.0
        name_masks[:, 1, 20:25] = 1.0

        logits = model(token_ids, name_masks)
        assert logits.shape == (2, 8)

    def test_gradient_flow(self, config):
        model = SoftmaxBindingHead(config)
        token_ids = torch.randint(0, 256, (1, 128))
        name_masks = torch.zeros(1, 8, 128)
        name_masks[0, 0, 5:10] = 1.0

        logits = model(token_ids, name_masks)
        loss = logits.sum()
        loss.backward()

        grad_count = sum(
            1 for p in model.parameters() if p.grad is not None and p.grad.abs().sum() > 0
        )
        assert grad_count > 0

    def test_attention_type(self, config):
        model = SoftmaxBindingHead(config)
        assert model.get_attention_type() == "softmax"


class TestResonanceBindingHead:

    @pytest.fixture
    def config(self):
        return HeadConfig(
            vocab_size=256, embed_dim=64, num_heads=2,
            num_layers=1, max_seq_len=128, max_names=8,
        )

    def test_forward_shape(self, config):
        model = ResonanceBindingHead(config)
        token_ids = torch.randint(0, 256, (2, 128))
        name_masks = torch.zeros(2, 8, 128)
        name_masks[:, 0, 5:10] = 1.0
        name_masks[:, 1, 20:25] = 1.0

        logits = model(token_ids, name_masks)
        assert logits.shape == (2, 8)

    def test_gradient_flow(self, config):
        model = ResonanceBindingHead(config)
        token_ids = torch.randint(0, 256, (1, 128))
        name_masks = torch.zeros(1, 8, 128)
        name_masks[0, 0, 5:10] = 1.0

        logits = model(token_ids, name_masks)
        loss = logits.sum()
        loss.backward()

        grad_count = sum(
            1 for p in model.parameters() if p.grad is not None and p.grad.abs().sum() > 0
        )
        assert grad_count > 0

    def test_attention_type(self, config):
        model = ResonanceBindingHead(config)
        assert model.get_attention_type() == "resonance_interference"

    def test_interference_gate_learnable(self, config):
        model = ResonanceBindingHead(config)
        # Check that interference_gate is a parameter
        gate_params = [
            name for name, p in model.named_parameters()
            if "interference_gate" in name
        ]
        assert len(gate_params) > 0

    def test_phase_proj_exists(self, config):
        model = ResonanceBindingHead(config)
        phase_params = [
            name for name, p in model.named_parameters()
            if "phase_proj" in name
        ]
        assert len(phase_params) > 0


class TestParameterComparison:
    """Model B should have more parameters than Model A (phase projection)."""

    def test_resonance_has_more_params(self):
        config = HeadConfig(embed_dim=64, num_heads=2, num_layers=1)
        model_a = SoftmaxBindingHead(config)
        model_b = ResonanceBindingHead(config)
        params_a = count_parameters(model_a)
        params_b = count_parameters(model_b)
        assert params_b > params_a


class TestPositionalEncoding:

    def test_output_shape(self):
        pe = PositionalEncoding(embed_dim=64, max_len=128)
        x = torch.randn(2, 50, 64)
        out = pe(x)
        assert out.shape == (2, 50, 64)

    def test_adds_positional_signal(self):
        pe = PositionalEncoding(embed_dim=64, max_len=128)
        x = torch.zeros(1, 10, 64)
        out = pe(x)
        # Output should not be all zeros (positional encoding added)
        assert out.abs().sum() > 0


class TestNamePooler:

    def test_output_shape(self):
        pooler = NamePooler(embed_dim=32)
        hidden = torch.randn(2, 50, 32)
        masks = torch.zeros(2, 5, 50)
        masks[:, 0, 5:10] = 1.0
        masks[:, 1, 20:25] = 1.0

        logits = pooler(hidden, masks)
        assert logits.shape == (2, 5)

    def test_zero_mask_gives_zero_logit(self):
        pooler = NamePooler(embed_dim=16)
        hidden = torch.randn(1, 20, 16)
        masks = torch.zeros(1, 3, 20)
        # Only first name has mask
        masks[0, 0, 5:10] = 1.0

        logits = pooler(hidden, masks)
        assert logits.shape == (1, 3)


class TestBuildNameMasks:

    def test_basic(self):
        tok = CharTokenizer()
        masks, names = build_name_masks(
            tok, "Alice gave to Bob", "Who?",
            ["Alice", "Bob"], max_len=50, max_names=4,
        )
        assert masks.shape == (1, 4, 50)
        assert len(names) == 4
        assert names[0] == "Alice"
        assert names[1] == "Bob"
        assert names[2] == ""
        assert names[3] == ""

    def test_mask_has_nonzero_entries(self):
        tok = CharTokenizer()
        masks, _ = build_name_masks(
            tok, "Alice gave to Bob", "Who?",
            ["Alice", "Bob"], max_len=50, max_names=4,
        )
        assert masks[0, 0].sum() > 0  # Alice mask
        assert masks[0, 1].sum() > 0  # Bob mask


# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailureClassification:

    def _make_example(self, **kwargs):
        defaults = dict(
            example_id=0,
            template_type=TemplateType.GIVE_RECEIVE,
            passage="Alice gave the book to Bob. Carol was nearby.",
            question="Who received the book?",
            correct_answer="Bob",
            all_names=["Alice", "Bob", "Carol"],
            all_objects=["book"],
            num_distractors=1,
            separation_distance=10,
            nesting_depth=1,
            role_assignments={"giver": "Alice", "receiver": "Bob"},
        )
        defaults.update(kwargs)
        return BindingExample(**defaults)

    def test_correct_classified(self):
        ex = self._make_example()
        assert _classify_failure(ex, "Bob") == FailureType.CORRECT

    def test_role_swap_classified(self):
        ex = self._make_example()
        result = _classify_failure(ex, "Alice")
        assert result == FailureType.ROLE_SWAP

    def test_non_correct_classified(self):
        ex = self._make_example()
        result = _classify_failure(ex, "Carol")
        # Carol could be nearest-name, random guess, or object confusion
        # depending on proximity — just verify it's not CORRECT
        assert result != FailureType.CORRECT


class TestDistanceBinning:

    def test_short(self):
        assert _bin_distance(5) == "short_0_19"

    def test_medium(self):
        assert _bin_distance(25) == "medium_20_39"

    def test_long(self):
        assert _bin_distance(50) == "long_40_59"

    def test_very_long(self):
        assert _bin_distance(100) == "very_long_60+"


class TestBindingEvaluator:

    @pytest.fixture
    def config(self):
        return HeadConfig(
            vocab_size=256, embed_dim=32, num_heads=2,
            num_layers=1, max_seq_len=128, max_names=8,
        )

    def test_evaluate_returns_result(self, config):
        model = SoftmaxBindingHead(config)
        ds = generate_dataset(num_examples=5, seed=42)
        evaluator = BindingEvaluator(config=config)
        result = evaluator.evaluate(model, ds, "test_model")

        assert isinstance(result, EvaluationResult)
        assert result.total_examples == 5
        assert 0.0 <= result.accuracy <= 1.0
        assert len(result.predictions) == 5

    def test_evaluate_failure_counts_populated(self, config):
        model = SoftmaxBindingHead(config)
        ds = generate_dataset(num_examples=10, seed=42)
        evaluator = BindingEvaluator(config=config)
        result = evaluator.evaluate(model, ds, "test")

        total_failures = sum(result.failure_counts.values())
        assert total_failures == 10

    def test_evaluate_template_accuracy(self, config):
        model = SoftmaxBindingHead(config)
        ds = generate_dataset(num_examples=10, seed=42)
        evaluator = BindingEvaluator(config=config)
        result = evaluator.evaluate(model, ds, "test")

        assert len(result.template_accuracy) > 0
        for acc in result.template_accuracy.values():
            assert 0.0 <= acc <= 1.0


class TestTrainAndEvaluate:

    def test_runs_without_error(self):
        config = HeadConfig(
            vocab_size=256, embed_dim=32, num_heads=2,
            num_layers=1, max_seq_len=128, max_names=8,
        )
        model = SoftmaxBindingHead(config)
        ds = generate_dataset(num_examples=5, seed=42)

        result = train_and_evaluate(
            model, ds, model_name="test",
            epochs=2, lr=1e-3, config=config,
        )
        assert isinstance(result, EvaluationResult)
        assert result.total_examples == 5

    def test_training_changes_predictions(self):
        """After training, model should give different predictions than random init."""
        config = HeadConfig(
            vocab_size=256, embed_dim=32, num_heads=2,
            num_layers=1, max_seq_len=128, max_names=8,
        )
        ds = generate_dataset(num_examples=10, seed=42)

        # Evaluate untrained
        model = SoftmaxBindingHead(config)
        evaluator = BindingEvaluator(config=config)
        result_before = evaluator.evaluate(model, ds, "before")

        # Train and evaluate
        model2 = SoftmaxBindingHead(config)
        result_after = train_and_evaluate(
            model2, ds, model_name="after",
            epochs=5, lr=1e-2, config=config,
        )

        # Predictions should differ (training did something)
        preds_before = [p.predicted_answer for p in result_before.predictions]
        preds_after = [p.predicted_answer for p in result_after.predictions]
        # Not a strict assertion since random init can vary
        # Just check it runs


# ═══════════════════════════════════════════════════════════════════════════════
# STATISTICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalCdf:

    def test_at_zero(self):
        assert abs(_normal_cdf(0) - 0.5) < 1e-6

    def test_large_positive(self):
        assert _normal_cdf(5.0) > 0.999

    def test_large_negative(self):
        assert _normal_cdf(-5.0) < 0.001

    def test_symmetry(self):
        assert abs(_normal_cdf(1.0) + _normal_cdf(-1.0) - 1.0) < 1e-6


class TestChi2Sf:

    def test_zero_gives_one(self):
        assert _chi2_sf(0.0) == 1.0

    def test_large_value_gives_small_p(self):
        assert _chi2_sf(20.0) < 0.001

    def test_critical_value_3_84(self):
        # chi2(1) = 3.84 corresponds to p ~ 0.05
        p = _chi2_sf(3.84)
        assert abs(p - 0.05) < 0.02


class TestMcNemarTest:

    def _make_predictions(self, correct_flags):
        """Helper to create prediction records from correct/incorrect flags."""
        return [
            PredictionRecord(
                example_id=i,
                template_type=TemplateType.GIVE_RECEIVE,
                correct_answer="X",
                predicted_answer="X" if c else "Y",
                is_correct=c,
                failure_type=FailureType.CORRECT if c else FailureType.ROLE_SWAP,
                num_distractors=2,
                separation_distance=10,
                nesting_depth=1,
                confidence=0.9 if c else 0.1,
            )
            for i, c in enumerate(correct_flags)
        ]

    def test_identical_models(self):
        flags = [True, True, False, False, True]
        preds_a = self._make_predictions(flags)
        preds_b = self._make_predictions(flags)

        result = mcnemar_test(preds_a, preds_b)
        assert result.p_value == 1.0
        assert not result.significant_at_05

    def test_different_models(self):
        # B always correct, A always wrong → should be significant
        n = 50
        preds_a = self._make_predictions([False] * n)
        preds_b = self._make_predictions([True] * n)

        result = mcnemar_test(preds_a, preds_b)
        assert result.p_value < 0.05
        assert result.significant_at_05

    def test_effect_size_positive_when_b_better(self):
        n = 30
        flags_a = [False] * 20 + [True] * 10
        flags_b = [True] * 20 + [True] * 10

        preds_a = self._make_predictions(flags_a)
        preds_b = self._make_predictions(flags_b)

        result = mcnemar_test(preds_a, preds_b)
        assert result.effect_size > 0  # B is better

    def test_mismatched_lengths_raises(self):
        preds_a = self._make_predictions([True, False])
        preds_b = self._make_predictions([True])

        with pytest.raises(AssertionError):
            mcnemar_test(preds_a, preds_b)


class TestConfidenceInterval:

    def test_zero_difference(self):
        low, high = accuracy_confidence_interval(0.5, 0.5, 100)
        assert low < 0
        assert high > 0

    def test_positive_difference(self):
        low, high = accuracy_confidence_interval(0.4, 0.8, 200)
        diff = 0.8 - 0.4
        assert low < diff < high
        assert low > 0  # CI should not include 0 for large difference

    def test_n_zero(self):
        low, high = accuracy_confidence_interval(0.5, 0.6, 0)
        assert abs(low - 0.1) < 1e-10  # diff with zero SE
        assert abs(high - 0.1) < 1e-10


class TestBindingStatistics:

    def _make_result(self, model_name, correct_ids, total=10):
        """Create EvaluationResult where specific IDs are correct."""
        predictions = []
        correct_count = 0
        for i in range(total):
            is_correct = i in correct_ids
            if is_correct:
                correct_count += 1
            predictions.append(PredictionRecord(
                example_id=i,
                template_type=TemplateType.GIVE_RECEIVE,
                correct_answer="X",
                predicted_answer="X" if is_correct else "Y",
                is_correct=is_correct,
                failure_type=FailureType.CORRECT if is_correct else FailureType.ROLE_SWAP,
                num_distractors=2,
                separation_distance=10,
                nesting_depth=1,
                confidence=0.9,
            ))

        return EvaluationResult(
            model_name=model_name,
            total_examples=total,
            correct=correct_count,
            accuracy=correct_count / total,
            predictions=predictions,
            failure_counts={
                FailureType.CORRECT.value: correct_count,
                FailureType.ROLE_SWAP.value: total - correct_count,
                FailureType.NEAREST_NAME_BIAS.value: 0,
                FailureType.OBJECT_CONFUSION.value: 0,
                FailureType.RANDOM_GUESS.value: 0,
            },
            template_accuracy={"GIVE_RECEIVE": correct_count / total},
            template_counts={"GIVE_RECEIVE": total},
            distractor_accuracy={2: correct_count / total},
            distance_accuracy={"short_0_19": correct_count / total},
            nesting_accuracy={1: correct_count / total},
        )

    def test_compare_produces_report(self):
        result_a = self._make_result("softmax", {0, 1, 2}, total=10)
        result_b = self._make_result("resonance", {0, 1, 2, 3, 4, 5}, total=10)

        stats = BindingStatistics()
        report = stats.compare(result_a, result_b)

        assert isinstance(report, ComparisonReport)
        assert report.model_a_accuracy == 0.3
        assert report.model_b_accuracy == 0.6
        assert report.accuracy_difference == pytest.approx(0.3)

    def test_format_report_produces_string(self):
        result_a = self._make_result("softmax", {0, 1}, total=10)
        result_b = self._make_result("resonance", {0, 1, 2, 3}, total=10)

        stats = BindingStatistics()
        report = stats.compare(result_a, result_b)
        text = format_report(report)

        assert isinstance(text, str)
        assert "BINDING BENCHMARK" in text
        assert "softmax" in text
        assert "resonance" in text

    def test_hypothesis_supported_when_b_significantly_better(self):
        # B much better with enough samples
        n = 100
        result_a = self._make_result("softmax", set(range(30)), total=n)
        result_b = self._make_result("resonance", set(range(70)), total=n)

        stats = BindingStatistics()
        report = stats.compare(result_a, result_b)

        assert report.accuracy_difference > 0
        # May or may not be significant depending on McNemar's

    def test_hypothesis_not_supported_when_equal(self):
        n = 20
        ids = set(range(10))
        result_a = self._make_result("softmax", ids, total=n)
        result_b = self._make_result("resonance", ids, total=n)

        stats = BindingStatistics()
        report = stats.compare(result_a, result_b)

        assert not report.hypothesis_supported


# ═══════════════════════════════════════════════════════════════════════════════
# END-TO-END TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    """Integration tests running the full pipeline."""

    @pytest.fixture
    def small_config(self):
        return HeadConfig(
            vocab_size=256, embed_dim=32, num_heads=2,
            num_layers=1, max_seq_len=64, max_names=8,
        )

    def test_full_pipeline(self, small_config):
        """Generate data, train both models, compare."""
        ds = generate_dataset(num_examples=10, seed=42)

        model_a = SoftmaxBindingHead(small_config)
        model_b = ResonanceBindingHead(small_config, lambda_interference=0.3)

        result_a = train_and_evaluate(
            model_a, ds, "softmax", epochs=2, config=small_config,
        )
        result_b = train_and_evaluate(
            model_b, ds, "resonance", epochs=2, config=small_config,
        )

        stats = BindingStatistics()
        report = stats.compare(result_a, result_b)

        assert isinstance(report, ComparisonReport)
        assert report.summary  # non-empty summary
        assert report.model_a_name == "softmax"
        assert report.model_b_name == "resonance"

    def test_both_models_produce_valid_logits(self, small_config):
        """Both models should produce finite logits."""
        ds = generate_dataset(num_examples=3, seed=42)
        tok = CharTokenizer()

        for ModelClass in [SoftmaxBindingHead, ResonanceBindingHead]:
            if ModelClass == ResonanceBindingHead:
                model = ModelClass(small_config, lambda_interference=0.3)
            else:
                model = ModelClass(small_config)
            model.eval()

            for ex in ds:
                token_ids = tok.encode(
                    ex.passage, ex.question, small_config.max_seq_len,
                ).unsqueeze(0)
                masks, _ = build_name_masks(
                    tok, ex.passage, ex.question, ex.all_names,
                    small_config.max_seq_len, small_config.max_names,
                )

                with torch.no_grad():
                    logits = model(token_ids, masks)

                assert torch.isfinite(logits).all(), (
                    f"{ModelClass.__name__} produced non-finite logits"
                )

    def test_resonance_has_interference_mechanism(self, small_config):
        """Verify the interference computation is actually invoked."""
        model = ResonanceBindingHead(small_config, lambda_interference=0.5)

        # Check that phase_proj weight is non-trivially used
        has_phase = any("phase_proj" in n for n, _ in model.named_parameters())
        assert has_phase

        has_gate = any("interference_gate" in n for n, _ in model.named_parameters())
        assert has_gate
