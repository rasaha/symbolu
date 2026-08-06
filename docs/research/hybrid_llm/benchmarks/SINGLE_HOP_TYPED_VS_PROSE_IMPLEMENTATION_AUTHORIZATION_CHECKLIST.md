# Single-hop typed-vs-prose — implementation authorization checklist

Overall verdict: **`IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`**.

| # | Authorization requirement | Status |
|---|---|---|
| 1 | One isolated implementation package | ✅ `experiments/single_hop_typed_vs_prose/` only |
| 2 | Existing generic backbone reused unmodified | ✅ plain `SoftmaxTransformerLM` / `BackboneConfig` only |
| 3 | Non-memory model path | ✅ no BindingSlots, E1, recurrent state, prefix memory, or external table |
| 4 | No bounded quadratic relation/event reader | ✅ ordinary causal softmax token attention only |
| 5 | Same tokenizer and input channel | ✅ one fixed reversible lexical tokenizer, no arm marker or typed-only embedding |
| 6 | Tokenizer mapping frozen | ✅ ASCII 0–127; PAD/BOS/EOS 128/129/130; 69 protocol lexemes 131–199 |
| 7 | Tokenizer is data-independent | ✅ no fitting, BPE training, hashing, unknown substitution, or corpus-derived vocabulary |
| 8 | Same model and parameter count | ✅ one frozen class/config/head for B0 and B1 |
| 9 | One shared structured-output channel | ✅ autoregressive canonical seven-field JSON through the tied vocabulary head |
| 10 | Model recipe frozen | ✅ 64D, 2 layers, 4 heads, 256 FFN, 1024 sequence, zero dropout |
| 11 | Token budgets frozen | ✅ 512 input including shared marker; 384 output; fail closed; no truncation |
| 12 | Objective frozen | ✅ output-token and EOS next-token loss only; prompt targets masked |
| 13 | Optimizer frozen | ✅ AdamW 3e-4, betas 0.9/0.95, eps 1e-8, wd 0.01, clip 1.0 |
| 14 | Update and batch limits frozen | ✅ batch 8; at most 2000 updates per arm/seed; no restart/extension |
| 15 | Canonical graph and fact hash required | ✅ both arms derive from one graph and must share SHA-256 digest |
| 16 | S1–S8 generator authorized | ✅ deterministic, local-RNG, in-memory implementation only |
| 17 | A1–A6 transformations authorized | ✅ evaluation-only with explicit causal expectation metadata |
| 18 | Shared evaluator required | ✅ one strict parser/evaluator; no arm-specific post-processing |
| 19 | Determinism evidence required | ✅ serializer, tokenizer, init, order, evaluator, import-RNG, and digest checks |
| 20 | Reserved seeds hard-gated | ✅ smoke/dev/final seeds rejected absent separate authorization token |
| 21 | Unit-test seed separated | ✅ non-benchmark test seed only; ephemeral fixtures are not evidence |
| 22 | Dedicated CI required | ✅ implementation unit workflow plus existing CI |
| 23 | No import-time side effects | ✅ no generation, training, writes, network, RNG mutation, or model initialization on import |
| 24 | No benchmark execution authorized | ✅ no smoke, development, or final seed may run |
| 25 | No scientific verdict authorized | ✅ no typed-structure advantage claim or protocol-lock claim |
| 26 | Standing invariants preserved | ✅ `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED` |

The subsequent implementation PR must remain draft and unmerged until independently audited. Passing unit
checks demonstrates only mechanical completeness; it does not authorize any benchmark run or scientific
conclusion.
