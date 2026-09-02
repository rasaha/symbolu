# ugence-readiness-comparison

The separately commissioned comparison engine of the Benchmark Registry ADR's
consuming-evaluation-engine role, as assigned by the owner ruling on Composite
ballot §10.1 and commissioned (research-only, slice 1) by the ratified ballot in
`docs/architecture/REASONING_METHOD_GOVERNANCE_CONTRACT_AND_COMMISSIONING_BALLOT.md` §9.

One pure function: `compare(request) -> result`, implementing §5 and §7 of that
specification exactly. It performs no I/O, no normalization, no fetch of a
benchmark reference, no averaging, no fallback across resource dimensions, no
read of self-reported quality, and no inference of authority from names.

Every result states `authority_resolution_basis = "REQUESTER_ASSERTED"` and every
assessment is `usage_scope = "RESEARCH_ONLY"`. Nothing this package produces is
approval-bearing.

The port contracts live in `ugence-reasoning-method-governance`; that package
never imports this one.
