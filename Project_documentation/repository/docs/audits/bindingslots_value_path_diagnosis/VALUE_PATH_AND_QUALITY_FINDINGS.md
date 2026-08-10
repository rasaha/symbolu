# Value-path and quality-interference findings (detail)

All numbers are from the byte-identically reproduced frozen snapshots (step 1200 unless noted),
computed with zero optimizer steps and unchanged model-state hashes. `chance = 1/48 ≈ 0.021`.

## H2 seed 23 — the routing-probe/eval-retrieval dissociation, localized

The persistence phase saw H2 s23 hold correct-slot probability ≈ 0.96 on the **fixed routing probe**
while end-to-end needle collapsed 1.00@700 → 0.00@1200, but could not say *why*. The diagnosis now
answers it:

- **Value is written and stays intact.** A1: cosine(m_postwrite[s*], m_query[s*]) = **0.996**,
  normalized L2 drift 0.087. No later overwrite of `s*` dominates.
- **Value is usable by the frozen readout.** A4a (u_read = m_query[s*]) → needle **1.00**; A4b
  (c_mem = W_o(m_postwrite[s*])) → needle **1.00**.
- **The failure is the read address.** Ordinary needle on the actual failed eval examples = **0.00**
  (answer-logit margin **−6.02**), and the ordinary read places only **0.579** probability on `s*`.
  Forcing r[s*]=1 (A3) → needle **1.00**, margin **+6.43**.
- **Linear vs functional.** A2 linearly decodes the collapsed slot at ~chance (0.062), yet the value
  is functionally recoverable (A4a=1.0). Per §9 this is *not* information absence; the classifier was
  corrected to key "recoverable" on the functional test (`code_correction_record.json`).

**Diagnosis: `ADDRESS_DISTRIBUTION_FAILED`.** The routing that looked healthy on the probe does not
transfer to the evaluation query distribution; the memory contents and readout are fine.

## R0 seed 23 — same failure, without the teacher

Plain frozen-CR1 R0 s23 (no persistence residual, no teacher) reproduces the identical phenotype:
ordinary needle 0.00 (margin −9.51), cosine(post, query) 0.952, read prob on `s*` 0.60, and
**oracle address / direct read / post-write restore all → 0.99** (margin +5.59). This proves the
address-distribution failure is a **general property of the frozen recipe**, not an artifact of the
H2 teacher. `ADDRESS_DISTRIBUTION_FAILED`.

## H2 seed 24 — weak clean-stable former (control interpretation)

H2 s24 is the "weak `CLEAN_STABLE`" exemplar (committed needle 0.283). Its diagnostics show the
partial retrieval is **address-independent**: read probability on `s*` is **0.01**, and forcing the
address barely moves it (0.28 → 0.36; A4a 0.36, A4b 0.38; margins stay negative). So H2 s24 does not
retrieve through slot addressing at all — it clears the clean-stable bar via a non-slot route. It is
reported `VALUE_PATH_NOT_LOCALIZED` (gray-zone retrieval; no single controlled bypass recovers it),
which is the honest outcome and a caution that a passing clean-stable count does not by itself imply a
working slot pathway.

## Quality interference — a distinct gradient conflict in addressing

At the frozen 1200 checkpoint, on fixed diagnostic batches (zero optimizer steps), the cosine between
the language-model gradient and the arm's auxiliary gradient (O1R correct-slot-probability; H2 teacher
KL) is materially negative in the **write-address projection** for every quality-failed seed and
positive in the clean controls:

| parameter group | O1R s23 (clean) | O1R s24 | O1R s25 | H2 s24 (clean) | H2 s25 |
|---|---|---|---|---|---|
| write_addr_proj (`W_wk`) | +0.24 | **−0.12** | **−0.25** | +0.10 | **−0.21** |
| read_addr_proj (`W_rq`) | −0.03 | −0.16 | −0.10 | +0.01 | −0.00 |
| write_gate | +0.06 | **−0.26** | −0.06 | +0.09 | +0.15 |
| backbone | +0.01 | −0.02 | +0.03 | +0.01 | +0.06 |
| embeddings | −0.01 | +0.01 | −0.00 | −0.03 | −0.01 |

The consistent, control-separated conflict is in **`write_addr_proj`**; `write_gate` and
`read_addr_proj` are secondary and seed-dependent. The **backbone and embeddings are not in conflict**
— so the quality regression is an addressing-parameter optimization-balance problem, not a broad
language-model interference. Each quality seed is classified `QUALITY_GRADIENT_CONFLICT_LOCALIZED`.

R0 s25 (quality-failed, plain CR1) has no persistence/teacher auxiliary; its quality failure therefore
cannot be a persistence gradient conflict and is reported `QUALITY_INTERFERENCE_NOT_LOCALIZED`.

## The two families are separate

Family 1 is a **read-address selection/generalization** failure (value + readout intact); Family 2 is
a **write-address gradient conflict** during persistent supervision. Different stages, different
parameters, different causes — consistent with the instruction not to assume a shared cause.
