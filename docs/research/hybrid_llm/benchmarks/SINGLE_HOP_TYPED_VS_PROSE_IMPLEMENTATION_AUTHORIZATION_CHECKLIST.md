# Single-hop typed-vs-prose — implementation authorization checklist

Overall verdict: **`IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`**.

| # | Authorization requirement | Status |
|---|---|---|
| 1 | One isolated implementation package | ✅ `experiments/single_hop_typed_vs_prose/` only |
| 2 | Existing generic backbone reused unmodified | ✅ plain `SoftmaxTransformerLM` / `BackboneConfig` only |
| 3 | Non-memory model path | ✅ no BindingSlots, E1, recurrent/prefix memory, retrieval table, or external model |
| 4 | No bounded quadratic relation/event reader | ✅ ordinary causal softmax token attention only |
| 5 | S1 answer-ID leakage closed | ✅ `select_entity` query contains criteria and null answer ID |
| 6 | Task-label collision closed | ✅ explicit shared operation vocabulary in B0 and B1 |
| 7 | Split leakage prohibited | ✅ reason code derives from operation/outcome, never hidden split identity |
| 8 | S3 validity coverage | ✅ supported and unsupported proposed targets required |
| 9 | A6 non-ambiguity | ✅ decoy is high-similarity but not a second exact answer |
| 10 | Same tokenizer and input channel | ✅ one fixed reversible lexical tokenizer; no arm marker or typed-only embedding |
| 11 | Tokenizer mapping frozen | ✅ ASCII 0–127; PAD/BOS/EOS 128/129/130; 74 lexemes 131–204 |
| 12 | Tokenizer is data-independent | ✅ no fitting, BPE training, hashing, unknown substitution, or corpus vocabulary |
| 13 | Same model and parameter count | ✅ one frozen class/config/head for B0 and B1 |
| 14 | One shared structured-output channel | ✅ canonical seven-field JSON through tied vocabulary head |
| 15 | Model recipe frozen | ✅ vocabulary 205; 64D; 2 layers; 4 heads; 256 FFN; 1024 sequence; zero dropout |
| 16 | Token budgets frozen | ✅ 512 input including common marker; 384 output; fail closed; no truncation |
| 17 | Objective frozen | ✅ output-token and EOS next-token loss only; prompt targets masked |
| 18 | Optimizer frozen | ✅ AdamW 3e-4, betas 0.9/0.95, eps 1e-8, wd 0.01, clip 1.0 |
| 19 | Update and batch limits frozen | ✅ batch 8; at most 2000 updates per arm/seed; no restart/extension |
| 20 | Canonical graph and fact hash required | ✅ both arms derive from one graph and share SHA-256 digest |
| 21 | S1–S8 generator authorized | ✅ deterministic, local-RNG, in-memory implementation only |
| 22 | A1–A6 transformations authorized | ✅ evaluation-only with explicit represented-output behavior |
| 23 | Shared evaluator required | ✅ one strict parser/evaluator; no arm-specific post-processing |
| 24 | Determinism evidence required | ✅ serializer, tokenizer, init, order, evaluator, import-RNG, and digest checks |
| 25 | Reserved seeds hard-gated | ✅ smoke/dev/final rejected absent separate exact authorization token |
| 26 | Unit-test seed separated | ✅ non-benchmark test seed only; ephemeral fixtures are not evidence |
| 27 | Dedicated CI required | ✅ implementation unit workflow plus existing CI |
| 28 | No import-time side effects | ✅ no generation, training, writes, network, RNG mutation, or model initialization |
| 29 | No benchmark execution authorized | ✅ no smoke, development, or final seed may run |
| 30 | No scientific verdict authorized | ✅ no typed-structure advantage or protocol-lock claim |
| 31 | Standing invariants preserved | ✅ `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED` |

The subsequent implementation PR must remain draft and unmerged until independently audited. Mechanical tests
demonstrate implementation integrity only and authorize no benchmark execution or scientific conclusion.
