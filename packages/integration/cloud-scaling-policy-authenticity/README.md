# Ugence Cloud Scaling Policy Authenticity — Phase 5B-0B

**A verified policy proof grants nothing.** It establishes that one exact policy version was
authentically issued and is valid at an injected instant, and stops. It is not an
authorization, not an envelope, not an ActionGate admission, not a credential, and not
permission to execute anything.

## The question it answers

Phase 5B-0A answered *did this recommendation come from a trusted producer?* This package
answers *did these policy limits come from the authoritative policy system, unchanged and
valid for this tenant, at this evaluation instant?*

Before it, Phase 5A carried a `PolicyTargetBindingReference` and said plainly that it never
asks the Policy Authority anything: its one trust state is `PRESENT_BUT_NOT_TRUST_VERIFIED`.

## What a `VERIFIED` outcome means, exactly

At the injected `as_of`, through the resolution port the composition root wired, the complete
six-component coordinate resolved to a **non-historical** `RESOLVED` answer. That answer
means the Policy Authority found a record under that exact coordinate, the stored artifact
still re-derived it and still canonicalized, the declared and signed body digests both
equalled the recomputed one, the issuance signature verified under a key of the named
authority that was un-revoked, in-window, tenant-permitted and entitled to `ISSUE_POLICY`,
external approval evidence held, the lifecycle was active, the instant fell inside the
effective period, and no verified revocation applied.

Then four gates this package adds on top, which the authority does not perform for a
consumer:

| Gate | Refusal | Why |
|---|---|---|
| a historical answer | `HISTORICAL_RESOLUTION_REFUSED` | a statement about the past cannot back an action about to be taken |
| the port answered another coordinate or instant | `RESOLUTION_ANSWERED_ANOTHER_QUESTION` | the port is injected, so the port is not trusted |
| `coordinate.content_digest != policy_body_digest` | `COORDINATE_DIGEST_UNBOUND` | issuance forbids it; resolution does not re-check it (residual R-3) |
| an algorithm outside the closed set | `UNSUPPORTED_ALGORITHM` | admission is this profile's, not the configured verifier's |

## What it does **not** establish

* **Not authorization.** `grants_authority` is a derived property that hard-returns `False`.
  No caller authorization happens anywhere in this chain: `expected_reference_tenant_id`
  checks the *reference's* declared tenant, never the caller's right to it.
* **Not bound to a recommendation, a scope or a candidate** — residual **R-4**, 5B-1's
  decision-scope repair. A candidate may be supplied; its digest is recorded as the scope of
  the determination and was **never reconciled** at 5B-0B, because a Phase 5A binding carries
  three of the coordinate's six components and cannot name a coordinate. One genuine policy
  proof therefore verified alongside any candidate whatsoever.
  `tests/test_candidate_not_bound.py` measures the original gap rather than describing it;
  gates 11-13 and 16 are what closed it.
* **The bounds the candidate carries — reconciled since R-8, when a candidate is supplied.**
  This line has been wrong twice. Before 5B-3 nothing extracted a bound at all; 5B-3 added
  extraction and this text still said extraction was out of scope. Gate 16 now selects the
  authenticated bound for the candidate's exact `(action_type, resource_class)` and refuses
  unless the candidate's ceilings **and its request** are within it. Extraction says "the
  signature covered these ceilings"; reconciliation says "this candidate is inside the one
  that applies to it".
* **Not an honest instant** — residual **R-2**, open. See below.

## The ratified rulings this implements

| Decision | Ruling |
|---|---|
| D-5B0B-1 | the verified artifact is a `PolicyResolution` that is `RESOLVED` **and** non-historical |
| D-5B0B-2 | `policy_body_digest` is the content binding; Phase 5A's `policy_artifact_digest` corresponds to neither digest and cannot hold a Policy Authority digest |
| D-5B0B-3 | the issuance signature covers all six coordinate components; a Phase 5A binding cannot name a coordinate |
| D-5B0B-4 | **option (a)** — verify through the Policy Authority's own `PolicyKeyRing`, not a lent Trusted Evidence Authority trust anchor |
| D-5B0B-5 | authenticity means "is valid now", judged at an **injected** `as_of`; no clock |
| D-5B0B-6 | the proof travels **alongside** the candidate; Phase 5A stays at `0.1.0` with all ten frozen digests unmoved — **superseded by D-5B1-1** (see below) |
| D-5B0B-7 | the digest payload partitions into a **verified** half and a **recorded** half, so an unattested fact is digest-covered without reading as attested |
| D-5B1-1 | the policy coordinate travels **inside** the candidate, so a determination can be reconciled against it; Phase 5A moves to `0.2.0` and one of its (now eleven) frozen digests moves |
| D-5B1-3 | the partition guard becomes a **ratchet** driven by repository history, so a promotion cannot ship without a profile-version bump |

