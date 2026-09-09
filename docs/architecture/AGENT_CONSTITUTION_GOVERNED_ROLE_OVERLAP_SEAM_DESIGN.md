# Governed-role overlap — the family-neutral exclusivity seam, designed and enumerated

**Status:** design and enumeration only. **No source is changed by this
document**, and Policy Authority's public surface is untouched. It exists
because `ACC-OVL-7` requires the seam design and its enumeration to be recorded
**before** that surface changes.

**Governing rulings:** `ACC-OVL-1` – `ACC-OVL-8`
([`ADR_UGENCE_AGENT_CONSTITUTION_RECONCILIATION_SUSPENSION_AND_OVERLAP_RULINGS.md`](ADR_UGENCE_AGENT_CONSTITUTION_RECONCILIATION_SUSPENSION_AND_OVERLAP_RULINGS.md)).

**Baseline:** `7ebc03be`, the Policy Authority `0.4.0` suspension commit. Clean
tree, all scoped gates green.

**No constitution is issued or activated by this document, and no `ACC-FC-5`
gate is closed or advanced by it.** `ACC-OVL-4` binds throughout: no second
constitution issues until the invariant is implemented and verified.

---

## 1. The problem the seam exists to solve

`[V]` `governed_role_refs` lives **inside** the constitution artifact, and the
generic core is structurally forbidden to look at it: *"the generic core knows
nothing about any policy family: it never imports a family type, never branches
on one"* (`core/adapters.py`), and the core reads **only**
`PolicyArtifactDescriptor` fields.

So `ACC-OVL-2`'s split — the authority enforces, the adapter projects, conformance
mirrors — is only implementable if the thing the authority compares is
**family-neutral**. The adapter must hand the core something opaque, and the core
must enforce uniqueness over it without knowing what it means.

## 2. The seam

### 2.1 What an adapter projects

One new **optional** field on `PolicyArtifactDescriptor`:

```python
exclusivity_claims: tuple[ExclusivityClaim, ...] = ()
```

where `ExclusivityClaim` is a frozen, hashable, family-neutral triple:

| Component | Meaning to the core | Meaning in the constitution family |
|---|---|---|
| `namespace` | an opaque token scoping the claim, so two families can never collide | `"ugence.agent-constitution/governed-role"` |
| `subject` | an opaque token the core compares for **equality only** | one entry of `governed_role_refs`, NFC-normalised |
| `scope` / `tenant_id` | taken from the coordinate, never restated by the adapter | same |

`[R]` **The core never parses `subject`.** It compares normalised tokens for
equality. That is the whole of what makes the seam family-neutral: a second
family adding exclusivity semantics registers claims in its own namespace and
needs no core change, which is the property `test_second_adapter.py` exists to
protect.

`[R]` **Scope and tenant come from the coordinate, not from the adapter.** An
adapter that could restate them could widen its own claim's reach; taking them
from the coordinate makes "same tenant and scope" (`ACC-OVL-1`) structural.

### 2.2 Where the core enforces

**At issuance**, before the digest, before approval, before signing and before
any mutation — on `require_admissible_supersession`'s exact precedent (registry
reads only; nothing from a rejected artifact is ever stored):

> For each claim the candidate projects, if any **other** issued version is
> *simultaneously effective* and projects an equal claim, refuse — unless that
> version is the candidate's **explicitly verified supersession predecessor**.

**At resolution**, re-derived rather than trusted: a resolved version whose claim
is also held by another simultaneously effective version denies with a new
reason. `[R]` Issuance-time enforcement alone would be a check at the door on a
store that can be filled another way — the same reasoning that made every
suspension rule re-derive at resolution.

### 2.3 "Simultaneously effective", defined in the core's own terms

A version is effective at an instant when it would resolve there: lifecycle
active, `as_of` inside the half-open `[effective_from, effective_to)`, not
revoked, not superseded, not suspended. Two versions are **simultaneously
effective** when their effective intervals **overlap**, evaluated over the
half-open intervals rather than at a single instant — an overlap that begins next
month is still an overlap, and issuance must refuse it now rather than let it
arrive.

`[R]` **Neither registration order, mapping order, nor arrival order may break a
tie** (`ACC-OVL-3`). There is no tie to break: an unresolved overlap **refuses**.

### 2.4 The supersession exception, and only that one

`ACC-OVL-8`: the exception narrows to an **explicitly verified supersession
relationship** — the candidate declares the incumbent as its
`supersedes_coordinate`, and that supersession record verifies. `[R]` Delegation
is **absent from the current contracts and is not invented here**; it needs its
own contract and owner round covering delegated authority bounds, identity,
scope, duration, revocation, and the monotonic rule that delegated authority
cannot exceed issued authority.

### 2.5 What the constitution family must do

`ACC-OVL-7`: **fail closed if its required projection is missing, malformed or
unresolved.** The constitution adapter projects one claim per entry of
`governed_role_refs`; a constitution whose refs are absent, unnormalisable or
duplicated is refused at `describe` time, before it can reach issuance carrying
no claims and thereby appear to conflict with nothing.

`[R]` **This is the sharpest edge in the design.** An adapter that projects no
claims is indistinguishable, to the core, from an artifact with nothing to
claim — which is exactly right for families with no exclusivity semantics
(`ACC-OVL-7`), and exactly wrong for a constitution. The failure must therefore
be caught in the **family**, because the core cannot tell the two apart and must
not learn how.

---

## 3. The enumeration (`ACC-OVL-5`, discharged)

