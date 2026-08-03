# V1 Adapter Behavior (frozen) — P2.1

`adapt_compiled_workflow` (the v1 path) is **not modified** by P2.1. Its behaviour
is byte-frozen for every `workflow_ir.v1` input. Machine form:
`V1_ADAPTER_BEHAVIOR.json`.

- The v1 dispatch path (`compatibility.adapt_workflow` with a v1 document, and the
  direct `adapt_compiled_workflow`) produce **identical** `adaptation_fingerprint`
  (asserted by `test_v1_path_frozen_fingerprint_matches_direct`).
- For the four P3A scenarios the committed v1 adaptation fingerprints reproduce
  exactly (conformance manifest `v1_adaptation_fingerprint`), and the v1 plan
  fingerprints reproduce the frozen P3A expected outputs (e.g. procurement plan
  `sha256:c19735…`).
- v1 node dispositions, role requirements, non-agent dispositions, eligibility,
  rankings, composition, permissions, fallbacks and AgentTeamPlan are unchanged;
  the AWC P1/P2 suite (158) remains green.

The v2 semantic adapter is a strictly parallel path; a v1 document is never routed
to it (and the v2 adapter rejects a v1 document: `UNSUPPORTED_COMPILER_CONTRACT`).
