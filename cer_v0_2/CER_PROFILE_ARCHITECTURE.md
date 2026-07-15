# CER Profile Architecture (Deliverable 2)

Decision and design for multi-profile CER. Grounded in the implemented `cer_v0_2/`.

Labels: `FACT` (implemented/measured) · `RECOMMENDATION`.

## 1. Chosen architecture: universal envelope + domain profiles
`RECOMMENDATION` (implemented). Not one flat schema (would force scale and rollout to share a payload shape, losing semantic precision), not fully separate schemas (would duplicate the envelope and split conformance machinery). The **universal envelope + domain profiles** shape is the smallest architecture that preserves precision:

```
CER envelope (profile-independent)
  cer_version · profile · risk_tier · authority · state_binding ·
  policy_ref · actuation(profile-specific) · provenance · extensions
Profiles
  kubernetes.scale.v1     (tool.tool_name="scale")
  kubernetes.rollout.v1   (tool.tool_name="rollout")
```

## 2. What every profile defines
`FACT` (`profiles/base.py`, `profiles/*.py`): required / optional / **prohibited** actuation fields; argument normalization + units; the ActionGate envelope projection; the ACP cloud mapping; canonical test vectors. Unknown profiles fail closed (`get_profile`).

## 3. Identity & domain separation (no collision)
`FACT`. Identity = ActionGate v2 `action_hash` of the profile's envelope projection. The **profile participates in the identity via `tool.tool_name`** (`scale` vs `rollout`), which is inside the hashed payload, plus a disjoint argument set. Measured: for the *same target*, `scale.v1` digest `07f7a6aa…` ≠ `rollout.v1` digest `72ddae26…`. Two profiles cannot collide even where field names overlap (e.g. `target`), because `tool_name` differs.

## 4. Backward compatibility (V0.1 frozen)
`FACT`. `kubernetes.scale.v1`'s envelope projection is byte-identical in shape to CER V0.1's, so the **same actuation yields the same digest across CER V0.1 and V0.2** — measured: V0.1 scale `07f7a6aa…` == V0.2 `kubernetes.scale.v1` `07f7a6aa…`. V0.1 is not altered; the compatibility tests assert this.

## 5. Profile-downgrade / confusion guard
`FACT` (`base.check_fields`, `envelope.validate_cer`): each profile declares **prohibited** fields (rollout-only fields under scale, and vice-versa); a mismatched payload fails closed. The actuation `operation` must match the profile's ActionGate operation. A V0.1 CER (cer_version 0.1) is rejected by the V0.2 validator and vice-versa — V0.1 and V0.2 semantics cannot be confused.

## 6. Provenance
`FACT`. Provenance (runtime/model/objective/…) is a profile-independent envelope section, never in the identity (ActionGate v2 excludes it). Measured: rollout digest is invariant to provenance changes.

## 7. Reuse (0 control-plane changes)
`FACT`. Both profiles reuse the frozen ActionGate v2 identity profile and ACP core unchanged. ACP already supports `CloudOperation.ROLLOUT`, so rollout adds **0 ACP lines**. The control plane receives only the CER; the profile→mapping dispatch is data, not a runtime switch.
