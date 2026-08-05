# E1 protocol-lock — load-bearing design decisions (resolved on non-reserved fixtures)

Per the merged preregistration, load-bearing choices left open are resolved here on **non-reserved**
development fixtures and frozen before any reserved-seed run. Nothing in this document consults reserved
identities, combinations, or seeds.

## D1 — shared compositional task (why B0 is re-instantiated, not the old checkpoint)

The merged E1 probe requires **paraphrase** and **unseen-identity** generalization. The original
BindingSlots needle task (single entity token → single value token) **cannot express** paraphrase or
compositional identity, so the literal 2M-param needle checkpoint cannot be evaluated on it. Therefore:

- **B0 is the anonymous-slot *recipe* instantiated on the shared compositional task at 32-slot density**
  — content-addressed **soft write / soft read** over 32 anonymous slots, **no explicit-key
  supervision**, trained with its **own** next-value-token objective. It is **not** modified to resemble
  E1 and receives **no** address supervision.
- **E1 is the explicit-key dual-encoder** on the **identical** episodes.
- Both models consume byte-identical episodes; the only differences are the frozen architectural bundle
  and (for E1) the contrastive address supervision that anonymous slots structurally cannot express.

This is the only coherent way to compare "anonymous slots" vs "explicit keys" on a task carrying the
semantic structure the probe demands. It is documented here and frozen before reserved execution.

## D2 — semantic identity = composition of primitives; meaning is primitive-level

- **Entity primitives** and **attribute primitives** are shared, seen-in-training atoms. Each primitive
  has a small **synonym group** of distinct surface tokens.
- An **identity** = an unordered pair of entity primitives; an **attribute** = one attribute primitive.
- A **fact** = (identity, attribute) → value token.
- The **stored key** renders identity+attribute in a **canonical** surface form (synonym index 0).
- The **query** renders the **same** identity+attribute in a **different** surface form (non-zero synonym
  indices, reordered, with filler/distractor tokens) and shares **no** surface token verbatim with its
  key for the matched primitives. Success therefore requires learning **synonym→primitive** grouping and
  **composition** — i.e., semantic matching, not surface-token equality (anti-shortcut by construction).
- **Unseen identity (G1)** = a novel **combination** of seen primitives (compositional generalization);
  primitives/synonyms are seen so both models can embed them, but the combination is held out.

## D3 — frozen E1 architecture (dual encoder)

- Shared token embedding table (dim d); **separate** key- and query-projection heads; L2-normalized
  embeddings; **cosine** score.
- **Learned null key**: a single trainable normalized vector added as candidate index N (no-match).
- Loss: InfoNCE-style softmax cross-entropy over the N episode keys + null, temperature τ (frozen on dev).
- Inference: **hard top-1** over {N keys, null}; null ⇒ abstain; else return the selected key's value.
- Value: each key carries a value token id; **predicted value = value of the hard-top-1 key**. No soft
  value mixing; no Gumbel/STE/top-k.

## D4 — frozen B0 architecture (anonymous slots)

- Content-addressed memory: 32 slots × d. Write: soft address = softmax over slots of a learned
  projection of each fact's representation; values accumulated softly. Read: soft address from the query
  representation; `u_read = Σ_j r_j M_j`; decode to value logits. Trained with cross-entropy on the value
  token only — **no address supervision, no explicit key, no abstention head** (anonymous slots do not
  natively abstain; on no-match queries B0 selects its nearest slot, the expected anonymous-slot
  weakness, reported honestly as false-accept).

## D5 — determinism

CPU fp32, `threads=4`, sequential; all RNG seeded (`random`, `torch.manual_seed`); deterministic init;
no dropout; fixed data/candidate order per seed. Repeated fixture runs must be byte-identical
(model-state hash, loss trajectory, predictions, metrics, artifact hashes).

## D6 — reserved vs non-reserved

Identity-combination pools are partitioned into **train / development / final(reserved)** deterministically
and disjointly. Gate numbers, τ, no-match hyperparameters, and compute bounds are frozen using the
**development** pool only. The **final(reserved)** pool and the reserved seed set are **never** read
during Stage 2. A mechanical protocol-lock verifier asserts no reserved seed/identity was touched.
