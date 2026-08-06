# PR #1363 (typed-vs-prose benchmark preregistration) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `0c63d1f2` onto the authoritative default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (now the default tip; local default synchronized;
working tree clean). Documentation-only; nothing required correction.

## Verified — Git + GitHub + PR diff + repository history + CI + review state + merged evidence
- **Open/draft/unmerged/mergeable clean;** documentation-only (3 files under
  `docs/research/hybrid_llm/benchmarks/`); no model/experiment code, dataset, training, seed allocation, or
  execution; `abc.json` and prior evidence unchanged.
- Contains the **preregistration**, the **shortcut/leakage analysis**, and the **PR #1362 audit record**.
- Asks **only** the controlled single-hop question (typed vs. information-equivalent flattened prose).
- **Exactly two primary arms** — B0 canonical flattened prose · B1 typed structured — with the **underlying
  fact set identical** and **input representation the only experimental variable**.
- **Excludes** BindingSlots · E1 memory · recurrent architecture changes · bounded quadratic reader ·
  table correction at answer time · real-model adaptation · multi-hop · unequal capacity.
- Includes **splits S1–S8** and **causal ablations A1–A6**; requires **deterministic SQL-equivalent ground
  truth**, a **mechanical information-equivalence verifier + shared fact-set hash**; separates endpoint /
  causal purity / evidence integrity / abstention / tenant isolation; requires **zero** unauthorized
  cross-tenant inclusion.
- Contains the **exact permitted future conclusion vocabulary** (`TYPED_STRUCTURE_SINGLE_HOP_*`); scopes any
  positive conclusion to controlled synthetic single-hop reasoning.
- Marks unresolved protocol values `APPROVAL_REQUIRED_BEFORE_EXECUTION`; does **not** imply implementation or
  execution is authorized; has **not** generated or consumed the proposed reserved seeds.
- **Preserves** `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
  `KDA_VALIDATION_BLOCKED`; forbidden tokens (`E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`,
  `KDA_VALIDATION_ELIGIBLE`, `PRODUCTION_READY`) appear only in the explicit "never emit" line.
- **CI 7/7 green; 0 unresolved review threads.**

Scientific scope unchanged; no arm added; causal requirements not loosened; execution not authorized.
Faithful, bounded, docs-only — merged.
