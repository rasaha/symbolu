"""Single-checkpoint paired-evidence orchestration. Torch-free and mechanically testable.

Enforces: ONE frozen checkpoint per seed, evaluated byte-identically on P0 and R1-R12; no optimizer step,
tuning, or checkpoint selection between P0 and R1-R12. If P0 is not established, R1-R12 outputs are stamped
NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION and excluded from every reasoning verdict.

`checkpoint` is any object exposing `.digest() -> str` (a torch model wrapped via model.parameter_digest,
or a fake blob in tests). `p0_eval(checkpoint) -> dict` must return {'established': bool, ...};
`r_eval(checkpoint) -> dict` returns the R1-R12 artifacts.
"""
from __future__ import annotations

NON_ADMISSIBLE = "NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION"


class CheckpointIdentityError(RuntimeError):
    """Raised if the checkpoint digest changes between P0 and R1-R12 (invariant violation)."""


def run_single_checkpoint(checkpoint, p0_eval, r_eval) -> dict:
    frozen_digest = checkpoint.digest()

    p0 = p0_eval(checkpoint)
    if checkpoint.digest() != frozen_digest:
        raise CheckpointIdentityError("checkpoint mutated during P0 evaluation")

    r = r_eval(checkpoint)
    if checkpoint.digest() != frozen_digest:
        raise CheckpointIdentityError("checkpoint mutated during R1-R12 evaluation")

    established = bool(p0.get("established"))
    result = {
        "parameter_digest": frozen_digest,
        "p0": p0,
        "r1_r12": r,
        "reasoning_admissible": established,
    }
    if not established:
        result["admissibility_stamp"] = NON_ADMISSIBLE
        result["reasoning_verdict_inputs_excluded"] = True
    return result
