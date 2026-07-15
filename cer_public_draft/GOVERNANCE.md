# CER Draft Governance & Contribution (Public Draft)

## Status
CER is a **public draft** — a versioned interoperability contract **implemented by the Ugence AI
Control Plane**. It is **not** a ratified standard and makes **no claim of standards-body
acceptance or industry adoption**. It is published to invite external review and independent
implementations.

## Change control
- **Additive first.** New profiles and new identity/extension versions are additive; existing
  profiles and vectors are immutable.
- **No silent vector edits.** Corrections land as new vectors or versioned errata.
- **Conformance is payload+bytes+digest**, not digest-only. A second implementation must reproduce
  the normalized payload and canonical bytes, not merely the hash.
- **Identity-affecting ambiguity = high severity.** Any disagreement between independent
  implementations on validity, normalized payload, canonical bytes, or digest is a defect resolved
  by normative language + new vectors — not by tuning implementations to each other.

## How to contribute / evaluate
1. Implement the spec independently (a language other than the reference Python is encouraged).
2. Run your implementation against `vectors/vectors.json`; it must reproduce every normalized
   payload, canonical byte string, and digest.
3. Report any divergence with the CER input and your intermediate payload/bytes — that is a
   specification-review event.

## Non-goals
This package does not distribute proprietary ActionGate or ACP internals, does not assert market
adoption, and does not position CER as a finished standard. It positions CER as an open,
independently-implementable contract that the Ugence AI Control Plane implements today.
