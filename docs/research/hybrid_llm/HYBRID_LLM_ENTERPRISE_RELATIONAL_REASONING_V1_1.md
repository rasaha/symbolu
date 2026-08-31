# Hybrid LLM for Enterprise Relational Reasoning — Training–Inference Architecture, Bounded Memory, Event Processing, and Validation Thesis

**Version 1.1 · 6 August 2026**
**Research status: research hypothesis under validation — NOT a production-readiness claim.**

> **About this version.** No editable canonical Markdown source for the Version 1.0 thesis (4 August 2026)
> was found in the repository at revision time. This Version 1.1 is therefore established as the canonical
> editable source, reconstructing the thesis structure and updating every evidence-dependent claim from the
> **merged** repository evidence (PRs #1344–#1361). Where a claim depends on an experiment, the exact merged
> verdict token is cited. See `HYBRID_LLM_V1_0_TO_V1_1_CHANGELOG.md`.

## Current evidence summary (replaces the "primary unresolved dependency" framing)
| Item | Status |
|---|---|
| Anonymous BindingSlots neural routing | **Unresolved** (`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`) |
| Explicit-key E1 semantic addressing | **Independently confirmed on controlled synthetic tasks** (`EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`, `E1_INDEPENDENTLY_CONFIRMED`) |
| Temporal latest-state transfer | **Partial** (`E1_TEMPORAL_TRANSFER_PARTIAL`) |
| C1 temporal-patching track | **Closed** (`T4_FACTORIAL_NO_INTERVENTION_SELECTED`) |
| Bounded frozen-readout diagnostic track | **Closed** (`FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`) |
| External relational database / table | **Operational source of truth under tested deterministic conditions** |
| KDA validation | **Blocked** (`KDA_VALIDATION_BLOCKED`) |

BindingSlots is **not** an operational dependency. Deterministic retrieval over an authoritative relational
database is the operational foundation; the neural layer is a bounded reasoning component under validation.

---

## 1. Executive thesis
**Preserved system thesis (unchanged):** the relational database remains authoritative; deterministic
authorization and retrieval happen **before** model reasoning; the model reasons over a **bounded authorized
working set**; evidence and proposed actions are governed **separately** from execution.

**Revised neural-memory positioning:**
- BindingSlots are **not** an operational dependency.
- Anonymous BindingSlots neural routing remains **unresolved**.
- **Explicit semantic-key addressing** is the supported neural-memory result — **only on controlled
  synthetic tasks**. It is **not** validated on enterprise data.
- Deterministic retrieval remains the operational foundation.

## 2. Architecture (primary operational path)
The following is the **primary operational architecture** (promoted from prior "fallback"):

```
Authorized deterministic retrieval
  → typed entity / relation / event working set
    → bounded reasoning
      → evidence-grounded answer or proposed action
        → ActionGate / human approval / policy enforcement
```

The relational database (SQL, joins, indexes, transactions, authorization, row-level security, durable
storage) is authoritative. The model receives a small authorized working set and never replaces the
database.

**BindingSlots relabel:** *"Optional research pathway; not required by the operational architecture."*
Component tables, figure captions, and surrounding text must not imply that enterprise reasoning depends on
BindingSlots.

> **Version 1.1 architecture note.** Any legacy figure that places BindingSlots on the operational critical
> path is superseded by this note: the operational dependency boundary is **deterministic retrieval →
> bounded reasoning → governed action**. BindingSlots (and any neural memory) sit *inside* "bounded
> reasoning" as an optional, still-under-validation research component — never on the retrieval or
> authorization path.

## 3. Typed representation (design hypothesis + limitation)
Typed entities, explicit relations, event records, evidence references, tenant scope, and schema metadata
remain **architectural design hypotheses** and are retained.

**Explicit limitation (added):** *Explicit-key E1 outperforming anonymous slots does not establish that
typed structured records outperform flattened prose in a real pretrained language model.* Typed-input
superiority over prose remains an **untested hypothesis** requiring a separate benchmark (see §11.A).

## 4. BindingSlots (current evidence)
- Anonymous BindingSlots can **store** usable values.
- Ordinary neural **read-address routing** remains **unreliable**.
- The **A1** hard-negative / read-address intervention was **not selected**.
- The **G1** gradient-isolation intervention was **not selected**.
- **External-table reliability** was **verified under tested conditions**.
- **Confidence-triggered fallback** missed confidently-wrong reads (it did not reliably detect errors).
- **Always-verify** produced exact tested answers but required **one table read per query** and was **far
  slower than table-only** in the reference benchmark.
- **Original BindingSlots neural routing remains unresolved**
  (`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`).

**No further BindingSlots optimization sweep is presented as the next roadmap step.**

## 5. Explicit-key E1 (successor evidence)
- Explicit **semantic-key** matching materially **outperformed** anonymous BindingSlots.
- It **independently replicated** on controlled synthetic semantic-matching tasks.
- Evaluation used approximately **32 competing episode-local memories**.
- The result supports **semantic neural addressing within the tested controlled task**.
- It does **not** repair anonymous BindingSlots.
- It does **not** prove enterprise transfer.
- It does **not** replace the external database.
- It does **not** unblock KDA.

Verdicts: `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED` · `E1_INDEPENDENTLY_CONFIRMED`.
Preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.

## 6. Temporal reasoning
**Supported only on controlled synthetic tasks:** direct semantic retrieval · unseen-identity retrieval ·
paraphrase generalization · confusable-record discrimination · explicit position-indexed retrieval ·
bounded no-match behavior.

**Partial or unresolved:** latest-state inference · predecessor/successor reasoning · multi-event state
reduction · historical enterprise-state reconstruction · policy-version reasoning on real enterprise data ·
natural-language temporal transfer.

**Evidence chain:** temporal transfer `E1_TEMPORAL_TRANSFER_PARTIAL` → T4 shortfall `T4_SHORTFALL_MIXED` →
minimal three-factor interventions `T4_FACTORIAL_NO_INTERVENTION_SELECTED` → bounded frozen readouts
`FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`.

**Bounded closure:** *The tested C1-level and bounded frozen-readout approaches did not recover sufficient
latest-state capability. No further C1 or frozen-readout intervention is authorized.* This does **not** claim
all temporal neural architectures are impossible.

## 7. External-table and operational reliability
- **Table-only** retrieval was **exact** under the tested reference conditions.
- **Always-verify** (neural-plus-table) was also **exact** under those conditions.
- Always-verify required a **table read for every query**.
- In the reference benchmark, **neural inference dominated latency** and was **far slower than table-only**.
- The neural layer must justify itself through **reasoning value, not exact-lookup reliability**.

Reference-backend latency is **not** generalized to production infrastructure; no production-reliability
claim is made from the synthetic/reference tests.

## 8. Validation program (distinct tracks)
BindingSlots confirmation is **no longer** an assumed prerequisite for all subsequent work.

**Operational foundation:** deterministic interface correctness · authorization and tenant scoping · typed
working-set contracts · evidence integrity · external-table reliability · governance separation.

**Neural capability research:** explicit-key semantic addressing · structured relational reasoning ·
temporal-state reasoning · optional bounded relational reader · quality preservation · real-model transfer.

**Completed evidence (honest):** explicit-key semantic addressing — **controlled-task confirmed**; temporal
transfer — **partial**; C1 bounded temporal interventions — **closed**; frozen-readout diagnostic — **signal
not found**.

## 9. Development roadmap (status-based, not approved phases)
1. **Deterministic retrieval & authority separation** — operational foundation; database remains
   authoritative.
2. **Explicit-key semantic addressing** — independently confirmed on controlled synthetic tasks.
3. **Temporal latest-state reasoning** — partial; current C1 and bounded-readout tracks **closed**.
4. **Structured relational benchmark** — future research option; **not authorized**.
5. **Optional bounded relational reader** — future ablation option; **not authorized**.
6. **Real-model adaptation & quality preservation** — future research option; **not authorized**.
7. **Read-only enterprise shadow pilot** — future option only after preceding gates; **not authorized**.
8. **KDA** — validation **blocked**.

Future items are **not** approved execution phases.

## 10. Supported and unsupported claims
**Supported on controlled synthetic tasks:** explicit-key semantic addressing · bounded semantic matching
at the tested density (~32 episode-local memories) · deterministic external-table reliability under the
tested reference conditions · authority separation and bounded working-set contracts as implemented system
controls where evidence exists.

**Partially supported:** structural temporal transfer · no-match behavior · a bounded latest-state signal
under some conditions, **below required gates**.

**Not currently supported:** anonymous BindingSlots reliability · reliable latest-state inference ·
predecessor/successor reasoning · multi-hop enterprise relational reasoning · typed structured input
superiority over flattened prose in a real model · arbitrary enterprise schema generalization · real-model
quality preservation · efficiency superiority · bounded quadratic-reader benefit · production readiness ·
autonomous action authorization · KDA readiness.

("Controlled synthetic task" qualifiers apply wherever relevant above.)

## 11. Future research menu (explicitly UNAUTHORIZED)
A. flattened prose versus typed structured input · B. single-hop and multi-hop relational reasoning ·
C. foreign-key and join-path causal ablations · D. evidence grounding · E. tenant-isolation stress testing ·
F. schema-version and drift handling · G. optional bounded relational-reader ablation · H. real-pretrained-
model quality and efficiency · I. read-only shadow pilot · J. any genuinely new temporal successor
architecture.

**Each item requires its own preregistration and explicit authorization. Inclusion in this roadmap does not
authorize implementation or execution.**

## 12. Conclusion
The Hybrid LLM system architecture remains viable as a **bounded, evidence-grounded reasoning layer over an
authoritative relational database**. **Explicit-key semantic addressing is supported on controlled synthetic
tasks.** **Anonymous BindingSlots, reliable temporal-state reasoning, enterprise relational transfer, and
KDA remain unresolved.** **Deterministic retrieval remains the operational foundation.** No production-
readiness claim is made.

---

See `HYBRID_LLM_ENTERPRISE_RELATIONAL_REASONING_V1_1_STATUS_MATRIX.md` for the capability status matrix and
`HYBRID_LLM_V1_0_TO_V1_1_CHANGELOG.md` for the change log.
