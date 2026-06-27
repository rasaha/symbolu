"""Symbol-U controllability pilot — EXPERIMENTAL / ISOLATED.

Framing (frozen): Symbol-U = deterministic open-loop feedforward conditioning
code. The pilot tests CONTROLLABILITY (can it steer tone/affect/style along
intended axes better than matched controls?), not semantic information addition.

Does not modify or depend on the older detector files or clean_softmax. Reuses
the sibling complementarity_probe backends only to compute the Symbol-U vector.
"""
