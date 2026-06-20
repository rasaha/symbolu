"""CPU-safe tests for the CG-wrapper generation-quality ablation (Task 4).

Two tiers:
  1. Pure-Python tier (no torch): metric/stat correctness + eval-set integrity. Always runs.
  2. Torch tier: module imports, wrapper construction on a stub backbone, gate=0 logit
     equivalence (arm D == base), and ΔBhava behaviour. Skips cleanly when torch / the wrapper
     deps / a checkpoint are unavailable — never assumes a GPU or a real model.

This is RESEARCH-track only and imports no governance code.
"""

import sys
from pathlib import Path

import pytest

# Make the script-local cg_ablation package importable without installing it.
_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from cg_ablation import metrics as M  # noqa: E402
from cg_ablation import evalsets as E  # noqa: E402


# ===========================================================================
# Tier 1 — pure Python (always runs)
# ===========================================================================

class TestAnswerExtraction:
    def test_hash_marker_preferred(self):
        assert M.extract_final_integer("work... #### 42") == 42

    def test_last_number_fallback(self):
        assert M.extract_final_integer("so the total is 17 apples") == 17

    def test_comma_thousands(self):
        assert M.extract_final_integer("answer: 1,234") == 1234

    def test_fractional_rejected(self):
        assert M.extract_final_integer("about 3.5 things") is None

    def test_no_number(self):
        assert M.extract_final_integer("no digits here") is None

    def test_exact_match(self):
        assert M.exact_match("#### 5", 5)
        assert not M.exact_match("#### 6", 5)


class TestJsonMetrics:
    def test_parse_ok_with_prose(self):
        assert M.json_parse_ok('Here: {"a": 1, "b": [1,2]} done')

    def test_parse_fail(self):
        assert not M.json_parse_ok("not json at all")
        assert not M.json_parse_ok('{"a": 1,}')  # trailing comma invalid

    def test_required_keys(self):
        assert M.json_has_keys('{"name":"x","age":3}', ["name", "age"])
        assert not M.json_has_keys('{"name":"x"}', ["name", "age"])

    def test_nested_braces_balanced(self):
        assert M.json_has_keys('{"a": {"b": 1}, "c": 2}', ["a", "c"])


class TestConstraints:
    def test_exact_words(self):
        assert M.constraint_satisfied("Paris", {"type": "exact_words", "value": 1})
        assert not M.constraint_satisfied("Paris France", {"type": "exact_words", "value": 1})

    def test_max_words(self):
        assert M.constraint_satisfied("a b c", {"type": "max_words", "value": 5})

    def test_line_count(self):
        assert M.constraint_satisfied("a\nb\nc", {"type": "line_count", "value": 3})

    def test_one_of_case_insensitive(self):
        assert M.constraint_satisfied("YES", {"type": "one_of", "value": ["yes", "no"]})

    def test_ends_with(self):
        assert M.constraint_satisfied("all good DONE", {"type": "ends_with", "value": "DONE"})

    def test_unknown_type_fails_closed(self):
        assert not M.constraint_satisfied("x", {"type": "made_up", "value": 1})


class TestConsistencyAndStats:
    def test_pairwise_agreement(self):
        assert M.pairwise_agreement([1, 1, 1]) == 1.0
        assert M.pairwise_agreement([1, 2]) == 0.0
        assert M.pairwise_agreement([1, 1, 2]) == pytest.approx(1 / 3)

    def test_mcnemar_improvement(self):
        a = [False, False, True, True]
        b = [True, True, True, True]
        r = M.mcnemar_exact(a, b)
        assert r["b01_improve"] == 2 and r["b10_regress"] == 0
        assert r["delta"] == pytest.approx(0.5)

    def test_mcnemar_no_discordance_is_p1(self):
        a = [True, False, True]
        r = M.mcnemar_exact(a, a)
        assert r["p_value"] == 1.0 and r["delta"] == 0.0

    def test_bootstrap_zero_diff(self):
        x = [1, 0, 1, 0, 1]
        pt, lo, hi = M.paired_bootstrap_ci(x, x, n_boot=1000)
        assert pt == 0.0 and lo == 0.0 and hi == 0.0

    def test_bootstrap_positive(self):
        a = [0, 0, 0, 0]
        b = [1, 1, 1, 1]
        pt, lo, hi = M.paired_bootstrap_ci(a, b, n_boot=1000)
        assert pt == 1.0 and lo == 1.0 and hi == 1.0


