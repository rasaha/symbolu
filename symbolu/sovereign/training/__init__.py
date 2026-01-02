"""
Sovereign-1 Training & Validation Package
==========================================

Phase 4: "The Awakening" - Training and validation logic that
"stamps" the Sovereign State into the model weights.

Components:
-----------
1. InoculationTrainer: Self-supervised state learning
   - Predicts Next-State, not just next token
   - Alpha decay scheduler (1.0 → 0.2 over 3 epochs)
   - Prevents "Signal Washing"

2. BankDisambiguationTest: The "Hello World" of Sovereign AI
   - Tests homonym disambiguation (bank = financial vs river)
   - Pass: Cosine similarity < 0.4

3. AuthorityStressTest: Brake verification
   - Feeds random/nonsense tokens
   - Pass: Authority < 0.3 and Tamas > 0.8

Usage:
------
```python
from symbolu.sovereign.training import (
    InoculationTrainer,
    AlphaScheduler,
    BankDisambiguationTest,
    AuthorityStressTest,
    run_bank_test,
    run_stress_test,
)

# Training
trainer = InoculationTrainer(model, observer, loss_fn, optimizer)
for epoch in range(num_epochs):
    for batch in dataloader:
        loss, metrics = trainer.train_step(batch)
    trainer.end_epoch()

# Validation
result = run_bank_test(model, tokenizer)
assert result.passed, "Bank disambiguation failed"

# Stress test
result = run_stress_test(model)
assert result.passed, "Authority stress test failed"
```

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 11
"""

# Inoculation Trainer
from symbolu.sovereign.training.inoculation import (
    InoculationTrainer,
    InoculationConfig,
    AlphaScheduler,
    create_inoculation_trainer,
)

# Bank Disambiguation Test
from symbolu.sovereign.training.validation import (
    BankDisambiguationTest,
    HomonymTestSuite,
    DisambiguationResult,
    run_bank_test,
)

# Stress Testing
from symbolu.sovereign.training.stress_test import (
    AuthorityStressTest,
    StressTestResult,
    run_stress_test,
)

__all__ = [
    # Inoculation Training
    'InoculationTrainer',
    'InoculationConfig',
    'AlphaScheduler',
    'create_inoculation_trainer',

    # Validation
    'BankDisambiguationTest',
    'HomonymTestSuite',
    'DisambiguationResult',
    'run_bank_test',

    # Stress Testing
    'AuthorityStressTest',
    'StressTestResult',
    'run_stress_test',
]
