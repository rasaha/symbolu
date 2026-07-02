# Primitive Sequence Recovery — Project Status & Next Phase (docs only)

**Analysis only. Nothing implemented, downloaded, or changed.** No code, no assets, no schema
change, no `manifest_v2`, no manifest edit, no READY, no run, no scores. `manifest.json` stays
**NOT_READY**; runner stays **NOT_RUN**; Stage A untouched.

**Accepted premise (not re-litigated):** per `CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`, a
non-circular concept resolver is **not achievable with resources available in this environment**.
This document accepts that fully and does **not** attempt to rescue the confirmatory claim. It
determines the strongest scientifically defensible **stopping point publishable today**.

---

## Executive recommendation

**Freeze the repository as Version 1 of the *evaluation framework* — a pre-registered,
freeze-gated, reproducible methodology plus a documented *blocked* confirmatory result.** The
project cleanly splits into **Track A (representation/ontology framework) — COMPLETE and
publishable** and **Track B (semantic realization) — BLOCKED**. Publish Track A; report Track B
as blocked; withdraw the near-term confirmatory and concept-channel-independence claims; keep the
English lexical channel only as a control/baseline. **Do not run a confirmatory experiment** — it
is not reachable with non-circular, offline resources.

---

## COMPLETED (fully specified, frozen, validated)