class TestLogitMetrics:
    def test_kl_identical_is_zero(self):
        base = [[2.0, 1.0, 0.0], [0.0, 1.0, 2.0]]
        assert M.logit_kl_per_token(base, base) == pytest.approx(0.0, abs=1e-9)

    def test_flip_rate(self):
        base = [[2.0, 1.0, 0.0], [0.0, 1.0, 2.0]]
        wrap = [[2.0, 1.0, 0.0], [2.0, 1.0, 0.0]]
        assert M.top1_flip_rate(base, wrap) == 0.5

    def test_kl_positive_when_different(self):
        base = [[3.0, 0.0, 0.0]]
        wrap = [[0.0, 0.0, 3.0]]
        assert M.logit_kl_per_token(base, wrap) > 0.0


class TestEvalSetsIntegrity:
    def test_all_sets_load(self):
        sets = E.load_all()
        assert set(sets) == set(E.EVAL_SETS)
        assert all(len(v) > 0 for v in sets.values())

    def test_seeds_pinned(self):
        assert E.SEEDS == [0, 1, 2, 3, 4]

    def test_gsm_rows_have_integer_answers(self):
        for r in E.load_eval_set("gsm8k_style"):
            assert isinstance(r["answer"], int)
            assert "prompt" in r and "id" in r

    def test_constraint_rows_wellformed(self):
        for r in E.load_eval_set("format_constraints"):
            assert isinstance(r["constraints"], list) and r["constraints"]

    def test_json_rows_have_required_keys(self):
        for r in E.load_eval_set("json_format"):
            assert isinstance(r["required_keys"], list) and r["required_keys"]

    def test_ids_unique_per_set(self):
        for name in E.EVAL_SETS:
            rows = E.load_eval_set(name)
            ids = [r["id"] for r in rows]
            assert len(ids) == len(set(ids))


