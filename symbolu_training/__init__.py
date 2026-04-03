"""
Symbolu Training — Training-time modules moved out of core.

These modules are used during model training, not runtime inference or
agentic governance. They have been extracted from symbolu/ to clarify
the boundary between training infrastructure and the runtime product.

Modules:
    - training: Training infrastructure, data generation, unified training loop
    - jepa: Ontological State Predictor with Phase Attention
    - losses: Custom loss functions (Kosha gyroscope, phase corrector)
    - diagnostics: Training diagnostic logger (reality rips, fluidity events)
    - monitors: Graduation monitor for training progress
"""
