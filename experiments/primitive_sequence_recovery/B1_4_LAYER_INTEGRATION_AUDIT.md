# B1.4 — Layer-Integration Audit (L1 / L2 / L3)

**Status:** Integration audit (docs-only). Not a run, not a dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.
**No meaning validated. No dataset built. Nothing run or scored. B1.3 v3 remains parked.**
**Track B remains blocked. Structure, not validated meaning.**

Audited artifact: `B1_4_WORD_BLIND_ATTRIBUTE_VALIDATION_DESIGN.md` (pipeline §6, E-gate §4, probe §10).

---

## 1. Question

Does the B1.4 design **operationally integrate** the three layers — L1 structural operators, L2 latent
semantic formation `F`, L3 decoders — plus the validation layer? Or does it only **name** them while, in
practice, running as `varṇa split → attribute table → KCPR pole → generator → judge`, with **no implemented L2
formation function `F`**?

---

## 2. Layer definitions (restated)

- **L1 — structural operator layer (frozen):** `t_i = M_{σ_i} · t_{i−1}`. Operator composition over varṇas.
  Structural only (Stage A: G1/G2/G3 pass, G4 not validated). Not a semantic claim.
- **L2 — latent semantic formation (candidate):** `z = F(M_{σ_1}, …, M_{σ_n}, s_0) ∈ S`. `F` must be
  gloss-independent, **non-additive** (order/composition matters), **operator-derived** (a function of the L1
  operators, not a hand-tuned table beside them), and baseline-testable. `F` is not yet fixed or validated.
- **L3 — semantic decoders:** `y = D(z)`. Interchangeable read-outs (DBP / polarity / transformation / KCPR)
  over the *same* latent `z`.
- **Validation layer:** probe `P` (tests, ≠ decoder) + baseline suite `B` (must beat all) + failure state `⊥`.

---

## 3. B1.4 pipeline inspection (layer mapping)

Mapping each B1.4 pipeline step (design §6) to a layer:

| B1.4 step | What it does | Layer it corresponds to |
|---|---|---|
| 1. Target concept selected (hidden) | picks + hides the answer | experimental control (none) |
| 2. Generator never sees the word | blinding | validation hygiene (none) |
| 3. **Varṇa split** | decompose word → varṇas | **L1 *input* only** (tokenization), not the operator recurrence |
| 4. **Frozen varṇa attribute table** | varṇa → attribute axis **lookup** | **stands in for L2** — but is a table, not `F(M_σ…)` |
| 5. Experimentally assigned kosha | design-fixed condition | decoder parameter (L3 side) |
| 6. **Fixed KCPR pole rule** | attribute axis → pole | **L3 decoder** (`D`) component |
| 7. Profile assembled (attributes + poles) | ordered attributes + poles | the object handed downstream (the "`z`" B1.4 actually uses) |
| 8. Generator writes from profile | profile → passage | **L3 decoder** (`D`) — rendering |
| 9. Independent blinded judge | passage vs target/`Y` | **validation layer** (probe surface) |
| 10. Frozen scorer vs controls | metrics + label | **validation layer** (`P` + `B` + `⊥`) |

**Observation.** The chain from L1 to the profile is a **lookup + pole-selection**, not an operator-derived
latent formation. The `M_{σ_i}` operators (Stage A) never appear in the causal path; only the varṇa *identity*
is used, to index a table. The "profile" B1.4 treats as its latent is assembled by table lookup, not by any
`F`.

---

## 4. L1 integration status

**`L1_REFERENCED_ONLY`.**

B1.4 uses the **varṇa split** (step 3) — the same tokenization L1 consumes — but it does **not** use the L1
operators `M_{σ_i}` or the recurrence `t_i = M_{σ_i} t_{i−1}`. Nothing in the pipeline composes operators or
reads a structural trace. L1 is referenced at the tokenization boundary and otherwise absent from the causal
path. (This is consistent with the hard constraint not to modify Stage A / `symbolu_neural`; it just means L1
is not *wired in*, only *named*.)

---

## 5. L2 integration status

**`L2_PLACEHOLDER_ATTRIBUTE_TABLE`.**

B1.4 has **no implemented `F`**. The frozen **attribute table** (step 4) is a static varṇa→attribute lookup
standing in for L2. Measured against the rulebook's admissibility conditions on `F`:

- **Operator-derived?** No — it is a table indexed by varṇa identity, not a function of the `M_{σ_i}` operators.
- **Non-additive / order-sensitive?** Not intrinsically — a per-varṇa lookup is closer to a bag/set of
  attributes; order enters only if a later step uses it, and the poles come from kosha, not from composition.
- **Gloss-independent?** Unresolved — this is exactly the open candidate-E question (`MILESTONE_A_INCONCLUSIVE`).

