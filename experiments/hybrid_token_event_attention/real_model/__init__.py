"""
RM1 — Real-Model Validation of the Dual-Domain Hybrid LLM.

This is an *additive* package. It replaces the local token-model stand-in used in the frozen
controlled study (`experiments/hybrid_token_event_attention/`) with an **actual open-weight causal
language model** loaded through Hugging Face Transformers, and drives that real model through the
same frozen external governed architecture:

    real token-language model
        -> provisional evidence extraction
        -> deterministic validation and normalization
        -> exact EvidenceRecords
        -> P5 smallest-sufficient-set selection
        -> contract-aware reasoning router
        -> deterministic reasoning by default
        -> bounded event attention only for relational contracts
        -> typed evidence-linked findings
        -> real token-model explanation
        -> TAP or an explicitly labelled TAP-faithfulness evaluation

RM1 does NOT fine-tune the base model, and does NOT add FSCS, LoRA, adapters, Phase recurrence, or
any other architecture change. It isolates the single effect of swapping the token stand-in for a
real frozen model.

Frozen components (event schema, normalization bridge, P5 selector, deterministic reasoner, H2/H3
event modules, causal controls, datasets) are IMPORTED from the parent package and never modified.

Honesty boundary: if a genuine open-weight model cannot be loaded (missing torch / transformers /
accelerate / safetensors, no suitable hardware, no weights, or no network access) the harness
terminates with ``RESOURCE_BLOCKED`` and exact remediation steps. It never substitutes the old
stand-in and calls the output a real-model result.
"""

RM1_VERSION = "rm1.0.0"
