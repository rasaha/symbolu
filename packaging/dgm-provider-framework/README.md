# dgm-provider-framework (compatibility distribution)

Legacy wheel name for the Governance Provider Framework. The implementation now
lives in the canonical package **`ugence-governance-provider-framework`**
(`packages/governance-provider-framework`). This distribution ships only the
logic-free `governance_providers` compatibility shim and depends on the canonical
wheel (with the `adapters` extra) — there is no duplicated source and no concrete
provider. Prefer `ugence-governance-provider-framework` in new dependency
declarations.
