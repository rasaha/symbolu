# Composite-Threat Detection — Advisory Assembly-of-Capability Layer

**Status:** design + reference implementation for an **advisory** evidence
producer that plugs into the deterministic Action Gate
([`ACTION_GATE_SPECIFICATION.md`](ACTION_GATE_SPECIFICATION.md)). It adds a
*second axis* of scrutiny — across a **sequence** of actions — without touching
the per-action deterministic decision.

Conformance keywords **MUST / MUST NOT / SHOULD / MAY** are used in the RFC-2119
sense. The reference implementation lives in
[`composite_threat_detector/`](composite_threat_detector/).

---

## 1. Problem: individually-admissible, jointly-dangerous

The Action Gate decides **one action at a time**. Given the same envelope,
policy, and evidence it always returns the same one of six outcomes. That is its
strength and, for a patient adversary, its gap: a forbidden *composite* can be
decomposed into steps that each clear the per-action gate.

> A machinist who wants a firearm does not buy "a gun". They acquire a steel
> rod, a piston, and a trigger mechanism — **separately**. Each purchase is
> lawful and unremarkable. The weapon exists only in the **assembly**.

The digital analogue, within one agent session (`correlation_id`):

| Step | Action (each returns ALLOW / ALLOW_WITH_CONSTRAINTS on its own) | Fragment contributed |
|---|---|---|
| 1 | `SECRET_READ` — one approved credential | credential material |
| 2 | `DB_MUTATION` — one bounded, simulated query | reach into stored data |
| 3 | `MONITORING_DISABLE` — one noisy alert silenced | observability gap |
| 4 | `NET_EXPOSE` — one narrow `/32` egress on :443 | outbound path |

No single action is deniable. Together they are a **data-exfiltration
capability**. The composite-threat detector is the layer that **reconstructs
that story from the fragments and asks a human to look — ideally before the last
part is fitted.**

The Action Gate already anticipates this: the canonical envelope reserves
`correlation_id` and `sequence_id` "for structuring detection"
([spec §2](ACTION_GATE_SPECIFICATION.md), fields 23–24). This layer is that
detector.

---

## 2. Non-negotiable: advisory, escalate-only

This detector is **behavioral evidence** in the sense of
[Action Gate §3](ACTION_GATE_SPECIFICATION.md): *ADVISORY, OPTIONAL*. The
**non-compensatory composition invariant** governs it:

- It **MUST NOT** admit an action, satisfy a `MUST_HAVE`, clear a `FORBID`,
  approve, or lower any required assurance.
- It **MAY** only move a decision toward **more** assurance — i.e. recommend
  `ESCALATE_TO_HUMAN`.
- The gate **MUST** remain fully functional and safe with this layer **removed**
  (the standing conformance test of [§12](ACTION_GATE_SPECIFICATION.md)).

The reference enforces this structurally: the only signals a finding can carry
are `OBSERVE` and `ESCALATE` (`signals.py`); there is deliberately no `ALLOW` or
`DENY` in the output alphabet, and `to_advisory_evidence` stamps every record
`authority=ADVISORY`, `effect=ESCALATE`.

---

## 3. Model

The engine is **deterministic** and **domain-agnostic**. All domain knowledge is
data, carried in an **Ontology**:

- **Fragment** — a reusable capability "part" that is benign in isolation
  (credential material, egress path, a firearm barrel).
- **Recipe** — a named composite capability (the "crime story"): the set of
  fragments whose assembly constitutes it. `required` fragments are load-bearing;
  `optional` fragments corroborate/aggravate.
- **extract(event) → fragments** — a pure function mapping one event to the
  fragment(s) it contributes. It reads only structured event fields — never
  wall-clock or randomness — so replay is exact.

Two ontologies ship: `ctd.digital.actiongate` (operates on Action-Gate
envelopes) and `ctd.physical.firearm` (the prompt's literal illustration, made
runnable — proving the engine is not hard-wired to any one domain).

### 3.1 Completeness and the signal ladder

For a correlation and a recipe:

