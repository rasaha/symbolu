"""
PCAM runtime integrations (Phase 2).

This subpackage holds thin adapters that bind ``KVCachePolicy`` to
real inference runtimes. Each runtime gets its own module under
``simulator/pcam/integrations/<runtime>.py``.

Phase 2 ships only the vLLM adapter:

    from simulator.pcam.integrations.vllm import PCAMEvictor

Additional adapters (SGLang, TGI, DeepSpeed-Inference) are deliberately
deferred until a real design partner asks for them. The Phase 2
non-goal is to ship adapters speculatively.

All adapters in this subpackage MUST delegate to
``simulator.pcam.kv_policy.KVCachePolicy`` for scoring, sketch updates,
sink pinning, and victim selection. There is no second policy
implementation, no bridge class, and no separate scoring path.
"""
