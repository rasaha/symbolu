# ACP Cloud Adapter Design (V2 §8)

Code: `symbolu_robotics/autonomous_control_plane/cloud/adapter.py`
(`CloudShadowAdapter`). The adapter orchestrates one cloud decision end-to-end,
reusing the **frozen ACP core unchanged**:

```
real cluster state  ->  CloudConstraintEvaluator            (real cloud_controller)
                    ->  filter_admissible + LexicographicActionSelector   (FROZEN core)
                    ->  DecisionTrace                                       (FROZEN core)
                    ->  cloud_recommendation                                (§7 mapping)
                    ->  compose(ActionGate verdict, ACP rec)                (§3 composition)
```

The selector runs **byte-for-byte unchanged** on cloud envelopes because
`CloudActionCandidate` exposes `.candidate_id` + `.identity` and `CloudWorldState`
exposes `.version` — exactly the duck-typed contract the frozen
`LexicographicActionSelector` / `filter_admissible` / `DecisionTrace` require. The
frozen selector's own tests (`filter_admissible` fail-closed, total-order
selection) hold on cloud candidates without modification.

## Selection order (frozen key, cloud-supplied)

`_blast_sort_key(c) = (blast_radius, is_destructive?1:0, operation)` — smallest
operational blast first, destructive last, then the candidate id appended by the
selector as the always-unique final tie-break. Total, deterministic, replayable.

## Safety posture (all enforced here)

- **OFF by default** (`enabled=False`). A disabled adapter does no work and
  returns `None`; nothing is recorded. This is the kill switch.
- **Never actuates.** No Kubernetes client import (asserted by a test), no
  Deployment patch, no ActionGate token minted. Every `CloudShadowRecord` is
  `shadow_only=True`.
- **Contained exceptions.** Any failure inside `_observe` is caught, recorded as
  `shadow_error=True` with `error_kind`, and returned as a `HOLD` — it never
  propagates to the caller (a real control loop must be unaffected).
- **Bounded logging.** `BoundedCloudSink` is a fixed-capacity `deque(maxlen)`
  (reusing the robotics bounded-sink pattern); evicted records are counted in
  `dropped`. No unbounded growth / DoS path.
- **Commit-time revalidation.** `commit_revalidate` reuses the **frozen**
  `ReferenceCommitRevalidator` to detect cluster drift (resourceVersion / state
  change), candidate rebinding (a manifest digest mutated after the decision),
  and expiry between decision and commit (TOCTOU). It gates nothing — it records
  whether the earlier recommendation still holds.

## On the reference authorization object

`commit_revalidate` constructs a frozen `ControlAuthorization` purely to drive the
revalidator's binding check. This is a **content-identity binding**, explicitly
**not** a cryptographic execution credential. ACP never mints a real execution
token — that is ActionGate's exclusive role (see `ACP_ACTIONGATE_BOUNDARY.md`).
The object exists only so the frozen TOCTOU machinery can be reused unchanged to
answer "does ACP's earlier decision still bind the thing about to be committed?"

## Output

`observe(...)` returns a `CloudShadowResult` (ACP decision, cloud recommendation,
optional `CompositionResult`, per-candidate evidence, and the appended record) or
`None` when disabled. `CloudShadowRecord.content_dict()` is a fully deterministic
view (every field is a deterministic function of inputs), used for rerun-identity
checks.

## Rollback / kill-switch

- **Kill switch:** `enabled=False` (default) disables all shadow work instantly.
  The adapter is not wired into any production path.
- **Rollback:** delete `symbolu_robotics/autonomous_control_plane/cloud/` and
  `robotics_reliability_bench/acp_cloud/`; nothing in production imports them, and
  the frozen ACP core + `cloud_controller` are untouched.
