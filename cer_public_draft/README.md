# Canonical Execution Request (CER) — Public Draft

**A versioned interoperability contract for governing autonomous-agent actions.**

CER is a runtime-independent, hashable representation of *exactly what an autonomous agent is
about to do*. A runtime **proposes** a CER; a governance layer **authorizes** it and clears it
against **operational safety**; the result returns to the runtime. Because the request is
canonical and provenance-excluded, the **same action from different runtimes has the same
identity**, so one governance layer can front many runtimes.

> **Status.** This is a **public draft** — a versioned interoperability contract **implemented by
> the Ugence AI Control Plane**. It is **not** an industry standard already adopted by the market,
> and this package makes **no claim of standards-body acceptance or industry adoption**. It is
> published to invite external review and independent implementations.

## What this package contains
```
README.md                     — this file
SPEC.md                       — normative specification (envelope, identity, canonicalization, hashing)
IDENTITY_PROFILE.md           — the v2 identity projection (what is / isn't in the action identity)
SECURITY_MODEL.md             — threat model and security invariants
VERSIONING_AND_EXTENSIONS.md  — versioning, profile-version negotiation, extension rules
GOVERNANCE.md                 — contribution / change-control model for the draft
schemas/                      — JSON Schemas: kubernetes.scale.v1, kubernetes.rollout.v1, database.mutation.v1
vectors/vectors.json          — conformance vectors (full CER input + expected digest)
reference/                    — clean-room reference implementation (Python standard library only)
conformance/run.py            — self-contained conformance runner
```
This package **deliberately contains no proprietary ActionGate or ACP internals.** The reference
implementation computes only CER validation, canonicalization, the identity projection, and the
digest — the parts that must be independently implementable for CER to be a real contract.

## Quick start
```bash
python conformance/run.py       # runs the reference impl over the vectors
```
```python
from reference import validate, normalized_payload, canonical_bytes, action_digest
validate(cer)                    # fail closed on any structural/profile/secret violation
action_digest(cer)               # the v2 action identity (hex)
```

## Conformance in one line
A conformant implementation, given a CER, must reproduce the **normalized payload**, the
**canonical bytes**, and the **digest** in `vectors/vectors.json` — **not merely the digest**. A
matching digest with a divergent normalized payload is a conformance failure.

## Proven properties (reference evidence, not adoption)
- **Independently implementable:** a clean-room implementation (this `reference/`) reproduces
  byte-identical canonical payloads and digests from the written spec, importing no reference code.
- **Runtime-independent identity:** identical actuation from three real runtimes → identical digest.
- **Cross-domain:** Kubernetes (scale, rollout) and database (mutation) profiles, no identity
  collision across domains.
- **Exact-action binding:** any material change alters the digest; approvals/evidence bind to it.

## License / contribution
See `GOVERNANCE.md`. This draft is offered for external review and independent implementation;
it is not a ratified standard.
