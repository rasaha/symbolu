# Product-Package Boundary — Code Governance

> Documentation only. **No package is created by this audit.** Authoritative source:
> `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§14/appendix). Verified against repo conventions
> at commit `3ec11e4e`.

## 1. Repository conventions observed

- Canonical **capabilities** live under `packages/capabilities/<name>/` with a `src/` layout, a
  `pyproject.toml` (independent distribution, `ugence-<name>`), stdlib-or-minimal deps, and a
  `verify_<name>_distribution.py` (e.g. `packages/capabilities/storygraph/`).
- Neutral contracts and the framework live under `packages/` (`governance-contracts`,
  `governance-provider-framework`).
- **Providers** are top-level adapter packages modeled on `actiongate_provider/` (pure offline
  `core/`; thin `provider.py` `BaseProvider` adapter; `errors/`; versioned `mapping/`;
  `conformance/`; `tests/`).
- **There is no `products/` directory yet** — Code Governance introduces the first product package
  tree. The terminology audit already reserves the product tier (Assert/Decide/Act/Sequence + Code).

## 2. Minimum physical layout for MVP 1A–1C (candidate — do not implement in this phase)

```
products/code-governance/
  api/               # product public surface (status, envelopes) — PRODUCT_PUBLIC
  workflow/          # Workflow Service: state machine, reference propagation, fail-closed chain proof
  github_connector/  # GitHub Evidence Connector (product; no authority): webhook, install auth, ingestion
  evidence_mapping/  # GitHub evidence → immutable evidence_refs + claim manifest
  policy/            # Repository Policy Pack loading/compilation (from approved base branch)
  action_mapping/    # build ActionGovernanceRequest + ExactChangeAuthorization envelope + merge identity
  reconstruction/    # governance-chain reconstruction / audit view (fail closed on incomplete chain)

providers/github-execution/   # GitHub EXTERNAL_EXECUTION provider (modeled on actiongate_provider/)
```

## 3. Package vs. module vs. configuration decisions

| Element | Decision | Rationale |
|---|---|---|
| Code Governance product API | **package** (`products/code-governance/api`) | PRODUCT_PUBLIC surface; independently versioned |
| Workflow Service | **module** in the product package (`workflow/`) | product-internal; not separately distributable |
| GitHub Evidence Connector | **module** (`github_connector/`) | product connector; no authority; not a provider |
| GitHub Execution Provider | **separate package** (`providers/github-execution/`) | must be a GPF-registrable provider; follows provider conventions; enables GitLab/Gerrit peers |
| Repository Policy Pack | **configuration + module** (`policy/`) | policy packs are data authored/versioned via the policy compiler; loader is code |
| Claim Manifest schema | **module/schema** (`evidence_mapping/`) | PRODUCT_PUBLIC schema; may later graduate to neutral |
| Merge Action schema | **module** (`action_mapping/`) | PRODUCT_INTERNAL (`merge_identity_schema.json`) |
| Governance-chain reconstruction | **module** (`reconstruction/`) | product-internal audit view |
| GitHub webhook adapter | **module** in `github_connector/` | part of the connector |
| User-facing status projection | **module** in `api/` | product-internal; integrates unified console |
| Competitive Code Adjudication | **separate capability package** (`packages/capabilities/competitive-adjudication/`) — MVP2 | peer to `storygraph`/`decision-authority`; advisory only; **out of MVP 1** |
| Deployment Governance | **separate artifact/chain** — MVP3 | out of MVP 1 |

## 4. Scope guardrails

- **Competitive Code Adjudication** and **Deployment Governance** stay **outside MVP 1 implementation**
  unless a neutral interface forces earlier definition (none does).
- The product must depend **downward only** (product → capabilities → neutral contracts; product →
  connector; product → GPF → GitHub execution provider). See `DEPENDENCY_DIRECTION.md`.
- No product code imports capability internals — only public surfaces (`ugence_decision_authority.api`,
  `ugence_governance_provider_framework.api`, `ugence_governance_contracts`, `tap_provider`,
  `actiongate_provider`, `ugence_storygraph`).
