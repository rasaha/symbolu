# Profile Extensibility

The neutral core may later support deployment clearance, agent-tool execution, database mutation,
financial transaction, and robotics operation. Each is a **profile** over the same core.

## What a profile may add

| Extension point | Example (GitHub) | Rule |
|---|---|---|
| required signal types | `ARTIFACT_IDENTITY`, `REQUIRED_CONTROL` (checks) | must be `TrustedSignal`s; core evaluates them via the neutral policy |
| profile-specific reason codes | `GITHUB_MERGE_TREE_MISMATCH` | `PROFILE_SPECIFIC`; map to a core status; never a new status |
| target-specific identity | `repository/pr/head/base/merge_tree` | folded into `action_fingerprint`; core treats it opaquely |
| profile policy | required-check set, freeze classes | passed in as policy; never mutable global state |

## What a profile may NOT do

- **May not broaden.** Profile constraints may only **narrow** (monotonicity is a core invariant,
  enforced above the profile).
- **May not replace or subclass authority semantics.** A profile cannot introduce a path that mints
  authorization, converts a denial to clearable, or overrides ActionGate/Decision-Authority ownership.
- **May not add a status.** The four statuses are fixed; profiles contribute reason codes that map onto
  them.
- **May not embed a target client in the core.** Target/API access lives in the profile's signal
  adapter, not the evaluator.

## Constrained extension interface (not an open plugin)

Profiles register through a **narrow, typed** extension surface — not an arbitrary plugin loader:

```text
ClearanceProfile
├── profile_id: str
├── required_signal_types: frozenset[str]
├── profile_reason_codes: frozenset[str]        # each mapped to a core status
├── action_identity_fields: tuple[str, ...]     # folded into action_fingerprint
└── narrowing_policy: ClearancePolicy           # narrowing-only by construction
```

The core validates at registration that every profile reason code maps to exactly one of the four
statuses and that the narrowing policy has no widening operation. There is **no** `eval`, no dynamic
code import, and no capability for a profile to alter the core evaluation algorithm — only to supply
data (signal types, reason mappings, identity fields, narrowing policy). This avoids the
"profile overreach" and "unconstrained plugin" risks (RISK_REGISTER).
