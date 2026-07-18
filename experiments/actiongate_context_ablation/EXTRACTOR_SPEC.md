# EXTRACTOR_SPEC

The extraction function `F: context -> canonical envelope`, in two modes. Both
feed the **real** `adapter.build_env` (the runtime `action_gateway.mapping`
builder) and the **real** `gate.evaluate`. Neither changes ActionGate semantics.

## Adapter (real path)

`adapter.py` locates the frozen reference harness (`action_gate_ref`) and the
runtime mapping layer (`action_gateway`) exactly as the production `_core`/`_ref`
shims do — no reimplementation of canonicalization, hashing, policy, tokens, or
the gate. It exposes:

- `build_env(spec, signed_policy)` → canonical envelope via the real builder
  (fixed clock `2026-07-12T14:00:00Z`, fixed valid UUIDv4 `action_id` so envelopes
  diff only on content).
- `evaluate(spec, signed_policy)` → `{envelope, decision, action_hash, ...}` where
  `decision` is the real six-outcome record from `gate.evaluate`.
- `default_signed_policy()` → the real signed frozen reference bundle (verified).

The gate is deliberately free of AI/BCVF/USE/SCC (its own docstring), so `D` is a
pure deterministic function of the envelope, policy, evidence, and approvals.

## STRUCTURED_ORACLE_EXTRACTOR

Merges each surviving unit's explicit `contrib` fragment into a `RequestSpec`
(args, target additions, evidence, approvals, reversibility, credential
permissions, state). **Zero NLP error** — it *is* ground truth for the fixtures.
Used to establish semantic causality on deterministic contexts.

## REALISTIC_EXTRACTOR (narrow, transparent reference)

Recovers a `contrib` fragment from each unit's natural-language `text` via a small
readable keyword/regex ruleset (`extractor.reference_fragment`). It is a *reference*
extractor, **not production quality**.

### Recognized phrasings (exhaustive)

- Evidence: "signed artifact"/"signed build"; "simulation"/"dry run"/"simulated"
  (fidelity from "high/full" vs "medium/partial"); "verified backup"/"restorable
  backup".
- Approvals: "dual control"/"two approvers" → dual; "approved by"/"single
  approver"/"manager approval" → single.
- Facts: "unbounded"/"no limit"/"without a where"; "bulk"; "public"+"sensitive";
  "0.0.0.0/0"/"open to the internet" (+"admin"); "widen"; "last/only replica";
  "self-grant"/"grant to itself"; "export" (+"approved sink/destination").
- Numeric: `N rows|records|objects|resources` → `affected_count`.

### KNOWN LIMITS (deliberate)

- Any paraphrase outside the list above is **silently dropped** (e.g. "cleared by
  infosec" ≠ approved sink; "point-in-time copy we restored" ≠ verified backup;
  "gave the go-ahead" ≠ approval). Tier 3 is written precisely to exercise these
  misses.
- No negation-scope analysis beyond the listed keywords; no coreference; no
  table/JSON structural parsing beyond regex.
- These misses are the intended signal: when the realistic extractor and the
  oracle disagree on whether a removal is critical, the ablation is labelled
  `EXTRACTOR_SENSITIVE` (attributed to F, not to semantics) and excluded from
  ground-truth critical sets.

### Why not a better extractor?

Building a production extractor *is the product*, and this experiment exists to
decide whether the product is worth building at all — before that cost. A
transparent reference extractor lets us measure the extractor-instability rate
`r_F` honestly rather than assume a perfect `F`.
