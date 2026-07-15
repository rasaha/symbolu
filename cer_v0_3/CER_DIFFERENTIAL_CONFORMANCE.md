# CER Differential Conformance (Deliverable 3)

Runs **every existing V0.1 and V0.2 CER** through two independent implementations
— the reference (`cer_v0_2` + `action_gate_ref`) and the clean-room
(`cer_v0_3.cleanroom`) — and requires equality of *validation result, normalized
payload, canonical bytes, digest, and error category*. A matching hash with a
divergent normalized payload would NOT pass: payload and bytes are compared
explicitly, before the digest.

Labels: `FACT` (measured). Machinery: `conformance/differential.py`; frozen result
`conformance/differential_v0_1_v0_2.json`; test `tests/test_differential.py`.

## Corpus under differential test
`FACT`. **77 items**:
- **47** V0.2 valid CERs (scale + rollout, across ugence / langgraph / openai-agents);
- **4** V0.2 invalid CERs (unknown profile, unsupported extension, malformed payload,
  profile downgrade);
- **26** V0.1 CERs, translated to their identity-equivalent V0.2 `scale.v1` form and
  required to reproduce the **frozen V0.1 digest** (fingerprint `3ec7f36d…`, unchanged).

## Result
`FACT`.
| Check | Result |
|---|---|
| Validation-result agreement | **77 / 77** |
| Normalized-payload agreement (valid items) | **73 / 73** |
| Canonical-byte agreement (valid items) | **73 / 73** |
| Digest agreement (valid items) | **73 / 73** |
| Error-category agreement (invalid items) | **4 / 4** |
| V0.1 identity reproduced by clean-room (== reference == frozen) | **26 / 26** |
| **Identity-affecting differences** | **0** |
| **Specification ambiguities affecting identity** | **0** |

`all_identity_agree = true`. The two implementations — one importing the reference
canonicalizer/projector/hasher, one reimplementing them from the published spec with
no shared code — produce **byte-identical** normalized payloads and canonical bytes,
and identical digests, for every valid vector; reject every invalid vector with the
same coarse error class; and both reproduce every frozen V0.1 digest.

## Difference classification (milestone §4)
`FACT`. Zero differences of any class were produced. The runner is nonetheless wired
to classify each difference it might find:
- `specification_ambiguity` — validation-result / normalized-payload / canonical-byte
  divergence (would be **high severity**: identity-affecting);
- `implementation_defect` — digest divergence on equal canonical bytes, or a missed
  V0.1 reproduction;
- `harmless_diagnostic` — both reject an invalid vector but with different coarse error
  labels (not identity-affecting);
- `vector_defect` / `unsupported_behavior` — reserved for cross-domain vectors (§ DB stage).

Because the count is zero, `CER_SPECIFICATION_ERRATA.md` records **no identity-affecting
erratum** from the V0.1/V0.2 differential; the ambiguity-audit checklist (§10) is applied
to the database domain in the later stage, where the clean-room and reference implement a
*new* profile from the same written spec — the sharper independent-implementation test.

## Why this is strong evidence for Q1 and Q3
`INTERPRETATION`. The clean-room was written from the specification and JSON Schema and is
statically proven (AST) to import none of the reference code. That it reproduces the
reference's normalized payload and canonical bytes exactly — not merely the final hash —
means the CER V0.2 specification is precise enough to be implemented independently without
an identity-affecting ambiguity across the entire existing corpus.
