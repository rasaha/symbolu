# Context-to-Action Identity Binding (V2.2 §6)

Proves all three layers bind to the same operation, from the reduced context all
the way to hypothetical execution. Code:
`robotics_reliability_bench/acp_control_plane/identity_chain.py` (+ the V2.1
`identity_binding.py` for the ActionGate↔ACP sub-binding).

## The chain

```
context digest
      │   (the reduced context actually handed to the LLM stage)
      ▼
action hash (ActionGate)
      │   (the envelope ActionGate authorized)
      ▼
ACP candidate identity
      │   (the CloudActionCandidate ACP judged)
      ▼
hypothetical execution identity
      (digest of all of the above — one id for the whole pipeline)
```

## The three digests + the execution identity

- `context_digest = ctx:sha256({context_id, base, surviving_spans})` — binds the
  exact reduced context (surviving span ids + text + base). Any change to what the
  LLM saw changes the whole chain.
- `actiongate_action_hash` — the **real** ActionGate action hash of the envelope
  built from the proposed action (`action_gate_ref.projection.action_hash`).
- `acp_candidate_identity` — the ACP `CloudActionCandidate.identity` (frozen ACP
  domain-separated identity).
- `execution_identity = exec:sha256({context_digest, proposed_action_digest,
  action_hash, candidate_identity})` — one id for the whole hypothetical execution.

Schemas are **not merged**: the three identities are deliberately different values
(different domains); the chain *links* them, it does not equate them.

## `verify_chain` — fail-closed

The decisive check (`identity_chain.verify_chain`):

> the action ActionGate + ACP evaluated must be **exactly** the action the reader
> derived from the reduced context.

If `reader_op_facts != stack_op_facts` → `CONTEXT_TO_ACTION_MISMATCH`
(`CONTEXT_IDENTITY_MISMATCH` end-to-end class), and the operation is not eligible.
Missing context digest / action hash / candidate identity also fail closed.

This is the whole-pipeline analogue of the V2.1 ActionGate↔ACP binding. Together
they close every gap:

| gap | caught by | class |
|---|---|---|
| the LLM proposes action A but a different action B reaches the layers | `verify_chain` | `CONTEXT_IDENTITY_MISMATCH` |
| ActionGate authorizes patch A but ACP judges patch B | V2.1 `bind()` | `COMPOSITION_IDENTITY_MISMATCH` |
| a critical span is dropped so no action can be derived | reader | `INSUFFICIENT_CONTEXT` |

## Corpus proof

- `healthy_rollout` — chain bound end-to-end; `execution_identity` present;
  eligible.
- `identity_mismatch` — a divergent `stack_op_override` (different replica target
  than the reader read) → `CONTEXT_IDENTITY_MISMATCH`, not eligible.
- `malformed_context` — a critical span malformed → reader `INSUFFICIENT_CONTEXT`,
  no downstream, not eligible.

Every non-mismatch, reader-OK scenario is `chain_bound = True` (§10 I5 —
identity consistency 100 %).