class TestMetricsReportVerdict:
    """The decision evaluator (pure Python) resolves the post-Active-CG categories correctly."""

    def _import(self):
        import importlib
        return importlib.import_module("metrics_report")

    # active (non-inert) B vs base diagnostics shared by most cases
    _ACTIVE_DIAG = {
        "D_gate0": {"max_abs_logit_diff_vs_base": 0.0},
        "B_full": {"mean_logit_kl_vs_base": 0.4, "mean_top1_flip_vs_base": 0.2,
                   "mean_correction_to_hidden_ratio": 0.047},
    }

    @staticmethod
    def _p(direction, sig):
        return {"gsm8k_style": {"significant": sig, "direction": direction}}

    def test_k0_hidden_coupling_wins(self):
        R = self._import()
        diag = {"D_gate0": {"max_abs_logit_diff_vs_base": 0.5}, "B_full": self._ACTIVE_DIAG["B_full"]}
        v = R.evaluate_kill_criteria({}, {}, diag)
        assert v["decision"] == "INVESTIGATE_K0_HIDDEN_COUPLING"

    def test_inert(self):
        R = self._import()
        diag = {"D_gate0": {"max_abs_logit_diff_vs_base": 0.0},
                "B_full": {"mean_logit_kl_vs_base": 1e-6, "mean_top1_flip_vs_base": 0.0,
                           "mean_correction_to_hidden_ratio": 1e-5}}
        v = R.evaluate_kill_criteria({}, {}, diag)
        assert v["decision"] == "INERT"

    def test_active_no_effect(self):
        R = self._import()
        v = R.evaluate_kill_criteria({}, self._p("none", False), self._ACTIVE_DIAG,
                                     paired_b_vs_c=self._p("none", False),
                                     paired_c_vs_a=self._p("none", False),
                                     b_vs_c_logit={"mean_logit_kl_B_vs_C": 0.3, "mean_top1_flip_B_vs_C": 0.1})
        assert v["decision"] == "ACTIVE_NO_EFFECT"

    def test_regression(self):
        R = self._import()
        v = R.evaluate_kill_criteria({}, self._p("regress", True), self._ACTIVE_DIAG,
                                     paired_b_vs_c=self._p("none", False),
                                     paired_c_vs_a=self._p("none", False),
                                     b_vs_c_logit={"mean_logit_kl_B_vs_C": 0.1, "mean_top1_flip_B_vs_C": 0.05})
        assert v["decision"] == "REGRESSION" and v["b_regresses_A_sets"] == ["gsm8k_style"]

    def test_cg_dynamic_signal(self):
        R = self._import()
        v = R.evaluate_kill_criteria({}, self._p("improve", True), self._ACTIVE_DIAG,
                                     paired_b_vs_c=self._p("improve", True),
                                     paired_c_vs_a=self._p("none", False),
                                     b_vs_c_logit={"mean_logit_kl_B_vs_C": 0.3, "mean_top1_flip_B_vs_C": 0.1})
        assert v["decision"] == "CG_DYNAMIC_SIGNAL"

    def test_static_offset_no_cg_dynamic(self):
        R = self._import()
        # B>A but B≈C (not distinguishable, logits ~equal) => the gain is the static offset.
        v = R.evaluate_kill_criteria({}, self._p("improve", True), self._ACTIVE_DIAG,
                                     paired_b_vs_c=self._p("none", False),
                                     paired_c_vs_a=self._p("improve", True),
                                     b_vs_c_logit={"mean_logit_kl_B_vs_C": 1e-5, "mean_top1_flip_B_vs_C": 0.0})
        assert v["decision"] == "STATIC_OFFSET_NO_CG_DYNAMIC"
        assert any("STATIC OFFSET" in w for w in v["warnings"])

    def test_weak_objective_gain(self):
        R = self._import()
        # B>A, but B-vs-C distinguishable in the WRONG direction (C beats B) => ambiguous/weak.
        v = R.evaluate_kill_criteria({}, self._p("improve", True), self._ACTIVE_DIAG,
                                     paired_b_vs_c=self._p("regress", True),
                                     paired_c_vs_a=self._p("improve", True),
                                     b_vs_c_logit={"mean_logit_kl_B_vs_C": 0.3, "mean_top1_flip_B_vs_C": 0.1})
        assert v["decision"] == "WEAK_OBJECTIVE_GAIN"


# ===========================================================================
# Tier 2 — torch / wrapper (skips cleanly without torch or a real model)
# ===========================================================================

try:
    import torch
    _HAS_TORCH = True
except Exception:
    torch = None
    _HAS_TORCH = False

# Gate the whole torch tier; Tier 1 (pure Python) above still runs without torch.
pytestmark_torch = pytest.mark.skipif(
    not _HAS_TORCH, reason="torch required for wrapper-level tests"
)


def _build_stub():
    """Build a stub-backed wrapper, skipping if deps are missing."""
    from cg_ablation.stub_backend import build_stub_wrapper
    try:
        return build_stub_wrapper(hidden_size=64, vocab_size=128, num_heads=8, seed=0)
    except ImportError as exc:  # wrapper deps unavailable
        pytest.skip(f"wrapper deps unavailable: {exc}")


@pytestmark_torch
class TestModuleImports:
    def test_wrapper_imports(self):
        import importlib
        importlib.import_module("symbolu_training.training.unified.mistral_wrapper")
        importlib.import_module("symbolu_core.phase_transformer")
        importlib.import_module("symbolu_training.jepa.state_projector")

    def test_ablation_config_imports(self):
        from symbolu_training.training.conscious_generation.ablation.config import (
            AttentionAblationConfig,
        )
        assert AttentionAblationConfig.all_off().use_guna_bias is False


