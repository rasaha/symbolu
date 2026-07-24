# Prior Results & Scope (Phase 1)

*This track — Claim Decomposition and Semantic Scope Integrity (ClaimIntegrity) — investigates the
upstream assumption every downstream governance layer silently makes: that the claim being evaluated is
the claim the model actually made. This document freezes what the prior tracks concluded and states why
that assumption is worth a study of its own. All prior outcome-bearing artifacts are hash-pinned in
`claim_integrity/verify_prior_artifacts.py`, which fails on drift.*

## What the prior tracks established

**AGE (Assertion Governance Engine).** A falsification-first study of assertion governance concluded
governance value is real but **only for high-risk domains** — a calibrated, simple rule captures most
of it; elaborate machinery is not justified for low-risk assertions.

**AssertionGate noisy-signal robustness.** Concluded **keep only for high-risk** as the simplest
calibrated rule; correlated failure across signals defeats every method equally, so added method
complexity does not buy robustness when the signals share a fault.

**EvidenceAssurance (immediately prior track).** Provenance-, independence-, alignment-, freshness-,
authority-, and counterevidence-aware verification reaches **zero correlated-failure escape** on
tell-bearing failures at a noise-floor false-block, while signal-only baselines and a learned
comparator escape 0.67–1.00. Adopted as an upstream, high-risk-gated evidence-verification stage
feeding a thin AssertionGate — not a product, not an 11th module.

**The no-tell ceiling.** EvidenceAssurance escapes **100%** on a correlated failure that leaves no
observable metadata trace (model consensus on a false premise, training-data contamination). No
metadata-based evidence method can catch a failure that leaves no trace.

## The assumption this track attacks

Every one of those results is conditioned on a premise stated explicitly in the EvidenceAssurance
conclusion:

> **EvidenceAssurance assumes that the correct claim has already been extracted from the model output.**

Grounding, entailment, evidence retrieval, provenance analysis, and delivery all evaluate *a claim*.
If that claim is not what the model actually asserted — if decomposition dropped a qualifier, inverted
a negation, broadened a population, converted a correlation to a cause, or detached a citation — then
**every downstream decision is computed against the wrong proposition**. The evidence query itself is
built from the altered claim; the evidence can be impeccable and the verdict still wrong.

This is a distinct failure surface from the ones prior tracks studied:

- AGE / AssertionGate ask: *given a claim and signals, what do we deliver?*
- EvidenceAssurance asks: *given a claim and evidence, is the evidence sound and independent?*
- **ClaimIntegrity asks: is the claim we are about to govern the claim that was actually made?**

A semantic-drift error here is not caught by any downstream layer that trusts the claim it receives.
It is, in the vocabulary of the prior track, a **correlated failure that originates before evidence
evaluation** — and potentially a *no-tell* one, because a fluent altered claim carries no signal that
it differs from the original.

## Scope of this study

**In scope:** whether natural-language outputs can be decomposed into atomic, governable claims without
altering meaning, scope, qualifiers, negation, modality, uncertainty, temporality, numerics,
population, jurisdiction, causality, attribution, or evidentiary status; how often decomposition
changes practical meaning; which semantic dimensions are most fragile; whether decomposition errors
explain downstream failures; whether simple methods suffice; and whether a distinct ClaimIntegrity
stage is justified.

**Explicitly out of scope (and not modified):** EvidenceAssurance and its corpus/manifests;
AssertionGate and its robustness artifacts; AGE; ExecutionGate; ModelPolicy; ActionGate; TAP; the
Unified Control Plane; prior shadow-pilot artifacts; prior evaluation outputs; prior ground-truth
labels. Downstream components are consumed only through **fixed read-only adapters** for the
downstream-impact experiment (Phase 18).

**Method discipline:** deterministic local fixtures; no live provider calls; no unrestricted web
retrieval; no real-world actions; no production integration; enforcement off. The primary outcome
dataset is **new** (Phase 6) — prior final-evaluation corpora are not reused as the outcome dataset.

## Falsification posture

The objective is **not** to prove ClaimIntegrity deserves to exist. The core hypothesis — that a
meaningful fraction of downstream governance failures originate in claim decomposition — is stated with
explicit rejection conditions (Phase 5). If sentence splitting performs as well, if decomposition
errors rarely change downstream decisions, or if downstream layers absorb the drift, the study will say
so and recommend against a distinct component.
