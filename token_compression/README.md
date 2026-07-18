# token_compression

Formula-recovery and hypothesis-definition workspace for protected-context
compression (the "ContextGuard" direction evaluated in
`../TOKEN_COMPRESSION_LOGIC_EVALUATION.md`).

This directory holds the audit trail that must exist **before** any compression
harness is built. No experiments are run here yet.

## Contents

- **[`SOURCE_FORMULA_AUDIT.md`](SOURCE_FORMULA_AUDIT.md)** — the required deliverable.
  For every candidate formula (SCC, USE, KVPro/INT4, ActionGate `D`, and the
  proposed compression reformulations) it records: the formula, its real source
  file/line, exact-vs-reconstructed status, variable definitions, compression role,
  a fair baseline, failure modes, an eligibility decision, and one interpretation
  label. Recovery was done against actual code, not the prose description.

## Load-bearing results (see the audit for evidence)

1. **SCC entropy sign is settled: `+γ·(1−Eᵢ)`** (high entropy penalized), from four
   implementations and the frozen spec. The lone `+γ·Eᵢ` is a docstring typo.
2. **No implemented text-graph "USE" exists.** Every implemented USE/phase formula is
   over neural/signal phases; applying phase to text is a category error the task
   forbids. `R_USE` relation recall is a *new* reformulation, not patent reuse.
3. **KVPro "int4_protected" = generic asymmetric group-INT4 + static top-4% max-abs
   outlier-channel sidecar.** No error-bound mask optimization; WarmTier is
   hardware-untested. Reuse is a design analogy only.
4. **ActionGate `D(C_orig)=D(C_comp)` is the one exactly-measurable differentiator**,
   valid only on an eval set seeded to perturb the 24 envelope fields.

## Rules for this workspace

- Do not claim SCC, USE, or KVPro "already proves token compression." None was built
  for it.
- Protection (P0) is a hard constraint, never a term in a weighted score.
- SCC/USE may only relax, restore, add validation, or reject — never authorize
  deletion of a deterministically protected unit.
- Per task §6, no SCC/USE/protected-context experiment runs until this audit is
  committed. The next step is a preregistration of the deterministic-structural + P0
  layer with BCVF-style kill criteria.
