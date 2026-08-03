# dgm-actiongate-provider (compatibility distribution)

Legacy wheel name for the ActionGate action-governance provider. The implementation
now lives in the canonical package **`ugence-actiongate-provider`**
(`packages/providers/actiongate`). This distribution ships only the logic-free
`actiongate_provider` compatibility shim and depends on the canonical wheel (with the
`decision-authority` extra) — there is no duplicated source and no second ActionGate
implementation. It does not depend on TAP. Prefer `ugence-actiongate-provider` in new
dependency declarations.