So the thing B1.4 calls its latent (`profile`) is a **decoder input**, not an L2 latent `z = F(M_σ…, s_0)`.
L2 is described conceptually in the governing docs but **not defined or implemented** in B1.4.

---

## 6. L3 integration status

**`L3_DECODER_PRESENT`.**

The KCPR pole rule (step 6) and the word-blind generator (step 8) **are** functioning as decoders `D`: they map
the assembled profile to a human-facing passage. B1.4's L3 machinery is real and present. The caveat is that it
decodes a **placeholder** profile (a table lookup), not a true L2 latent — so L3 is present but is operating
over the wrong upstream object relative to the rulebook's `y = D(z)` where `z = F(M_σ…)`.

---

## 7. Validation layer status

**`VALIDATION_LAYER_DESIGNED`** (for a decoder-level study).

Probe `P` (§10), baseline suite `B` (§11), failure `⊥` conditions (§13), metrics + multiple-comparison
correction (§14), and terminal labels (§17) are all specified strongly at design level, with `probe ≠ decoder`
honored. Two residual pre-registration dependencies remain open by design and gate any run: the **`Y` source
is not yet fixed** (multiple candidates in §5), and the **E-admissibility gate is unresolved** (§4). These do
not weaken the validation *design*; they bound what it can be pointed at. As designed, this validation layer
validates the **decoder-level attribute profile**, not L2.

---

## 8. Key mismatch

> **B1.4 is currently an attribute-profile decoder validation design, not a full L1→L2→L3 integration.**

It wires L1-tokenization → an attribute-table stand-in for L2 → real L3 decoders → a well-specified validation
layer. The missing piece is the **L2 formation function `F`**: there is no operator-derived, non-additive,
gloss-independent map from the L1 operators to a latent `z`. B1.4 tests whether a *decoder over a table* beats
controls — a legitimate question — but it does **not** test an integrated L1→L2→L3 pipeline.

---

## 9. Implication for E-admissibility

The E gate and the L2 question are the **same** question wearing two labels:

- **If `E` is "just an attribute table,"** it is an **L3 decoder input**, not a true L2. That corresponds
  precisely to the B1.4 §4 label `E_ADMISSIBLE_ONLY_AS_DECODER_NOT_ESSENCE`: usable to *decode*, not to
  *validate an essence*. A win in that mode is a statement about the decoder, not about Symbol-U's latent.
- **If `E` must be L2**, then it has to be **derived from L1 operator features** (a real `F(M_σ…, s_0)`) or
  from another **non-gloss latent mechanism** — satisfying operator-derivation and non-additivity. That object
  does not exist yet; producing it is the substance of Milestone A / an L2 specification, not a table lookup.

So the candidate-E audit's `MILESTONE_A_INCONCLUSIVE` and this audit's `L2_PLACEHOLDER_ATTRIBUTE_TABLE` are two
views of one gap: **there is no operator-derived latent `F`.**

---

## 10. Recommended correction

**Split into `B1.4a` (decoder test) and `B1.4b` (L2 integration test).**

- **`B1.4a` — decoder-level attribute-profile study.** Keep the current B1.4 design *as is*, but **relabel its
  scope honestly**: it validates whether the attribute-table decoder + KCPR beats controls under word-blind
  generation. It may run (once `E`-as-decoder and `Y` are pinned) and can only earn a **decoder-utility**
  result — never an essence/L2 claim. Corresponds to `E_ADMISSIBLE_ONLY_AS_DECODER_NOT_ESSENCE`.
- **`B1.4b` — true L1→L2→L3 integration test.** **Blocked until `F` is specified**: define an operator-derived,
  non-additive, gloss-independent `z = F(M_{σ_1}, …, M_{σ_n}, s_0)` from the frozen L1 operators, then decode
  and validate. No `B1.4b` run until `F` exists and passes the `F`-admissibility conditions.

This split preserves the legitimate decoder work without letting it masquerade as full-layer integration, and
it names the real prerequisite (`F`) for the integration claim. (Recommendation only; no edit to the B1.4
design is made by this audit.)

---

## 11. Decision label

**`B1_4_DECODER_LEVEL_ONLY`.**

B1.4 integrates L1-tokenization + real L3 decoders + a designed validation layer over an **attribute-table
placeholder for L2**; it does **not** implement the L2 formation `F`, so it does not achieve full L1→L2→L3
integration. Governing consequence: `B1_4_L2_MISSING_BLOCKS_FULL_VALIDATION` — any *full-layer* validation
claim is blocked until `F` is specified. Recommended path: `B1_4_REQUIRES_SPLIT_DECODER_VS_L2` (§10).

---

## 12. Boundary statement

> B1.4 layer-integration audit completed. No meaning validated. No dataset built. Nothing run or scored. B1.3
> v3 remains parked. Track B remains blocked. Structure, not validated meaning.
