# CER V0.2 Baseline Freeze (V0.3 Stage 1)

Immutable fingerprints of every V0.1/V0.2 and frozen-control-plane artifact V0.3
builds on. **No frozen artifact may be rewritten.** Corrections in V0.3 are
introduced only as an **erratum** (`CER_SPECIFICATION_ERRATA.md`), a **versioned
clarification**, or a **new V0.3 profile** — never by editing a frozen file.

Labels: `FACT` (measured at git HEAD `10ef4d1`).

## Frozen fingerprints (sha-256, first 16 hex)

### CER V0.1 / V0.2 specification & schemas
```
cf41e7381a3ae6cd  cer_v0_1/CER_V0_1_SPEC.md
ae97be97f791e6b1  cer_v0_2/CER_PROFILE_ARCHITECTURE.md
26c7e806b4240c5a  cer_v0_2/CER_KUBERNETES_ROLLOUT_PROFILE.md
41ca69d40149339c  cer_v0_1/cer_v0_1.schema.json
fe80b2d50f5a3e40  cer_v0_2/cer_v0_2.schema.json
8da0b5bb2ed8062e  cer_v0_2/profiles/kubernetes.scale.v1.schema.json
84ca8d14145b1356  cer_v0_2/profiles/kubernetes.rollout.v1.schema.json
```

### Universal envelope + both Kubernetes profiles
```
c04bd2560c0fd6aa  cer_v0_2/envelope.py
eb0f1254c74d099f  cer_v0_2/profiles/_common.py
a1e7a0c2d7a8f77a  cer_v0_2/profiles/base.py
05e7e26c6ab6fea0  cer_v0_2/profiles/scale.py
306266320c2d7b49  cer_v0_2/profiles/rollout.py
86b14c4167e010da  cer_v0_2/actuation.py
602221a26daab40d  cer_v0_2/control_plane.py
```

### Canonicalization + identity implementation (ActionGate reference) — identity profile frozen
```
64983d92802fb580  action_gate_ref/jcs.py            (RFC-8785 JCS + Action Profile)
4a9268ba7e4238ad  action_gate_ref/hashing.py         (domain-separated length-prefixed hashing)
ce458712e7643a27  action_gate_ref/projection.py      (v1/v2 identity projection — FROZEN)
5408ce8ed032dd73  action_gate_ref/canon_profile.py   (versions, domains, algorithms)
0307acdb4e05d6ed  action_gate_ref/schema.py           (envelope validator + OPERATIONS taxonomy)
a358c6459ccb7ac9  action_gate_ref/gate.py             (deterministic decision state machine)
a2f7c5b51f5fa907  action_gate_ref/policy.py           (signed ruleset incl. R7 DB_MUTATION, R3 DB_DELETE)
```

### All conformance vectors (47 V0.2 + V0.1)
```
3ec7f36d741f6302  cer_v0_1/conformance/vectors.json
3dc9f372c47121bd  cer_v0_2/conformance/vectors.json   (47 vectors)
```

### ACP core (domain-neutral) + Kubernetes cloud adapter
```
6f1e5af0a3c2e75a  autonomous_control_plane/envelopes.py        (ActionDecision — domain-neutral core)
b810e2f0c3bc0e28  autonomous_control_plane/cloud/composition.py (compose() — reused unchanged in V0.3)
21fd7283100eff66  autonomous_control_plane/cloud/outcomes.py     (CloudRecommendation — reused unchanged)
e4e7e9362de04dd7  autonomous_control_plane/cloud/envelopes.py    (K8s cloud envelopes)
8d334746b7161804  autonomous_control_plane/cloud/adapter.py      (K8s shadow adapter)
ced292c276d01241  autonomous_control_plane/cloud/constraints.py  (K8s constraint evaluator)
```

### Previous final results
```
fb79ec0e2e580c50  cer_v0_1/conformance/results.json
1a0ae9b40a0dabc6  cer_v0_2/conformance/results.json
```

## What V0.3 reuses UNCHANGED (0 lines changed)
`FACT`.
- **ActionGate reference** (`projection.py`, `gate.py`, `schema.py`, `policy.py`, `jcs.py`,
  `hashing.py`, `canon_profile.py`) — the v2 identity profile and the `DB_MUTATION`/`DB_DELETE`
  operation taxonomy already exist; V0.3 adds no operation and changes no rule.
- **ACP composition core** — `compose()`, `AuthorizationVerdict`, `CombinedOutcome`,
  `CloudRecommendation`, `is_permissive`, and the `ActionDecision` set. The new database
  operational-safety adapter (V0.3) *reuses* `compose()` verbatim; it does not modify it.
- **CER V0.1 and V0.2 packages** — `cer_v0_1/`, `cer_v0_2/` are read-only baselines. V0.3
  imports the V0.2 corpus/producers only to re-derive existing vectors for differential
  conformance; it does not edit them.

## Correction discipline
`FACT`. Any V0.3 disagreement between the original and clean-room implementations is a
**specification-review event** recorded in `CER_SPECIFICATION_ERRATA.md`. Resolutions are
new normative language or new vectors; prior vectors are never edited in place. The V0.2
vector fingerprint `3dc9f372c47121bd` and V0.1 `3ec7f36d741f6302` remain byte-unchanged at
the end of V0.3 (asserted by the backward-compatibility tests).