### 3.1 Producer — `PolicyResolutionReason`

`[V]` 24 members at this baseline. **One** member is added:

| New member | Meaning |
|---|---|
| `EXCLUSIVITY_CONFLICT` | Another simultaneously effective version holds an equal exclusivity claim, and no verified supersession relationship permits it. The overlap is unresolved, so resolution refuses rather than choosing |

`[R]` One member, not two. The suspension round needed a second
`*_INTEGRITY_INVALID` member because it introduced a **store** whose history
could be malformed. This round introduces no store of signed records: claims are
projected from artifacts already verified by the time they are compared, so there
is no separate integrity failure mode to name.

### 3.2 Consumer — `cloud-scaling-policy-authenticity`

`[V]` The mapping is asserted **total** and **injective** over the producer's
non-`RESOLVED` members, so one member here is mandatory, not optional:

| Producer reason | Consumer outcome member |
|---|---|
| `EXCLUSIVITY_CONFLICT` | `EXCLUSIVITY_CONFLICT` |

`[V]` It does **not** join `TEMPORAL_OUTCOMES`. A conflict is a property of two
artifacts' declared intervals, not of the injected `as_of`: moving `as_of` cannot
make an unresolved overlap resolved.

### 3.3 Every other site the change touches

| Site | What it needs |
|---|---|
| `core/adapters.py` | `ExclusivityClaim`; the optional descriptor field |
| `core/exclusivity.py` (new) | claim normalisation, interval overlap, the comparison, the supersession exception |
| `core/issuance.py` | the pre-signing refusal |
| `core/resolution.py` | the re-derived check and the new reason |
| `core/errors.py` | `PolicyExclusivityError` |
| `core/registry.py`, `core/registry_sqlite.py` | a claims index, so the comparison is a lookup and not a full scan; **sqlite schema → `v3`** |
| `agent-constitution-policy/adapter.py` | project one claim per governed role; fail closed on a missing or malformed projection |
| `agent-constitution-conformance` | the mirrored check and its diagnostic evidence (`ACC-OVL-2`) |
| `policy-authority/public_api.json`, version | additive minor; two new names, one new enum member, one new descriptor field |
| `cloud-scaling-policy-authenticity` | one outcome member, one mapping entry, additive minor — **and its pin on the authority's version moves again** |

`[V]` **The version pin is not an obstacle**: it is designed to move, and moving
it is how an authority change surfaces in a consumer
(`test_phase5a_untouched.py`, `ACC-LC-IA-BASE-A1`). Recorded because the
suspension round found it the hard way, after the `ACC-SUSP-4` enumeration had
missed it.

---

## 4. Compatibility impact — the `ACC-OVL-7` stop-condition

The ruling requires a stop-and-report **if adding the generic seam changes
existing adapter obligations or serialized descriptors**. Both were checked
directly against the tree at the baseline:

**Serialized descriptors: none exist.** `[V]` `PolicyArtifactDescriptor` is
constructed by adapters and consumed by the core, and is **never serialized** —
it appears in neither `core/codec.py`, `core/registry.py` nor
`core/registry_sqlite.py`. `IssuedPolicyRecord` stores descriptor-*derived*
scalars (`adapter_id`, `policy_type`, `policy_body_digest`), not the descriptor.

**No digest moves.** `[V]` `body_digest()` is
`framed_body_digest(adapter_id, policy_type, canonical_projection)`. A descriptor
field outside `canonical_projection` is not covered by any digest, so every
digest issued to date — the ratified `ACC-FC` content's included — is unmoved.

**Existing adapter obligations: unchanged.** `[V]` Four adapters construct
descriptors (`uvi`, `agent-constitution-policy`,
`agentic-proposer-strategy-permission-policy`,
`cloud-scaling-capacity-bounds-policy`), all by keyword. An optional field
defaulting to `()` leaves all four constructing and behaving identically;
`ACC-OVL-7`'s "families with no exclusivity semantics produce no claims" is the
default, not an opt-out they must write.

**Therefore the stop-condition is `[V]` NOT triggered.**

`[R]` One consequence is recorded rather than left implicit: the change **is**
still a Policy Authority **public surface** change — `public_api.json` pins
dataclass field sets and order — and `ACC-OVL-7` requires this document to exist
before it. That requirement is what this document discharges; it is not a
compatibility break.

---

## 5. What remains open

`[G]` **The claims index is a storage-shape decision.** Comparing a candidate
against "all simultaneously effective versions" is a scan unless the registry
indexes claims. Indexing them means a `v3` sqlite schema and a new Protocol
method on both registries. That is inside `ACC-OVL-7`'s grant, but it is the
largest single piece of the change and is called out so it is costed rather than
discovered.

`[G]` **Conformance's mirrored check has no enforcement power and must not
appear to.** `ACC-OVL-2` is explicit that conformance cannot be the sole
enforcement boundary. The mirrored check produces **diagnostic evidence**; the
package's existing disclosure — that presented facts are a caller assertion
(`ACC-FACTS`) — applies unchanged to what it reports.

`[G]` **The invariant will be unexercisable on the day it lands**, exactly as
suspension and supersession are: no constitution has been issued, and
`ACC-FC-5` gates 1 and 2 remain unadvanceable by any pull request. `ACC-OVL-4`
is what makes the gap harmless in the meantime, and it holds whether or not the
implementation has landed.

**Next step:** implement §2 and §3 as one change set, family half and core half
together — the two halves are only meaningful jointly, on `ACC-S1-Q2`'s
precedent.
