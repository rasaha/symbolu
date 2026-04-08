"""
CurriculumStageManager: Orchestrates Conscious Generation Stages A→D with
PPL-gated progression.

Stage A (Backbone Stabilization): L_LM dominant; L_ont at 1%; all others = 0
Stage B (Ontology Formation):     λ_ont ramps to 0.1; λ_jepa, λ_csr = 0.01
Stage C (Primitive Specialization): All λ_f ramp to target; λ_kosha = 0.05
Stage D (Integrated Generation):  use_field_integrated_softmax = True; all λ at target

Transitions are gated by PPL stability (variance < threshold over window).

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 5 (D.7.1)
"""

from typing import Dict, List, Optional, Tuple
from .weight_scheduler import PrimitiveLambdaScheduler


# Lambda keys matching UnifiedTrainingConfig field names
LAMBDA_ONT = "lambda_ont"
LAMBDA_KOSHA = "lambda_kosha_routing"
LAMBDA_BLISS = "lambda_bliss_token"
LAMBDA_JEPA = "lambda_plausibility_token"
LAMBDA_CSR = "lambda_csr_token"
LAMBDA_VRITTI = "lambda_vritti_token"
LAMBDA_GUNA = "lambda_guna_token"
FIELD_INTEGRATED = "use_field_integrated_softmax"

ALL_LAMBDAS = [LAMBDA_ONT, LAMBDA_KOSHA, LAMBDA_BLISS, LAMBDA_JEPA,
               LAMBDA_CSR, LAMBDA_VRITTI, LAMBDA_GUNA]


