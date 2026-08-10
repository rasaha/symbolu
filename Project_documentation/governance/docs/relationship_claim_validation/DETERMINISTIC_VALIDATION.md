# Deterministic Validation (v0.1)

Source: `deterministic.py`. Pure functions of the claim + document set; run
**before** any judge. Hard failures are resolved here and never reach the judges.

> Scope: synthetic, self-contained. See `CLAIM_VALIDATION_PREREGISTRATION.md`.

---

## 1. Checks (in order)

| Check | Fails when | Terminal status |
|---|---|---|
| legality | relationship_type ∉ legal set | UNSUPPORTED (remove) |
| schema | missing id / missing entity / self-loop | UNSUPPORTED (remove) |
| direction well-formed | source == target | UNSUPPORTED (remove) |
| duplicate | (source,type,target) already retained upstream | UNSUPPORTED (remove) |
| document existence | a cited document id is absent | INSUFFICIENT_EVIDENCE (abstain) |
| citation validity | a cited span id is absent from cited docs | INSUFFICIENT_EVIDENCE (abstain) |
| has citation | claim cites no evidence spans | INSUFFICIENT_EVIDENCE (abstain) |

A claim that passes all checks proceeds to the judges.

## 2. Rationale for the two terminal buckets

- **Remove (UNSUPPORTED):** the claim is malformed or structurally invalid — there
  is nothing to ground. Removing it is safe.
- **Abstain (INSUFFICIENT_EVIDENCE):** the claim might be true, but its cited
  evidence cannot be located. Abstention (not removal) is the conservative action.

## 3. Measured effect on the corpus (from the run)

Deterministic checks resolved **6** claims before the judges in the full system
(V4): 3 removals (illegal type `U5`, duplicate `U4`, self-loop `U6`) and 3
abstentions (missing doc `I3`, missing span `I4`, no-citation `I5`). This is the
"deterministic validation removes relationships before LLM adjudication" behavior
the brief asks about — here, before **judge** adjudication.