@pytestmark_torch
class TestWrapperConstruction:
    def test_build_on_stub(self):
        wrapper, backbone = _build_stub()
        assert wrapper.mistral_hidden_dim == 64
        assert wrapper.num_heads == 8
        assert wrapper.vocab_size == 128
        # Backbone is frozen.
        assert all(not p.requires_grad for p in backbone.parameters())

    def test_forward_shapes(self):
        wrapper, _ = _build_stub()
        ids = torch.randint(0, 128, (1, 6))
        out = wrapper(input_ids=ids, reset_state=True, return_last_hidden=True)
        assert out["logits"].shape == (1, 6, 128)
        assert out["delta_bhava"].shape[-1] == 12
        assert "adapter_gate" in out and "adapter_output_norm" in out


@pytestmark_torch
class TestGateZeroEquivalence:
    """Arm D (use_guna_bias=False) must be logit-identical to base — pre-registered K0."""

    def test_gate0_equals_base(self):
        from cg_ablation.arms import ARMS_BY_NAME, run_arm_logits

        wrapper, _ = _build_stub()
        ids = torch.randint(0, 128, (1, 8))

        base = run_arm_logits(wrapper, ARMS_BY_NAME["A_base"], ids)["logits"]
        gate0 = run_arm_logits(wrapper, ARMS_BY_NAME["D_gate0"], ids)["logits"]
        assert torch.allclose(base, gate0, atol=1e-4, rtol=1e-3), (
            "gate=0 arm is NOT logit-identical to base -> hidden coupling (K0 violated)"
        )

    def test_full_arm_runs_and_changes_or_not(self):
        # With a zero-init (untrained) phase_adapter, the full arm should ALSO equal base
        # (adapter_output == 0). This documents the 'inert until trained' property.
        from cg_ablation.arms import ARMS_BY_NAME, run_arm_logits

        wrapper, _ = _build_stub()
        ids = torch.randint(0, 128, (1, 8))
        base = run_arm_logits(wrapper, ARMS_BY_NAME["A_base"], ids)["logits"]
        full = run_arm_logits(wrapper, ARMS_BY_NAME["B_full"], ids)["logits"]
        # Untrained head => zero correction => identical. (If a trained head were loaded this
        # would differ; that path is exercised on GPU, not here.)
        assert torch.allclose(base, full, atol=1e-4, rtol=1e-3)


@pytestmark_torch
class TestStateDeltaBehaviour:
    def test_reset_state_zeroes_delta_bhava(self):
        wrapper, _ = _build_stub()
        ids = torch.randint(0, 128, (1, 6))
        out = wrapper(input_ids=ids, reset_state=True)
        assert float(out["delta_bhava"].norm().item()) == pytest.approx(0.0, abs=1e-6)

    def test_state_change_yields_nonzero_delta_bhava(self):
        wrapper, _ = _build_stub()
        torch.manual_seed(1)
        ids_a = torch.randint(0, 128, (1, 6))
        ids_b = torch.randint(0, 128, (1, 6))
        # First call resets (delta == 0), second call (no reset) should see a real delta because
        # the pooled state differs between the two different inputs.
        wrapper(input_ids=ids_a, reset_state=True)
        out2 = wrapper(input_ids=ids_b, reset_state=False)
        # Only meaningful if the two inputs actually differ.
        if not torch.equal(ids_a, ids_b):
            assert float(out2["delta_bhava"].norm().item()) > 0.0


