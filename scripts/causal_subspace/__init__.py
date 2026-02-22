"""
Causal Subspace Extraction & Validation Protocol
=================================================

An advanced mechanistic interpretability pipeline to causally isolate
and validate structural subspaces inside the hidden states of a
pretrained transformer.

Modules:
    data_collection   -- Part 1: Load model, extract hidden states per layer
    structural_labels -- Part 2: Attach structural metadata (dep parse, coref)
    disentanglement   -- Part 3: PCA baseline + SAE + contextual clustering
    mdl_probing       -- Part 4: Minimum Description Length probing
    causal_intervention -- Part 5: Activation patching (interchange intervention)
    trajectory        -- Part 6: Layer trajectory mapping
"""

__all__ = [
    "data_collection",
    "structural_labels",
    "disentanglement",
    "mdl_probing",
    "causal_intervention",
    "trajectory",
    "ontology_alignment",
]