### What 5B-1 changed here

Gate 11 reconciles a supplied candidate's `PolicyTargetBindingReferenceV2` against the
resolved policy — all six coordinate components, `policy_body_digest`, and the issuing
identity — and refuses a disagreement with `CANDIDATE_COORDINATE_MISMATCH`. That closes ADR
residual **R-4**: before it, one genuine policy proof verified alongside any candidate
whatsoever, including one whose policy binding named a different policy entirely.

`candidate_digest_fact` moved from the **recorded** half to the **verified** half as a result,
which moved the reference artifact digest and took `VERIFICATION_PROFILE_VERSION` to `v2` and
this distribution to `0.2.0`. `None` on that fact means no candidate accompanied the
determination — never that one was carried unchecked.

### Why option (a), and what it costs

Two measured asymmetries, both executable in the suite:

* `PolicyVerificationKey` carries `tenant_id` and the key ring enforces it; TEV's
  `TrustAnchorRecord` carries no tenant field, by ratified refusal. An artifact whose subject
  is "valid **for this tenant**" cannot be verified under an anchor that cannot express a
  tenant (`test_a_key_bound_to_another_tenant_cannot_authenticate_this_tenant_s_policy`).
* `KeyEntitlement` splits `ISSUE_POLICY` from `REVOKE_POLICY` on one key; TEV's capability is
  single-valued per anchor (`test_a_revoke_only_key_cannot_authenticate_an_issued_policy`).

The cost, recorded rather than discovered: `ugence-policy-authority` declares
`ugence-uvi-policy-contracts>=0.1.0` and its `api` module imports `.adapters.uvi`, so the UVI
contracts arrive transitively at the composition root even though Cloud Scaling would register
its own capacity-bounds adapter. The authority's generic core imports no UVI symbol.

Two trust systems now sit in one authorization chain — TEV's for producer attestations,
the Policy Authority's for policy. That is separation of concerns, not duplication: they
answer questions with different owners and different rotation authority. This package holds
**no keys, no key ring, no registry and no anchor records**; it delegates.

## Verified facts and recorded facts

`digest_payload()` is two separately framed maps, each carrying its own domain tag as a
canonical field:

* **`verified`** — the facts a gate actually checked: the six coordinate components, the body
  digest, the issuing authority and key, the record and adapter ids, the profile.
* **`recorded`** — carried and digest-covered, but **never attested**. Two members, two
  reasons:

  | Fact | Why nothing establishes it |
  |---|---|
  | `resolved_as_of_fact` | R-2 — the instant is injected and unvalidated |
  | `trust_configuration_digest` | reported by the resolution port about itself. The port is the seam to the authority, so any check here would be the port vouching for itself |

  Two facts have left this table since it was written, and the table listed them for longer
  than it should have. `candidate_digest_fact` was promoted to the verified half in **5B-1**,
  when gate 11 began reconciling the candidate's coordinate against the resolved one.
  `policy_type` was promoted in **5B-3**, when gate 14 began reproducing the signed body
  digest by reframing the resolution's descriptor projection — which supplied the pre-image a
  one-way hash had denied this package until then.

Being recorded does not mean unprotected — both halves are inside the artifact digest, so
neither can be rewritten after the fact. It means nobody checked it. Read a fact through
`verified_fact(name)` when you intend to act on something this package established;
`recorded_fact(name)` answers for the four that nothing did, and each accessor refuses the
other's half, so
an unattested value cannot arrive through a call that reads as attested. The partition is
total and disjoint over the artifact's fields, enforced at import: adding a field means
deciding which half it belongs to.

When 5B-1 closes R-4 and 5B-2 closes R-2, the corresponding fact is **promoted** into the
verified half — which moves the artifact digest, because the frame a fact sits in is part of
what that digest commits to.

## The open residual you must read before deploying

