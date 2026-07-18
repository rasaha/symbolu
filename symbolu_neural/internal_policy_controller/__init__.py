"""Internal draft->policy->final-answer Symbol-U controller — EXPERIMENTAL / ISOLATED.

A critique-and-revise (self-refinement) loop whose critic is Symbol-U/PSE instead
of the LLM itself. Measurement prototype only: no weights changed, no Transformer
trained, no decoder built. Isolated from clean_softmax / complementarity_probe /
controllability_pilot / api_control_protocol / Hybrid-Phase-Sovereign-JEPA. Reuses
the complementarity_probe backends only to compute the Symbol-U state of a draft.
"""
