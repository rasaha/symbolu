# dgm-tap-provider (compatibility distribution)

Legacy wheel name for the TAP assertion-governance provider. The implementation
now lives in the canonical package **`ugence-tap-provider`**
(`packages/providers/tap`). This distribution ships only the logic-free
`tap_provider` compatibility shim and depends on the canonical wheel (with the
`decision-authority` extra) — there is no duplicated source and no second TAP
implementation. It does not depend on ActionGate. Prefer `ugence-tap-provider`
in new dependency declarations.