**R-2 — whose clock supplies `as_of` is unsettled, and this implementation proceeds with
`as_of` injected and unvalidated**, by explicit owner authorization. Five gates in the
resolution depend on it, so a determination reached at an attacker-chosen instant can resolve
a policy that is revoked, expired or not yet effective *now*. Binding `as_of` to a trusted
time source is 5B-2's envelope-issuance work. `TEMPORAL_OUTCOMES` names the members that
instant can move, and `resolved_as_of_fact` sits in the artifact's **recorded** half so the
artifact itself says the instant was not verified.

**R-4** is likewise visible in the artifact's shape rather than only in its prose:
`candidate_digest_fact` is in the recorded half because nothing reconciled it.

## Wiring it

```python
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
)

port = PolicyAuthorityResolutionPort(
    registry=policy_registry,            # durable; the authority's in-memory one is reference-grade
    signature_verifier=policy_key_ring,  # the Policy Authority's own PolicyKeyRing
    adapters=adapter_registry,
    approval_verifier=approval_verifier, # optional; supplying one re-verifies approval at as_of
)
verifier = PolicyAuthenticityVerifier(resolution_port=port, production_mode=True)

result = verifier.verify(
    coordinate=coordinate,                       # all six components, exact
    expected_reference_tenant_id=coordinate.tenant_id,
    as_of=instant,                               # injected; this package reads no clock
    candidate=candidate,                         # optional; when supplied, reconciled
)
if result.verified:
    proof = result.verified_policy               # binds the body by digest
    policy = result.resolution.policy            # the body itself, via the authority's type
else:
    refuse(result.outcome)                       # a typed member, never a message string
```

`production_mode=True` refuses a port that has not opted in, and a port standing on the
authority's reference-grade in-memory registry declines the opt-in on its own.
`DenyAllPolicyResolutionPort` is the production-admissible "trust not configured yet" posture,
because it can only refuse.

Revalidate a verified artifact with `require_verified_policy_authenticity(...)` at **every**
consumption boundary, not once at minting. A frozen dataclass is not a security boundary.

## Changing the artifact digest

The artifact digest has a merged definition now, so it is something a consumer can pin.
Anything that changes what `digest_payload()` covers — adding a fact, or **promoting one from
the recorded half to the verified half**, which is what 5B-1 does when R-4 closes and 5B-2
does when R-2 does — moves it.

When that happens, three things change in **one commit**:

1. the constants in `tests/test_frozen_digests.py`;
2. `VERIFICATION_PROFILE_VERSION` in `identifiers.py`;
3. a CHANGELOG entry naming which digest moved and why.

`FROZEN_PARTITION_FINGERPRINT` catches an *accidental* move: it covers the profile version
together with both halves' exact membership, so a change that did not intend to move a fact
fails there. It does not catch a deliberate one — the 5B-1 audit measured that promoting a
fact, updating both pinned constants and leaving the profile version alone passes that file at
5 passed, because the pin and the change land in the same commit.

`tests/test_partition_ratchet.py` is what enforces the rule (D-5B1-3). It takes its "before"
from **repository history** — the membership at the merge base, parsed out of the historical
source rather than imported — and fails when the partition moved without a bump, or when the
version moved with no changelog line naming it. CI resolves the baseline from the event's own
default branch and sets `UGENCE_RATCHET_REQUIRED=1`, so a baseline it cannot resolve fails the
workflow instead of skipping.

Four rules, not three. The fourth was ratified during R-8, after an audit measured that the
third disclosed only `verified ∩ baseline.recorded` — a fact that *moved* halves. A name
entering the verified half from **neither** baseline half had not moved; it had appeared, so
it was promoted by nobody, demoted by nobody, and asked about by nothing. The bump it forces
was already earned by whatever else the change did. Such a fact must now be disclosed on its
own line as `added: <fact> — <what establishes it>`, and the direction is part of the claim:
a `promoted:` line does not satisfy the disclosure an added fact owes.

Pre-merge this was free — three remediation rounds reshaped the payload at `0.1.0` while
nothing pinned a digest. That window is closed.

## Running the suite

```
python -m pytest packages/integration/cloud-scaling-policy-authenticity -q
```

No editable install is required in a checkout. Outside one, the suite runs against the
installed distributions and the candidate-dependent tests skip.

CI runs it on every pull request touching this package, the Policy Authority, Phase 5A or the
UVI contracts — see `.github/workflows/cloud-scaling-policy-authenticity-ci.yml`, which also
re-runs the two authorities this package stands on and asserts the suite actually collected
its properties rather than silently collecting none.