@pytestmark_torch
class TestCGBootstrapMode:
    """ACTIVE init must escape the inert fixed point; ORIGINAL must stay the quiet baseline."""

    def _build(self, mode):
        from cg_ablation.stub_backend import StubBackbone
        from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper
        backbone = StubBackbone(64, 128, 8, seed=0)
        w = MistralCGWrapper(pretrained_model=backbone, pretrained_tokenizer=None,
                             phase_adapter_hidden=32, bootstrap_mode=mode)
        w.eval()
        return w

    def test_original_gate_and_zero_adapter(self):
        w = self._build("original")
        assert float(torch.sigmoid(w.adapter_gate).item()) == pytest.approx(0.1192, abs=1e-3)
        assert float(w.phase_adapter[-1].weight.abs().sum().item()) == 0.0

    def test_active_gate_and_nonzero_adapter(self):
        w = self._build("active")
        assert float(torch.sigmoid(w.adapter_gate).item()) == pytest.approx(0.2689, abs=1e-3)
        assert float(w.phase_adapter[-1].weight.abs().sum().item()) > 0.0

    def test_active_full_arm_changes_logits_but_gate0_still_base(self):
        from cg_ablation.arms import ARMS_BY_NAME, run_arm_logits
        w = self._build("active")
        ids = torch.randint(0, 128, (1, 8))
        base = run_arm_logits(w, ARMS_BY_NAME["A_base"], ids)["logits"]
        full = run_arm_logits(w, ARMS_BY_NAME["B_full"], ids)["logits"]
        gate0 = run_arm_logits(w, ARMS_BY_NAME["D_gate0"], ids)["logits"]
        # ACTIVE + nonzero adapter => the wrapper actually moves logits...
        assert not torch.allclose(base, full, atol=1e-4, rtol=1e-3)
        # ...but the gate=0 ablation is still logit-identical to base (K0 holds in any mode).
        assert torch.allclose(base, gate0, atol=1e-4, rtol=1e-3)


@pytestmark_torch
class TestBootstrapProbe:
    """The instrumentation reads grads/activations without affecting training."""

    def test_probe_reports_nonzero_gate_grad_in_active_mode(self):
        from cg_ablation.stub_backend import StubBackbone
        from cg_ablation.bootstrap_probe import BootstrapProbe
        from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper

        backbone = StubBackbone(64, 128, 8, seed=0)
        w = MistralCGWrapper(pretrained_model=backbone, pretrained_tokenizer=None,
                             phase_adapter_hidden=32, bootstrap_mode="active")
        probe = BootstrapProbe(w, every=1).install()
        ids = torch.randint(0, 128, (1, 8))
        out = w(input_ids=ids, reset_state=True)
        loss = out["logits"].float().pow(2).mean()  # any scalar to get grads flowing
        loss.backward()
        # gate grad should be NON-zero in active mode (adapter_output != 0 => dL/dgate != 0)
        assert w.adapter_gate.grad is not None
        assert float(w.adapter_gate.grad.abs().sum().item()) > 0.0
        probe.log(0)   # must not raise; activation norms captured by the forward hook
        probe.remove()

    def test_probe_is_inert_in_original_mode_gate_grad_zero(self):
        from cg_ablation.stub_backend import StubBackbone
        from symbolu_training.training.unified.mistral_wrapper import MistralCGWrapper

        backbone = StubBackbone(64, 128, 8, seed=0)
        w = MistralCGWrapper(pretrained_model=backbone, pretrained_tokenizer=None,
                             phase_adapter_hidden=32, bootstrap_mode="original")
        ids = torch.randint(0, 128, (1, 8))
        out = w(input_ids=ids, reset_state=True)
        out["logits"].float().pow(2).mean().backward()
        # ORIGINAL: adapter_output == 0 => dL/dgate == 0 exactly (the bootstrap-failure proof).
        g = w.adapter_gate.grad
        assert g is None or float(g.abs().sum().item()) == pytest.approx(0.0, abs=1e-8)


@pytestmark_torch
class TestCheckpointSanity:
    """Shape/key checks against a checkpoint manifest; skip if the file is absent."""

    def test_cg_head_keys_present_if_checkpoint_exists(self):
        import os
        ckpt = os.environ.get("CG_CHECKPOINT")
        if not ckpt or not Path(ckpt).exists():
            pytest.skip("CG_CHECKPOINT not set or file absent")
        from experiments.signal_gov.cg_checkpoint import (
            unwrap_state_dict,
            verify_cg_state_dict,
        )
        sd = unwrap_state_dict(torch.load(ckpt, map_location="cpu", weights_only=False))
        verdict = verify_cg_state_dict(sd)
        assert verdict.has_cg_keys, verdict.summary
