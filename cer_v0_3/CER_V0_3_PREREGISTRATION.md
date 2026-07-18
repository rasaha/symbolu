# CER V0.3 — Preregistration (Deliverable 1)

**Committed BEFORE the final run.** Freezes the frozen V0.2 baseline, the selected
domain, the clean-room boundary and forbidden-import rules, the new profile spec and
schema, the ActionGate mapping, the ACP adapter design, the producer paths, the
corpus, expected outputs, conformance thresholds, ambiguity-severity rules, verdict
rules, and environment limitations. No threshold is tuned after final aggregates are
observed. Deviations are appended, never edited in place.

Labels: `FACT` (implemented/frozen).

## 1. Falsifiable questions
- **Q1** CER can be implemented independently from the written spec + vectors, without importing the Ugence implementation.
- **Q2** the same envelope + identity architecture supports a materially non-Kubernetes domain.
- **Q3** the independent implementation produces byte-identical canonical payloads and digests.
- **Q4** governance stays precise when ACP needs a new domain-specific operational-safety adapter.

## 2. Frozen V0.2 baseline (immutable)
`FACT`. Per `CER_V0_2_BASELINE_FREEZE.md` (git `10ef4d1`). Key frozen fingerprints
(unchanged at the end of V0.3, asserted by `test_backward_compat.py`):
```
projection.py ce458712  gate.py a358c645  schema.py 0307acdb  policy.py a2f7c5b5
cloud/composition.py b810e2f0  cloud/outcomes.py 21fd7283
cer_v0_1/vectors 3ec7f36d  cer_v0_2/vectors 3dc9f372
V0.2 scale digest 07f7a6aa  V0.2 rollout digest 72ddae26
```

