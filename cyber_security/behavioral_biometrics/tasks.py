"""Controlled-task runner.

Defines the repeatable behavioral tasks (neutral, reusable content) with their stages
and expected UI interactions, so task-induced coupling can later be conditioned out.
Each task is a SPEC a real collector follows; a scripted synthetic driver produces a
matching session for software testing (marked SYNTHETIC_TEST_ONLY).

No GUI is created here — the runner emits the task's stage markers and (for testing)
drives synthetic events through the collector. Real collection binds these specs to an
OS input-hook adapter (documented in DATA_COLLECTION_PROTOCOL.md; not implemented).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from cyber_security.behavioral_biometrics import synthetic


@dataclass
class TaskSpec:
    task_id: str
    title: str
    stages: List[str]
    expected_interactions: List[str]      # privacy-safe expected event types per stage
    neutral_prompt: str
    repeatable: bool = True
    modality_focus: str = "mixed"


REGISTRY: Dict[str, TaskSpec] = {
    "fixed_copy": TaskSpec(
        "fixed_copy", "Fixed-copy typing",
        ["warmup", "type", "review"],
        ["keyboard.key_down", "keyboard.key_up"],
        "Type the neutral pangram shown, exactly, then press Enter.",
        modality_focus="keyboard"),
    "free_response": TaskSpec(
        "free_response", "Free-response typing (no sensitive content)",
        ["prompt", "type", "submit"],
        ["keyboard.key_down", "keyboard.key_up"],
        "Describe your commute in 2-3 neutral sentences. Do not include names or secrets.",
        modality_focus="keyboard"),
    "point_click": TaskSpec(
        "point_click", "Point-and-click target acquisition",
        ["ready", "acquire", "confirm"],
        ["pointer.move", "pointer.button_down", "pointer.button_up"],
        "Click each highlighted target as it appears.",
        modality_focus="pointer"),
    "drag_drop": TaskSpec(
        "drag_drop", "Drag-and-drop",
        ["ready", "drag", "drop"],
        ["pointer.button_down", "pointer.move", "pointer.button_up"],
        "Drag each tile into its matching slot.",
        modality_focus="pointer"),
    "scroll_select": TaskSpec(
        "scroll_select", "Scroll-and-select",
        ["ready", "scroll", "select"],
        ["pointer.scroll", "pointer.move", "pointer.button_down"],
        "Scroll to the requested neutral item and select it.",
        modality_focus="pointer"),
    "mixed_workflow": TaskSpec(
        "mixed_workflow", "Mixed keyboard-and-mouse workflow",
        ["warmup", "type", "point", "review"],
        ["keyboard.key_down", "pointer.move", "pointer.button_down"],
        "Fill the neutral form: type the field, then click Next; repeat.",
        modality_focus="mixed"),
    "repeat_workflow": TaskSpec(
        "repeat_workflow", "Repeated identical workflow (within-user repeatability)",
        ["warmup", "type", "point", "review"],
        ["keyboard.key_down", "pointer.move", "pointer.button_down"],
        "Repeat the identical neutral workflow you just completed.",
        modality_focus="mixed"),
    "impostor_workflow": TaskSpec(
        "impostor_workflow", "Same-task live-impostor workflow",
        ["warmup", "type", "point", "review"],
        ["keyboard.key_down", "pointer.move", "pointer.button_down"],
        "A DIFFERENT enrolled person performs the identical workflow on the same device.",
        modality_focus="mixed"),
}


def describe(task_id: str) -> Dict[str, Any]:
    t = REGISTRY[task_id]
    return {"task_id": t.task_id, "title": t.title, "stages": t.stages,
            "expected_interactions": t.expected_interactions, "neutral_prompt": t.neutral_prompt,
            "repeatable": t.repeatable, "modality_focus": t.modality_focus}


def list_tasks() -> List[Dict[str, Any]]:
    return [describe(tid) for tid in REGISTRY]


def run_synthetic_task(task_id: str, *, participant: str, device: str, session_id: str,
                       trial_id: str, seed: int, role: str = "verification",
                       condition: str = "genuine", day: int = 0,
                       coupling_user_gain: float = 0.0, coupling_task_gain: float = 0.0,
                       **kw) -> Dict[str, Any]:
    """Produce a SYNTHETIC_TEST_ONLY session for a task (for pipeline validation).
    Modality focus tunes event volume so single-modality tasks are still schema-valid."""
    if task_id not in REGISTRY:
        raise KeyError(f"unknown task {task_id!r}")
    spec = REGISTRY[task_id]
    n_keys = {"keyboard": 200, "mixed": 160, "pointer": 40}.get(spec.modality_focus, 140)
    if condition == "live_impostor":
        role = "verification"
    return synthetic.generate_session(
        participant=participant, device=device, task_id=task_id, session_id=session_id,
        trial_id=trial_id, seed=seed, role=role, condition=condition, day=day,
        coupling_user_gain=coupling_user_gain, coupling_task_gain=coupling_task_gain,
        n_keys=n_keys, **kw)


def run_protocol(*, participant: str, device: str, seed: int,
                 tasks: Optional[List[str]] = None,
                 coupling_user_gain: float = 0.0) -> List[Dict[str, Any]]:
    """Run a per-participant task battery (synthetic) mirroring the pilot protocol:
    enrollment + repeats across days + one same-task live impostor."""
    tasks = tasks or ["fixed_copy", "point_click", "mixed_workflow", "repeat_workflow"]
    out = []
    for si, tid in enumerate(tasks):
        out.append(run_synthetic_task(
            tid, participant=participant, device=device, session_id=f"{participant}_{tid}_{si}",
            trial_id=f"{participant}_{si}", seed=seed, role="enrollment" if si == 0 else "verification",
            day=0 if si < len(tasks) // 2 else 1, coupling_user_gain=coupling_user_gain))
    out.append(run_synthetic_task(
        "impostor_workflow", participant=participant, device=device,
        session_id=f"{participant}_impostor", trial_id=f"{participant}_imp", seed=seed + 7,
        condition="live_impostor", day=1, coupling_user_gain=coupling_user_gain))
    return out