class CurriculumStageManager:
    """
    Manages Stage A→D progression for Conscious Generation training.

    Uses PPL-gated transitions: a stage advance requires the validation PPL
    variance to fall below `ppl_var_threshold` over the last `stability_window`
    evaluations AND a minimum number of steps in the current stage.

    Args:
        target_lambdas: Dict of target λ values for Stage D (final values).
            Keys should match config field names. Missing keys default to 0.
        total_steps: Total training steps (used for stage duration proportions).
        stage_proportions: Tuple of (A%, B%, C%, D%) as fractions summing to 1.
            Default (0.30, 0.20, 0.25, 0.25) per spec.
        ppl_var_threshold: Maximum PPL variance for stage transition.
        stability_window: Number of evaluations over which to check PPL stability.
        ramp_mode: Ramp mode for PrimitiveLambdaScheduler ('linear', 'cosine', 'step').
    """

    STAGE_A = "A_BACKBONE"
    STAGE_B = "B_ONTOLOGY"
    STAGE_C = "C_PRIMITIVE"
    STAGE_D = "D_INTEGRATED"

    STAGES = [STAGE_A, STAGE_B, STAGE_C, STAGE_D]

    def __init__(
        self,
        target_lambdas: Dict[str, float],
        total_steps: int,
        stage_proportions: Tuple[float, float, float, float] = (0.30, 0.20, 0.25, 0.25),
        ppl_var_threshold: float = 0.5,
        stability_window: int = 5,
        ramp_mode: str = "cosine",
    ):
        self.target_lambdas = target_lambdas
        self.total_steps = total_steps
        self.stage_proportions = stage_proportions
        self.ppl_var_threshold = ppl_var_threshold
        self.stability_window = stability_window

        # Compute stage boundaries
        cumulative = 0.0
        self.stage_boundaries = {}
        for stage, prop in zip(self.STAGES, stage_proportions):
            start = int(cumulative * total_steps)
            cumulative += prop
            end = int(cumulative * total_steps)
            self.stage_boundaries[stage] = (start, end)

        # State
        self.current_stage = self.STAGE_A
        self.current_stage_idx = 0
        self.ppl_history: List[float] = []
        self.stage_history: List[Tuple[int, str]] = [(0, self.STAGE_A)]
        self.stage_entry_step = 0  # global_step when current stage began
        self._field_integrated_active = False

        # Lambda scheduler
        self.scheduler = PrimitiveLambdaScheduler(ramp_mode=ramp_mode)
        self._configure_stage_a()

    def _get_target(self, key: str) -> float:
        """Get the target lambda for a key, defaulting to 0."""
        return self.target_lambdas.get(key, 0.0)

    def _ramp_steps_for_stage(self, stage: str) -> int:
        """Get the number of ramp steps for a stage (80% of stage duration)."""
        start, end = self.stage_boundaries[stage]
        return max(int(0.8 * (end - start)), 1)

    def _configure_stage_a(self):
        """Stage A: Backbone Stabilization — L_LM dominant, λ_ont at 1%."""
        for key in ALL_LAMBDAS:
            self.scheduler.set_immediate(key, 0.0)
        # Only L_ont at 1%
        self.scheduler.set_immediate(LAMBDA_ONT, 0.01)
        self._field_integrated_active = False

    def _configure_stage_b(self, global_step: int):
        """Stage B: Ontology Formation — ramp λ_ont to target; weak JEPA/CSR."""
        ramp = self._ramp_steps_for_stage(self.STAGE_B)
        self.scheduler.set_schedule(LAMBDA_ONT, 0.01, max(self._get_target(LAMBDA_ONT), 0.01), ramp, global_step)
        self.scheduler.set_schedule(LAMBDA_JEPA, 0.0, 0.01, ramp, global_step)
        self.scheduler.set_schedule(LAMBDA_CSR, 0.0, 0.01, ramp, global_step)
        # Others stay at 0
        for key in [LAMBDA_KOSHA, LAMBDA_BLISS, LAMBDA_VRITTI, LAMBDA_GUNA]:
            self.scheduler.set_immediate(key, 0.0)
        self._field_integrated_active = False

    def _configure_stage_c(self, global_step: int):
        """Stage C: Primitive Specialization — all λ_f ramp to target; Kosha begins."""
        ramp = self._ramp_steps_for_stage(self.STAGE_C)
        # Ramp all primitives from current value to target
        for key in ALL_LAMBDAS:
            current = self.scheduler.get(key, 0.0)
            target = self._get_target(key)
            if target > 0:
                self.scheduler.set_schedule(key, current, target, ramp, global_step)
        # Kosha routing starts at 0.05 target (per spec); ramp from current value
        kosha_current = self.scheduler.get(LAMBDA_KOSHA, 0.0)
        kosha_target = max(self._get_target(LAMBDA_KOSHA), 0.05)
        self.scheduler.set_schedule(LAMBDA_KOSHA, kosha_current, kosha_target, ramp, global_step)
        self._field_integrated_active = False

    def _configure_stage_d(self, global_step: int):
        """Stage D: Integrated Generation — field-integrated softmax ON; all λ at target."""
        ramp = self._ramp_steps_for_stage(self.STAGE_D)
        for key in ALL_LAMBDAS:
            current = self.scheduler.get(key, 0.0)
            target = self._get_target(key)
            self.scheduler.set_schedule(key, current, target, ramp, global_step)
        self._field_integrated_active = True

    def _is_ppl_stable(self) -> bool:
        """Check if PPL is stable enough for stage transition."""
        if len(self.ppl_history) < self.stability_window:
            return False
        recent = self.ppl_history[-self.stability_window:]
        mean_ppl = sum(recent) / len(recent)
        if mean_ppl <= 0:
            return False  # Pathological PPL, do not treat as stable
        variance = sum((p - mean_ppl) ** 2 for p in recent) / len(recent)
        return variance < self.ppl_var_threshold

    def _min_steps_in_stage(self) -> int:
        """Minimum steps before stage transition is allowed."""
        start, end = self.stage_boundaries[self.current_stage]
        return max(int(0.5 * (end - start)), 100)

    def _advance_stage(self, global_step: int, val_ppl: float, reason: str) -> str:
        """Advance to the next stage. Returns transition message."""
        old_stage = self.current_stage
        self.current_stage_idx += 1
        self.current_stage = self.STAGES[self.current_stage_idx]
        self.stage_entry_step = global_step
        self.stage_history.append((global_step, self.current_stage))

        # Configure new stage
        configurators = {
            self.STAGE_B: self._configure_stage_b,
            self.STAGE_C: self._configure_stage_c,
            self.STAGE_D: self._configure_stage_d,
        }
        configurators[self.current_stage](global_step)

        return (f"[Conscious Gen Curriculum] Stage transition: {old_stage} -> "
                f"{self.current_stage} at step {global_step} "
                f"(PPL={val_ppl:.2f}, {reason})")

    def update(self, val_ppl: float, global_step: int) -> Optional[str]:
        """
        Update with new validation PPL. May trigger stage transition.

        Transitions use two paths:
        1. PPL-gated: advance when PPL variance < threshold over stability_window
        2. Time-based fallback: advance when global_step passes the next stage
           boundary, preventing the PPL gate from blocking indefinitely in
           short training runs.

        Args:
            val_ppl: Current validation perplexity.
            global_step: Current training step.

        Returns:
            Transition message if stage changed, None otherwise.
        """
        self.ppl_history.append(val_ppl)
        if len(self.ppl_history) > 200:
            self.ppl_history = self.ppl_history[-200:]

        # Check for stage advancement
        if self.current_stage_idx >= len(self.STAGES) - 1:
            return None  # Already at Stage D

        # Time-based fallback: if global_step has passed the NEXT stage's
        # start boundary, advance unconditionally.  This prevents the PPL
        # gate from blocking progress indefinitely when the stability_window
        # requires more evaluations than the stage allows.
        messages = []
        while self.current_stage_idx < len(self.STAGES) - 1:
            next_stage = self.STAGES[self.current_stage_idx + 1]
            next_start, _ = self.stage_boundaries[next_stage]
            if global_step >= next_start:
                messages.append(self._advance_stage(global_step, val_ppl, "time-based"))
            else:
                break

        if messages:
            return "\n".join(messages)

        # PPL-gated path: advance if stable
        steps_in_stage = global_step - self.stage_entry_step
        if steps_in_stage < self._min_steps_in_stage():
            return None  # Not enough time in current stage

        if not self._is_ppl_stable():
            return None  # PPL not stable yet

        return self._advance_stage(global_step, val_ppl, "PPL-stable")

    def step(self, global_step: int) -> Dict[str, float]:
        """
        Update lambda values for current step.

        Args:
            global_step: Current training step.

        Returns:
            Dict of current lambda values (keys match config field names).
        """
        return self.scheduler.step(global_step)

    @property
    def use_field_integrated_softmax(self) -> bool:
        """Whether field-integrated softmax should be active (Stage D)."""
        return self._field_integrated_active

    def get_diagnostics(self) -> Dict[str, object]:
        """Get diagnostic info about current curriculum state."""
        result = {
            "cg_curriculum_stage": self.current_stage,
            "cg_curriculum_stage_idx": self.current_stage_idx,
            "cg_curriculum_stage_entry_step": self.stage_entry_step,
            "cg_field_integrated_active": self._field_integrated_active,
        }
        result.update(self.scheduler.get_diagnostics())
        return result

    def get_state(self) -> Dict[str, object]:
        """Serialize curriculum state for checkpoint saving."""
        return {
            "current_stage": self.current_stage,
            "current_stage_idx": self.current_stage_idx,
            "stage_entry_step": self.stage_entry_step,
            "field_integrated_active": self._field_integrated_active,
            "ppl_history": list(self.ppl_history),
            "stage_history": list(self.stage_history),
            "scheduler_values": dict(self.scheduler._values),
        }

    def load_state(self, state: Dict[str, object]):
        """Restore curriculum state from checkpoint."""
        self.current_stage = state["current_stage"]
        self.current_stage_idx = state["current_stage_idx"]
        self.stage_entry_step = state["stage_entry_step"]
        self._field_integrated_active = state["field_integrated_active"]
        self.ppl_history = list(state.get("ppl_history", []))
        self.stage_history = list(state.get("stage_history", []))
        if "scheduler_values" in state:
            self.scheduler._values.update(state["scheduler_values"])