```
completeness = |present ∩ required| / |required|          # monotone, order-independent
signal       = ESCALATE if completeness ≥ escalate_at (default 1.0)
               OBSERVE  if completeness ≥ observe_at  (default 0.5)
               NONE     otherwise
```

`completeness` is **never** treated as proof. It only chooses between *observe*
(a watch signal — parts are accumulating) and *escalate* (assembly complete).
Both are advisory. A partial finding names the **missing** fragment, which is the
operationally useful part: it says which next action would complete the weapon.

### 3.2 Windowing (structuring / low-and-slow)

A structuring adversary spreads the steps out to slip under any per-action
threshold. `window_actions` bounds how many recent steps per correlation are
retained, so "assembly" means "within a bounded span", not "ever". A barrel
acquired 10,000 innocuous actions before the trigger falls out of the window.

### 3.3 Determinism

Same event stream ⇒ same findings ⇒ same `finding_id` (a domain-separated
SHA-256 over the canonical finding body). Arrival order within a correlation is a
monotone counter (or the trailing integer of the spec's `correlation_id:NNNN`
`sequence_id`); matching ties break on sorted ids. There is no clock and no
randomness in the engine — timestamps enter only at the evidence-adapter
boundary, supplied by the caller.

### 3.4 Edge-triggered emission

`observe()` returns only findings whose signal **rose** on the current event, so
a caller is not spammed with an unchanged standing finding. `standing_findings()`
gives the level-triggered current state on demand.

---

## 4. Integration with the Action Gate

The detector sits **beside** the gate, not inside its decision path:

```
              ┌───────────────────────── per action ─────────────────────────┐
   action ───►│  Action Gate (deterministic)  ──►  ALLOW / DENY / ESCALATE …  │──► commit
              └───────────────┬──────────────────────────────────────────────┘
                              │ (envelope + action_hash, for every admitted action)
                              ▼
              ┌──────────────────────────── per correlation ─────────────────┐
              │  Composite-Threat Monitor  ──►  advisory finding (OBSERVE /   │
              │  (accumulates fragments,        ESCALATE) bound to action_hash│
              │   matches recipes)              via to_advisory_evidence()    │
              └───────────────┬──────────────────────────────────────────────┘
                              ▼   the gate MAY consume this on the *next* action
                       ESCALATE_TO_HUMAN   (never ALLOW; never satisfies a hard rule)
```

Because the finding is emitted as classed advisory evidence bound to an
`action_hash`, a gate that consumes it can only raise the next related action to
`ESCALATE_TO_HUMAN`. Removing the detector entirely changes no per-action
decision — exactly the conformance property [§12](ACTION_GATE_SPECIFICATION.md)
requires of every optional evidence plugin.

---

## 5. Can / cannot claim

**Can (by construction + tests in `tests/test_monitor.py`):**
- deterministic reconstruction (same stream → identical findings + digests);
- advisory-only output (no ALLOW/DENY in the alphabet; escalate is the ceiling);
- correlation isolation (fragments never cross `correlation_id`);
- windowed assembly (bounded-span, not lifetime, matching);
- the gate is unaffected when the layer is removed.

**Cannot (explicitly out of reach):**
- intent (it detects **capability assembly**, not motive — hence *advisory*, and
  hence a human decides);
- completeness of the recipe library (it flags the composites it knows; it is not
  a proof that no other composite exists);
- world-truth of the fragments (it trusts the same structured action facts the
  gate does; garbage facts in, garbage fragments out).

The recipe library is intentionally small and conservative. Its purpose is to
make the **sequence** visible and route it to a human — not to adjudicate.

---

## 6. Reference implementation

`composite_threat_detector/` — Python 3.11+, standard library only.

```bash
cd cyber_security/composite_threat_detector
python3 -m pytest -q                                  # 14 tests
python3 -m composite_threat_detector.cli demo firearm         # the prompt, runnable
python3 -m composite_threat_detector.cli demo exfiltration    # digital analogue
python3 -m composite_threat_detector.cli ontologies           # list recipes
python3 -m composite_threat_detector.cli run events.jsonl --window 200
```

Exit code is non-zero when any `ESCALATE` finding is produced, so the CLI drops
into pipelines and CI gates.
