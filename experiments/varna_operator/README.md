# experiments/varna_operator — deterministic-operator scaffold (synthetic only)

Minimal, isolated scaffold for the **vṛtti-as-deterministic-operator** branch of
`varna_lens/THEORY_VRTTI_KERNEL_FORMALIZATION.md`. Each varṇa maps to a deterministic
operator (a d×d matrix); a word's representation is the **ordered operator product**.
Deterministic operators are the **point-mass / zero-conditional-entropy special case** of
the Markov-kernel frame — the kernel branch is **not** implemented here.

**This is scaffolding only:** synthetic toy operators, synthetic tests, a guarded runner.
**No real varṇa table, no fit, no result, no semantic claim, no validation.** Stage A is
neither imported nor modified.

## What is here

| file | role |
|---|---|
| `operators.py` | synthetic seeded **orthogonal** operator table; **ordered product** `word_operator`; `word_representation`; order-invariant baselines (`bag_operator_sum`, `additive_vector_model`). Reuses `experiments/common.stats`. |
| `run_varna_operator.py` | guarded entrypoint — emits **NOT_RUN** (no real table); computes nothing. |
| `test_varna_operator.py` | **synthetic** tests (19 checks). |

## What the tests demonstrate (synthetic)

- **order sensitivity** — `R([a,b]) ≠ R([b,a])` for non-commuting operators;
- **associativity** — `word_operator([a,b,c]) = M_c·M_b·M_a` and grouping is irrelevant;
- **non-commutativity** — `M_a·M_b ≠ M_b·M_a`;
- **identity behavior** — inserting the identity operator leaves the product unchanged; empty word = `I`;
- **deterministic reproducibility** — same seed → identical operators and representations;
- **anagram discrimination** — the additive/bag models (order-invariant) give **identical**
  representations for anagrams, while the **operator product distinguishes** them.

## Operator source

The scaffold uses **synthetic toy operators** (`random_operators`, seeded orthogonal
matrices). A frozen operator table (e.g. a Stage-A `M_σ` table) could be plugged in through
the same `op_map` interface **without modification**, but this scaffold neither imports nor
reads Stage A.

## Deliberately NOT done

- No real varṇa→operator table; no `word_formation_reading` / lexicon coupling.
- No Markov-kernel (stochastic) implementation.
- No fit, no verdict, no semantic claim, no validation.

## Run

```bash
python3 experiments/varna_operator/test_varna_operator.py   # 19 synthetic checks
python3 experiments/varna_operator/run_varna_operator.py    # prints NOT_RUN
```

> structure, not validated meaning.
