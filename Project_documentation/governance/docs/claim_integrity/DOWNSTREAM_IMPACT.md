# Downstream-Impact Experiment (Phase 18 — primary phase)

*`claim_integrity/downstream.py` + `eval_downstream.py` → `eval_results/downstream.json`. Each method's
decomposition is passed into a READ-ONLY adapter that maps it to downstream governance outcomes.
EvidenceAssurance and AssertionGate are **not modified**; the adapter models their behavior from the
corpus's per-claim `downstream_consequence`. The primary safety endpoint is **unsafe delivery**: a
decomposition that causes a claim which should be withheld to be delivered-as-supported.*

## Model

A gold claim marked `unsafe_allow` is one whose fragile dimension, **if preserved**, makes the thin
gate withhold (the faithful claim is hedged / negated / conditional / attributed / "no evidence" / …).
If decomposition **drops** that dimension, the altered claim is delivered-as-supported → **unsafe
delivery**. A dangling pronoun does not drop a dimension but **alters the evidence query** (ambiguous
subject) → reported separately as `evidence_query_altered`. An omitted claim is never governed →
unsafe. Drift on a `conservative_block` claim → false rejection.

## Result (ci_corpus_v1, 1144 gold claims)

| Method | unsafe delivery ↓ | false rejection ↓ | evidence-query altered ↓ |
|---|--:|--:|--:|
| Q_oracle | 0.000 | 0.000 | 0.000 |
| **B_sentence_split** | **0.068** | 0.068 | 0.091 |
| **P_claim_integrity** | **0.068** | 0.068 | **0.000** |
| L_hybrid (sim) | 0.080 | 0.068 | 0.091 |
| I_llm_simple (sim) | 0.122 | 0.068 | 0.091 |
| R_learned_comparator (sim) | 0.147 | 0.068 | 0.091 |
| N_minimal_split | 0.250 | 0.068 | 0.000 |
| A_preserve_whole | 0.454 | 0.068 | 0.000 |
| C_clause / O_aggressive | 0.568 | 0.000 | 0.091 |
| D_dependency / E_srl (sim) | 0.591 | 0.023 | 0.091 |
| F_openie / G_rule_spo (sim) | 0.864 | 0.023 | 0.091 |

## What this decides

**The decomposition METHOD matters enormously — but the component does not beat sentence splitting on
the primary endpoint.** Three findings, in order of confidence:

1. **Triple/parser/aggressive extraction is dangerous.** OpenIE/SPO cause **0.864** unsafe delivery —
   they strip the very dimensions (negation, modality, qualifier, scope) whose loss flips a withhold to
   an allow. Any system that decomposes this way ships unsafe claims at scale. This is the strongest,
   most robust result of the study.

2. **On unsafe delivery, the reference component ties sentence splitting (0.068 = 0.068).** Both retain
   modifiers, so both withhold the hedged/negated/conditional claims correctly. The shared 0.068 is the
   78 ADVERSARIAL_SCOPE conjunctions that **both** under-split (dropping the exception-bearing second
   claim) — an error only the oracle's correct 2-way split avoids. **H0-1 is not rejected on the
   primary safety endpoint.**

3. **The component's sole distinct benefit is evidence-query integrity.** It drives
   `evidence_query_altered` from **0.091 → 0.000** by resolving dangling pronouns, so downstream
   evidence retrieval runs on a concrete subject rather than an ambiguous "it". This is a real
   governance harm avoided — a claim evaluated against evidence for the wrong/undetermined entity — but
   it is a **secondary** endpoint, not unsafe delivery, and this model does not count it as a definite
   unsafe allow.

**Preserve-whole is unsafe here (0.454), not safe.** Its adversarial-drift safety (Phase 17) does not
survive contact with completeness: by refusing to decompose, it leaves multi-claim outputs with
ungoverned claims that pass unchecked. "Don't decompose" trades meaning-inversion risk for
ungoverned-claim risk, and downstream the latter dominates.

## Honest verdict for the architecture

The experiment supports a **narrow** conclusion: *use a preservation-first decomposition (never triple
extraction), and resolve references* — but it does **not** support a heavyweight distinct component
over sentence-splitting-plus-checks. The component's measured advantage over sentence splitting is
reference resolution and non-assertive filtering; its per-dimension preservation modules match, but do
not beat, what sentence-splitting already achieves by simply not stripping. The unsafe-delivery gap
that remains (0.068, the adversarial under-split) is unsolved by **both** and is the real target for
any future work.
