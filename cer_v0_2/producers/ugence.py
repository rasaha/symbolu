"""Native Ugence CER V0.2 producer (both profiles). Emits before execution; owns
no authorization/token/execution."""
from __future__ import annotations

from typing import Union

from ..actuation import EnvelopeContext, RolloutActuation, ScaleActuation, assemble_cer

Actuation = Union[ScaleActuation, RolloutActuation]


class UgenceCERProducer:
    RUNTIME = "ugence-agent-runtime"
    RUNTIME_VERSION = "0.2.0"
    MODEL = "mistral-cg"
    MODEL_PROVIDER = "ugence"

    def _objective(self, act: Actuation) -> str:
        if isinstance(act, ScaleActuation):
            return (f"raise availability of {act.namespace}/{act.deployment} "
                    f"to {act.to_replicas} replicas")
        return (f"roll out image {act.image_digest[:19]}… to "
                f"{act.namespace}/{act.deployment}")

    def propose(self, ctx: EnvelopeContext, act: Actuation) -> dict:
        # runtime-owned reasoning: understand -> plan -> select tool -> propose
        provenance = {
            "runtime": self.RUNTIME, "runtime_version": self.RUNTIME_VERSION,
            "model_provider": self.MODEL_PROVIDER, "model": self.MODEL,
            "planner": "ugence.deterministic.htn", "objective": self._objective(act),
            "reasoning_trace_ref": "ugence://trace", "adapter_version": "native",
            "explanation": f"Proposed {act.PROFILE} on {act.namespace}/{act.deployment}.",
        }
        return assemble_cer(act.PROFILE, ctx, act.actuation_block(), provenance)