## 3. Selected domain
`FACT`. `database.mutation.v1` (preference rank #1). Repository-grounded: ActionGate
already carries `DB_MUTATION`/`DB_DELETE` operations + rule R7 + fact extraction
(`CER_DOMAIN_SELECTION.md`). Materially non-Kubernetes; proves cross-domain portability
with **0** frozen-core changes.

## 4. Clean-room boundary + forbidden-import rules
`FACT`. `cer_v0_3/cleanroom/` reimplements validate/canonicalize/project/digest from the
published spec. Standard library only; imports NONE of `action_gate_ref`, `cer_v0_1`,
`cer_v0_2`, `symbolu_robotics`, or original-side `cer_v0_3` sub-packages. Enforced by AST
test `tests/test_forbidden_imports.py`. Zero third-party dependencies (JCS reimplemented).

## 5. New profile spec + schema
`FACT`. `CER_DATABASE_MUTATION_PROFILE.md` + `profiles/database.mutation.v1.schema.json`.
`operation="DB_MUTATION"`, `tool={server_id:"database",tool_name:"mutation"}`; sql_operation
∈ {INSERT,UPDATE,DDL} (DELETE reserved); identity-bearing statement/parameter/predicate
digests, affected-scope bound, transaction+isolation, expected_row_version, optional
compensation_ref. Secrets prohibited (recursive guard, fail closed). Unknown profile /
extension / downgrade / bad numeric / missing state binding fail closed.

## 6. ActionGate mapping
`FACT`. DIRECT onto frozen rule **R7** (FORBID unbounded; REQUIRE_SIMULATION MEDIUM;
MAX_SCOPE affected_count≤10000; ALLOW_WITH_CONSTRAINTS in_transaction). ActionGate lines
changed: **0**. Evidence/approvals bind to the DB action's v2 `action_hash`.

## 7. ACP adapter design
`FACT`. `cer_v0_3/acp_db/` — new sibling operational-safety evaluator (reachable, target-
bound, state-version-current, scope-within-bound, txn-capacity, no-migration, no-freeze,
replication, lock, rollback-available) over an authored fixture world; reuses the FROZEN
`compose()`/`AuthorizationVerdict`/`CloudRecommendation` unchanged. ACP-core lines changed:
**0**. Shadow-only; no live DB telemetry.

## 8. Producer paths
`FACT`. Two independent producers (`db_actuation.py` shared model): native
`UgenceDbProducer` and a generic `ToolRuntimeDbAdapter` (deterministic tool-call
interception). Both normalize the same actuation to the same digest. The clean-room is
NOT counted as the second producer.

## 9. Corpus & expected outputs (frozen)
`FACT`. `corpus.py` — 29 cross-domain cases + the V0.1/V0.2 differential (77 items).
Preregistered relationships: new-domain valid → **equal** (5); identity differences →
**different** (9); invalid & security → **invalid** (9, both implementations fail closed);
stale / missing-evidence → **governance** (HELD_BY_ACP / PENDING_AUTHORIZATION); unbounded →
**deny** (BLOCKED_BY_AUTHORIZATION); cross-domain evidence/approval → **rejected** (3);
bypass → no execution identity. Existing-profile regression: scale/rollout digests unchanged.

## 10. Fingerprints (frozen, commit `2ef5968`)
```
cleanroom/canon.py     3120653be30fa552   cleanroom/digest.py   12979809e605581b
cleanroom/cer.py       1a355ad34c362096   cleanroom/profiles.py 46cdf22496ae90bf
cleanroom/errors.py    f49d1957fb5af0d9
profiles/database.py   1b70482b63522842   profiles/_envelope.py 5550f0177f84d876
profiles/base.py       978a57a4e4783a30   database schema       1c4e394e2036d599
envelope.py            ebb84e2f62e5d452   control_plane.py      782b2f3d2fb3f446
db_actuation.py        de64c11a8b4ef469
acp_db/envelopes.py    01bfa46b1c45d91f   acp_db/safety.py      f0c5cb236d86da2e
acp_db/adapter.py      278f464850d0b660
producers/ugence_db.py c514718cb2d2376c   producers/tool_runtime_db.py 1d402fb7f949a637
corpus.py              f6872b384edbc7ce
conformance/differential.py adcdf2e2f7b2e4b2   conformance/cross_domain.py ab5744c21fb1f7e8
```
Base DB mutation digest (both producers, both implementations): `05ad2c02…`.

## 11. Conformance thresholds (frozen)
`FACT`. Differential: validation-result / normalized-payload / canonical-byte / digest
agreement = 100% on valid items; error-category agreement = 100% on invalid items; V0.1
identity reproduction = 100%; identity-affecting differences = 0. Cross-domain: equal /
different / invalid / governance / deny relationships all as preregistered; cross-domain
collisions = 0; evidence/approval transfer rejected = 100%; ownership_no_runtime_switch =
true; regression digests unchanged.

## 12. Ambiguity-severity rules (frozen)
`FACT`. A difference in **validity** (valid vs invalid) or in **normalized payload /
canonical bytes / digest** is a **high-severity, identity-affecting** standards defect. A
difference only in the **error label** (both reject) is a `harmless_diagnostic`. Resolutions
are new normative language + new vectors (`CER_SPECIFICATION_ERRATA.md`); a frozen vector is
never edited, and implementations are never tuned to each other to hide an ambiguity.

## 13. Verdict rules (frozen)
- **Independent implementability** → `CER_INDEPENDENT_IMPLEMENTATION_CONFORMANT` iff the
  clean-room ran, imported no reference code, and agreed on payload+bytes+digest for every
  valid vector with 0 identity-affecting ambiguity; `…_LIMITED` if it ran with reduced
  coverage; `CER_SPECIFICATION_AMBIGUOUS` if an identity-affecting ambiguity was found;
  `…_FAILED` otherwise.
- **Cross-domain profile** → `CER_CROSS_DOMAIN_SUPPORTED` iff the database profile validates,
  produces distinct non-colliding identities, preserves binding, and passes governance, AND
  the ActionGate mapping is a genuine direct mapping with 0 core changes;
  `…_SUPPORTED_WITH_LIMITATIONS` if it required a versioned additive ActionGate operation or a
  fixture stand-in reduced coverage; `…_NOT_SUPPORTED` on collision/binding weakening/inaccurate mapping.
- **Governance portability** → `CONTROL_PLANE_CROSS_DOMAIN_SUPPORTED` iff the frozen
  ActionGate + the new ACP adapter reproduce all four composed outcomes for the database
  domain with 0 frozen-core changes and 0 runtime branch; `…_LIMITED` if a documented
  stand-in reduced coverage; `…_COUPLED` if a runtime/domain branch entered the frozen core.
- **Security** → `CER_SECURITY_INVARIANTS_HOLD` iff all §11 invariants hold;
  `…_LIMITATIONS_FOUND` for a non-exploitable gap; `CER_HIGH_SEVERITY_DEFECT` on any
  identity/binding/secret failure.
- **Draft maturity** → `CER_V0_3_READY_FOR_PUBLIC_REPOSITORY` iff: two independent
  conformant implementations; no identity-affecting ambiguity; two materially different
  domains (Kubernetes + database); no cross-profile collision; complete versioned vectors;
  no runtime-specific Control Plane branch; no unresolved high-severity security issue;
  backward-compatible with V0.1/V0.2. Else `…_READY_FOR_EXTERNAL_REVIEW` /
  `…_INTERNAL_DRAFT_ONLY` / `…_NOT_READY`. **No standards-body / industry-adoption claim.**

## 14. Environment limitations (frozen)
`FACT`. Two domains only (Kubernetes {scale,rollout} + database {mutation}); database DELETE
reserved. ACP over authored fixtures (no live cluster, no live database telemetry).
ActionGate reference HMAC signing (not production asymmetric custody). Deterministic
producers (no live LLM). Context Minimization skipped where its span contract is absent.
Nothing actuates; ACP shadow-only. Repo-local, deterministic. No post-hoc threshold tuning.
