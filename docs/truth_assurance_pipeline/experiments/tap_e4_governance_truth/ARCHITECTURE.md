# TAP-E4 — Architecture

## 1. Position in the pipeline

```
TAP-E1 Intent  ─▶  TAP-E2 Retrieval  ─▶  TAP-E3 Relationship  ─▶  TAP-E4 Governance  ─▶  (TAP-E5 Evidence Packet ─▶ Claim Truth ─▶ Response Truth)
IntentRecord       RetrievalRecord        RelationshipRecord        GovernanceRecord
```

TAP-E4 consumes the three upstream records **through their frozen public interfaces only**
and emits exactly one `GovernanceRecord`. It imports upstream schemas; it never mutates
them and adds no field to them.

## 2. Boundary (what this layer is NOT)

| Concern | Owner | TAP-E4 stance |
|---|---|---|
| What did the user ask? | TAP-E1 | consumes `request_id` only |
| Which evidence is trustworthy/retrieved? | TAP-E2 | consumes tiers/provenance; never retrieves |
| What relationship does the evidence assert? | TAP-E3 | consumes assertions; never re-extracts |
| **Which documented authority governs here?** | **TAP-E4** | **this layer** |
| Is the obligation factually correct? | Claim Truth | out of scope |
| Should the action be executed? | Enforcement | out of scope |
| What do we tell the user? | Response Truth | out of scope |

Governance Truth answers *"which documented authority controls, and why"* — never *"is it
right"* or *"do it"*.

## 3. The Situation

Governance is situation-relative, so the layer takes an explicit `Situation`
(`jurisdiction`, `user_role`, `environment`, `date_year`, `contract`, `product`,
`business_unit`) supplied as application metadata. The Situation is data, not a document:
it is never treated as an authority and never grounds a decision by itself. A missing
Situation field lowers the relevant confidence axis rather than inventing a match.

## 4. Thirteen-stage deterministic pipeline

Every stage is a **pure function** of `(intent, retrieval, relationship, situation)`; the
engine threads an append-only `processing_trace`. No randomness, no wall-clock, no network.

1. **input validation** — schema versions, referential consistency (the relationship record
   must descend from this retrieval), provenance attached. Malformed input is refused, never
   repaired (`validator.py`).
2. **authority identification** — extract governance-predicate assertions (`GOVERNS`,
   `APPLIES_TO`, `REQUIRES`, `PROHIBITS`, `OVERRIDES`, `SUBORDINATE_TO`, `OBLIGATED_TO`,
   `PROHIBITED_FROM`) as candidates; collect `SUPERSEDES` and `EXEMPTS` assertions.
3. **authority normalization** — each candidate's tier from its TAP-E2 evidence unit
   (`tier_from_evidence`), refined by an explicit tier if the statement carries one.
4. **jurisdiction resolution** — `jurisdiction.py`; a global/empty authority applies
   broadly (lower confidence); an unknown situation jurisdiction lowers confidence.
5. **scope matching** — `scope.py`; people/roles/environments/products; broad scopes match
   with reduced specificity.
6. **temporal applicability** — `temporal.py`; explicit date comparison → EFFECTIVE /
   EXPIRED / FUTURE / HISTORICAL / SUPERSEDED / UNKNOWN.
7. **version resolution** — supersession removes superseded candidates; higher version
   wins among equals.
8. **exception evaluation** — `exceptions.py`; an `EXEMPTS` whose exempted role matches the
   situation removes the general obligation (exceptions are never flattened).
9. **precedence resolution** — `precedence.py`; the documented ordering key over survivors.
10. **conflict detection** — `conflict_resolution.py`; ≥2 survivors sharing the top key with
    incompatible obligations ⇒ a surfaced `GovernanceConflict` (no silent winner).
11. **confidence** — `confidence.py`; an 8-axis vector whose band is floored by its minimum
    component (a weak dimension can never be averaged away).
12. **governance gaps** — no governing policy, conflicting authorities, and **preserved
    upstream relationship gaps** are reported, not filled.
13. **GovernanceRecord generation** — assemble the decision, conflicts, gaps, confidence,
    and trace into one serializable record.

## 5. Determinism

Every sort carries a stable final tiebreak (authority name); tie *detection* deliberately
ignores that final tiebreak so a genuine tie is surfaced as a conflict rather than hidden by
alphabetical luck. There is no reliance on `set`/`dict` iteration order for any decision.
Verified identical across `PYTHONHASHSEED ∈ {0,1,7,42,123}`.

## 6. Frozen model, versioned and hashed

The authority hierarchy (`tap-e4-authority/1.0.0`) and precedence rules
(`tap-e4-precedence/1.0.0`) are documented, frozen models — **this study's ordering, not
law**. All resolver modules, the metrics, the gates, and the baseline definitions are folded
into a single `frozen_components_hash` recorded in the experiment lock, so any change to the
mechanism changes the hash.

## 7. Module map

| Module | Responsibility |
|---|---|
| `authority.py` | tier enum, ranks, immutable/non-selectable sets, `tier_from_evidence` |
| `jurisdiction.py` `scope.py` `temporal.py` `exceptions.py` | dimension resolvers |
| `precedence.py` | ordering key, selection, top-key tie detection |
| `conflict_resolution.py` | surface unresolved ties with incompatible obligations |
| `confidence.py` | 8-axis governance confidence (min-floored band) |
| `applicability.py` | `Situation`, `Candidate`, `GovernanceConfig`, A–F baselines, engine |
| `schema.py` | `GovernanceRecord` and all sub-structures |
| `validator.py` | input coherence checks (never repairs) |
| `metrics.py` | per-dimension metrics + independent critical failures |
| `harness.py` | E1→E2→E3→E4 driver, dev-only selection, gates, verdict, frozen hash |
| `loader.py` | gold-free public loader |