- **Ontology** — word → varṇa → **opaque primitive atom** (`assignment.json`, 34 atoms,
  injective, semantics-free; enforced by the gate's prohibited-content scan).
- **Canonical representation** — ordered opaque-atom sequence + the **relabeling-invariance
  theorem** (`CANONICAL_PRIMITIVE_REPRESENTATION.md`, `canonical.py`, tests): the assignment is
  invisible at the opaque level; content is testable only through a realization. This is a
  *proven property*, not a hope.
- **Realization separation** — all content lives in realizations (`en_gloss`, `sa_term`,
  `concept_id`); the assignment carries none; the gate rejects semantic leakage into it.
- **Freeze pipeline** — 8 JSON schemas + `SCHEMA_SPECIFICATION.md`; sha256 hashing;
  immutability/versioning rules.
- **Readiness gate** — `manifest.py::check_readiness` with hash verify, schema validation,
  referential integrity, independence, and hard NOT_READY blockers (unimplemented realizer,
  no model asset, no concept resolver, run disabled). Tested.
- **Pre-registration** — `PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md` with MRR/Top1, assignment- and
  order-scramble nulls, family bootstrap, and the cross-realization decision labels
  (`ONTOLOGICAL_SIGNAL / REALIZATION_ARTIFACT / NO_SIGNAL / REALIZER_DEPENDENT / INCONCLUSIVE`).
- **Baselines** — Phase-1 `LexicalOverlapRealizer` (Jaccard) and Phase-2
  `OrderSensitiveLexicalRealizer` (LCS), behind a stable `Realizer` interface; deterministic,
  offline, tested. **Plumbing validators only.**
- **Validation harness** — scaffold + gate + baseline test suites (all green); decision-logic and
  scramble-null logic implemented and unit-tested on synthetic data.
- **Frozen inputs** — `word_list` (107 active, collisions excluded, `family_id` refined),
  `meaning_reference` (+ per-realization refs), `distractors` (K=8, balanced, seed-frozen),
  `realizer.json` (interface, NOT_IMPLEMENTED), `run_params.json` (run_enabled=false),
  `manifest.json` (NOT_READY).
- **Design/audit record** — the full doc suite (implementation plan, semantic-realizer
  evaluation, offline-asset audit, PyPI audit, concept-resolver circularity audit).

## BLOCKED (cannot proceed with current, non-circular, offline resources)

- **Offline embedding asset** — BLOCKED. Firewall allows only PyPI; no PyPI wheel bundles usable
  semantic vectors (`PYPI_SEMANTIC_ASSET_AUDIT.md`); all real vectors/WordNet route through the
  blocked proxy.
- **Sanskrit realization (`sa_term`) scoring** — BLOCKED. No offline Sanskrit vector/lexical
  asset available.
- **Non-circular concept resolver (`concept_id`)** — BLOCKED. The decisive blocker: locally-
  buildable graphs are circular (F5); Sanskrit-grounded ontologies (IndoWordNet, classical
  taxonomy) are unobtainable here; English-mapped WordNet is F2/F3-circular.
- **Confirmatory cross-realization run** — BLOCKED. Requires ≥1 non-circular non-text channel,
  which does not exist here.
- **`ONTOLOGICAL_SIGNAL` verdict** — BLOCKED (and, absent an independent *second meaning source*,
  necessary-not-sufficient even if unblocked — the shared-source ceiling F4).
- **`manifest_v2` / READY / experiment execution** — BLOCKED, correctly, by all of the above.

## WITHDRAWN (stop asserting these)

- **"A confirmatory test is reachable soon."** WITHDRAWN — reclassified as BLOCKED. It is not
  near-term with non-circular, offline resources.
- **"`concept_id` is an independent confirmatory channel."** WITHDRAWN — as currently sourceable
  it is circular/redundant; demote to exploratory/robustness or drop.
- **"English lexical performance bears on Symbol-U."** WITHDRAWN — an English-only positive is
  capped at `REALIZATION_ARTIFACT`; it is a control, not evidence for the theory.
- **Not withdrawn:** the *theory itself* is **untested, not disproven** — we do not claim to have
  falsified Symbol-U; we claim the confirmatory test is currently unreachable. And the
  *framework* stands.

## FUTURE (optional, each gated on explicit approval + unblocking)

- Vendor a hash-pinned **English vector slice** (Option 2) → an **exploratory, control-grade** en
  run (ceiling: `REALIZATION_ARTIFACT`).
- Acquire an offline **Sanskrit** vector/lexical resource → `sa_term` scoring.
- Acquire a **Sanskrit-grounded concept ontology** + build a resolver passing C1–C3
  (incl. the run-time decorrelation gate) → *possibly* unblock the confirmatory channel.
- Add a genuinely **independent second meaning source** to escape the shared-source ceiling (F4)
  — the deepest missing piece.
- **Hard-negative (matched) distractors**; **larger corpus / power analysis** (N=107 is small).
- Only after all the above: `realizer.json → IMPLEMENTED`, `run_enabled=true`, author
  `manifest_v2.json`, and run the pre-registered protocol.

---

## Answers to the review questions

**1. Fully specified?** Yes for: ontology, canonical representation, realization separation,
freeze pipeline, readiness gate, pre-registration, baselines, validation harness (all under
COMPLETED). No experiment execution engine (deliberately absent).

**2. Testable now (and informative)?** Only claims about the **framework**: determinism,
offline-ness, order-sensitivity capability, gate correctness, and the relabeling-invariance
theorem. These are tested and hold.

**3. Untestable now?** Every **semantic** claim: `ONTOLOGICAL_SIGNAL`, the `sa_term` and
`concept_id` channels, and "varṇas carry intrinsic recoverable meaning." Blocked by asset +
circularity constraints.

**4. Withdraw entirely?** The near-term confirmability claim, the concept-channel-independence
claim, and any implication that English lexical scores bear on the theory (see WITHDRAWN). Keep
the theory as *untested*, and keep the framework.

**5. Is the English lexical channel still valuable (concept channel abandoned)?** **Yes — but only
as:** plumbing validation ✓, **negative control ✓ (leakage detector: it should be near chance;
if it is not, that flags gloss↔meaning token leakage)**, sanity baseline ✓, and publication
appendix ✓. **Not** as evidence for Symbol-U.

**6. Track A vs Track B?** **Yes, the project divides cleanly, and only Track B is blocked.**
Track A = the opaque-primitive ontology, canonical representation + relabeling-invariance theorem,
and the freeze/gate/reproducibility framework — **complete and publishable**. Track B = semantic
realization (embeddings + non-circular concept resolver) — **blocked**.

**7. Freeze current repo as Version 1?** **Yes.** Freeze it as *Version 1 of the evaluation
framework* — a self-consistent, reproducible, falsifiable methodology with frozen inputs,
baselines, and a gate that correctly refuses to run. It is a legitimate methods + negative-
infrastructure contribution; it is **not** a result about varṇa semantics and must not be
presented as one.

**8. Still missing before any honest semantic claim?** (i) an offline hash-pinned English vector;
(ii) a Sanskrit resource; (iii) a **non-circular, Sanskrit-grounded concept resolver** passing
C1–C3; (iv) the run-time decorrelation gate; (v) a **genuinely independent second meaning
source** (to beat the shared-source ceiling); (vi) hard-negative distractors; (vii) adequate
statistical power. Items (iii) and (v) are the hard ones; without them, no confirmatory claim is
honest.

**9. Roadmap** — see COMPLETED (done), BLOCKED (cannot proceed now), FUTURE (optional, approval-
gated) above. The one-line shape: *framework done → confirmatory blocked → optional exploratory
en run + resource acquisition, each behind approval → confirmatory only if a non-circular concept
channel and an independent meaning source both materialize.*

**10. Overall assessment.**
- **Scientific rigor: HIGH.** Pre-registration, opacity, a proven invariance theorem, adversarial
  self-audits, and — decisively — the willingness to declare the confirmatory claim **blocked**
  rather than manufacture it.
- **Reproducibility: HIGH.** Hash-pinned frozen inputs, deterministic baselines, seed-frozen
  distractors, dependency-free validator, green tests. Caveat: there is **no real result to
  reproduce** — reproducibility is of the *framework*, not of a finding.
- **Falsifiability: HIGH in design, currently LATENT.** Clear nulls and decision labels (incl.
  `NO_SIGNAL`) make the design falsifiable, but the confirmatory falsification is **blocked**, so
  no falsifying test has yet been run. The framework is falsifiable; the theory has not been put
  to a falsifying test.
- **Engineering quality: HIGH for scope.** Clean `Realizer` interface, a correct gate, isolated
  tests, no Stage A coupling, no heavy dependencies.
- **Remaining theoretical risks:** (a) **shared-source dependence (F4)** — the deepest: even a
  future "signal" could be a property of the *glossing*, not the varṇas, unless an independent
  meaning source exists; (b) realization/encoder dependence; (c) English/Sanskrit lexical
  confounds; (d) small N and easy distractors; (e) **practical unfalsifiability** — if no
  independent meaning source is ever available, the confirmatory claim may be permanently out of
  reach, which is itself an important finding to report.

---

## Bottom line

The **framework is a success**; the **confirmatory semantic test is blocked**; the **theory is
untested, not disproven**. The strongest publishable stopping point today is: **Version 1 of a
pre-registered, freeze-gated evaluation framework (Track A), together with an honest, documented
account that the confirmatory semantic channel (Track B) is blocked by circularity and offline-
asset constraints.** Freeze it, publish Track A, report Track B as blocked, and do not run a
confirmatory experiment until a non-circular concept channel *and* an independent meaning source
exist.

> structure, not validated meaning.
