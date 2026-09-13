# ugence-change-effect-records

**Contracts only. Inert by construction, and not a classifier.** The shapes a GERL
classification chain is written in: thirteen frozen, digest-bound record types, the
canonical-bytes profile that fixes their identifiers, the closed vocabularies they use,
and the admission succession tables as data. Scoped by
`docs/architecture/ADR_UGENCE_CHANGE_EFFECT_CLASSIFIER_SCOPING.md` (CEC-1 to CEC-5) and
`docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md` (item 3.3, with
the admission data of item 3.6), against GERL target classification version 4.2.10 and
its recorded erratum.

> This package holds shapes. It **never** classifies, measures, replays, projects,
> routes, resolves policy, admits, samples, reads or writes governed memory, or
> registers anything. A record is a shape, not a finding, and not a permission.

## What "contracts only" means here

Frozen dataclasses, closed enums, pure identifier derivations, canonical digests, and
refusal codes. **No classifier, no replay harness, no probe set, no anchor store, no
justification graph, no sampler, no projection, no routing rules, no policy resolver, no
admission boundary, no executor, no store, no clock, no network.** Nothing here could
produce a classification, act on one, or hand one to anybody, so the lines the rulings
draw are held structurally rather than by discipline — and the boundary tests assert
exactly that over source, AST and metadata.

The things the types deliberately do *not* do are the point of them:

* **They compute nothing across records.** Every digest is a caller input. No type
  resolves, dereferences or verifies another record, and no exported callable accepts
  two records and returns a conclusion about them.
* **They recompute no projection and re-apply no routing rule.** A `FinalResolutionRecord`
  carries the producer's assertion that the effective obligation set is empty; the Stage 3
  verifier recomputes that rather than believing it, and nothing here recomputes anything.
* **They derive no closure bundle.** The independent evaluator signs a raw evaluation
  result; the policy-governance-owned `ClosureBundleMapping` derives the canonical bundle.
  This package holds the bundle's shape and neither derives nor checks it.
* **They drive no state machine.** `LEGAL_SUCCESSIONS` and `CONTROL_REGISTER_TRANSITIONS`
  are data. The guarantee behind them is the audit root's atomic conditional append, which
  is not in this package and is not verified to exist anywhere.

## The identifiers, and why they are shaped as they are

`chain_id` and `obligation_id` are derived, never chosen, and never circular: an
identifier computed over its own record's digest could not be constructed at all, because
the record cannot be digested until its identifiers are known. `chain_id` therefore takes
only what step 0 fixes — tenant, candidate, anomaly family, family seed, and the
classifier-issued chain instance that distinguishes a resubmitted candidate from its
predecessor. `obligation_id` takes the chain plus the introducing record's *role* as a
constant, never its digest. Identifiers are unique and stable within one chain and are not
comparable across chains.

The byte projection is the repository's existing `_canon.py` envelope — namespace, U+001F
separator, schema version, sorted-key compact JSON, SHA-256 — with a **profile** on top
that the envelope does not itself impose: recursive NFC, absent fields omitted rather than
null, integers only within signed 64 bits, **JSON booleans refused outright** so a flag can
never be confused with a count, and the full 64-character digest, never truncated. Rule
section 6a publishes eight test vectors; `tests/test_identifiers.py` reproduces them from
this implementation, so the document and the code check each other.

## Status

Stage 1 substrate, authorized as tracked work by the owner on 2026-09-13 (ADR §8). The
design it implements is conditionally ratified, and **ratifying a design authorizes no
operation**. **No provider registers, no runtime path reaches this package, and progress
beyond Stage 1 is unauthorized** until archive custody exists, the audit root is verified
to supply the required linearizable operations, governed memory is verified to supply
atomic target-version compare-and-apply, the `[R]` parameters are ratified, and the owner
issues a separate authorization.
