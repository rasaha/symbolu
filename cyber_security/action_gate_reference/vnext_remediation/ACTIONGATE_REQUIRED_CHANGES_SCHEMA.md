# ACTIONGATE_REQUIRED_CHANGES_SCHEMA — schema for remediation payloads (vNext)

Status: **DESIGN ONLY.** Schema proposal; not implemented. Grounded in the real effect
operators (`policy.py DEFAULT_RULES`), the gate mapping (`gate.evaluate`), and the error
codes (`errors.py`).

## 1. Where it lives in the response

The decision dict returned by `gate.evaluate` is unchanged in its existing keys
(`outcome`, `dispositive_rules`, `applied_constraints`, `action_hash`, `policy_hash`,
`state_trace`, `terminal`, `reason`, `hash_algorithm_id`). Remediation adds two **optional**
top-level keys, populated according to disclosure level:

```
{
  ...existing decision fields (unchanged)...,
  "remediation": {                      // optional; omitted entirely at disclosure NONE
    "disclosure": "STANDARD",           // FULL | STANDARD | MINIMAL | NONE
    "action_hash": "<same as decision.action_hash>",
    "required_changes": [ RequiredChange, ... ],       // dispositive tier (+ see below)
    "all_unmet_conditions": [ UnmetCondition, ... ]     // FULL only; else omitted
  }
}
```

`remediation` is **not** part of the hashed audit payload (`audit.build_audit_record`) and
**not** part of the `action_hash` projection (`projection.PROJECTION_MANIFEST`). It is a
re-derivable view; the audit record already commits every input needed to recompute it.

## 2. `RequiredChange` object

```
RequiredChange = {
  "condition_id":     string,   // "<rule_id>:<operator>" e.g. "R2:MUST_HAVE", or a
                                 // pre-check id "PRIV_MONO" | "TICKET_SOD" | "FRESHNESS"
  "operator":         string,   // effect op: DENY|FORBID|REQUIRE|MUST_HAVE|
                                 // REQUIRE_ATTESTATION|REQUIRE_SIMULATION|REQUIRE_APPROVER|
                                 // MAX_SCOPE|MAX_COST|MAX_BLAST_RADIUS|MAX_IRREVERSIBILITY
  "operation":        string,   // envelope.operation (one of the 10 OPERATIONS)
  "severity_tier":    string,   // the outcome this condition maps to (dominance signal)
  "remediation_class": string,  // see §4 enum
  "reason_code":      string,   // stable machine code, see §5
  "required": {                 // machine-readable target; shape depends on operator (§3)
     ...
  },
  "satisfies_alone":  boolean,  // false whenever a strictly-more-severe unmet condition
                                 // co-exists (I2). Never implies ALLOW on its own.
  "binding": {
     "action_hash":   string,   // the action this was evaluated against
     "policy_hash":   string,   // active policy
     "rebind_required": boolean // true whenever remediation_class implies action modification
  }
}
```

`UnmetCondition` (in `all_unmet_conditions[]`) has the same shape minus `remediation_class`
detail may be coarser at lower disclosure; at `FULL` it is identical to `RequiredChange`.

## 3. `required` payload by operator (grounded in `gate.evaluate`)

| operator | outcome tier it produces | `required` payload |
|---|---|---|
| `MUST_HAVE` (soft) | REQUEST_MORE_EVIDENCE | `{"kind": "<evidence kind>", "bound_to": "<action_hash>", "min_fidelity": null}` |
| `MUST_HAVE` (`hard: true`) | **DENY** | `{}` — `remediation_class = IMPOSSIBLE` (terminal precondition; e.g. DB_DELETE backup) |
| `REQUIRE_ATTESTATION` | REQUEST_MORE_EVIDENCE | `{"attestation_type": "<attn_type>", "must_be_unexpired": true}` |
| `REQUIRE_SIMULATION` | SIMULATE_AND_RETRY | `{"kind": "simulation", "min_fidelity": "HIGH\|MEDIUM\|LOW", "bound_to": "<action_hash>", "structured_only": true}` |
| `REQUIRE_APPROVER` (absent) | ESCALATE_TO_HUMAN | `{"approver_policy": "<policy>", "min_approvers": N, "sod": "approver != requester/agent", "binds": ["action_hash","policy_hash","nonce"]}` |
| `REQUIRE_APPROVER` (present-but-invalid) | **DENY** | `{}` — `remediation_class = TERMINAL`, `reason_code` from the specific approval error (§5) |
| `MAX_SCOPE`/`MAX_COST`/`MAX_BLAST_RADIUS` | ESCALATE_TO_HUMAN | `{"fact": "<fact>", "current": "<value>", "limit": "<threshold>", "options": ["ACTION_MODIFICATION: reduce below limit","HUMAN_ONLY: obtain approver"]}` |
| `MAX_IRREVERSIBILITY` | ESCALATE_TO_HUMAN | `{"current": "<reversibility>", "max_class": "<class>", "options": ["ACTION_MODIFICATION: choose reversible target","HUMAN_ONLY"]}` |
| `FORBID` (fact true) | **DENY** | `{"fact": "<fact>"}` — `remediation_class = TERMINAL` (the action is forbidden as posed) |
| `REQUIRE` (fact false) | **DENY** | `{"fact": "<fact>"}` — `TERMINAL`, unless the fact is an argument the caller can set truthfully (then `RETRYABLE_BY_ACTION_MODIFICATION`; see §6) |
| `PRIV_MONO` | **DENY** | `{}` — `IMPOSSIBLE` (privilege non-monotonic; a different credential is a different action) |
| `TICKET_SOD` | **DENY** | `{}` — `TERMINAL` (self-authored ticket; SoD) |
| `FRESHNESS` | REQUEST_MORE_EVIDENCE | `{"refresh": "state_freshness.as_of", "bound_seconds": <freshness_bound_seconds>}` |

The evidence `kind`, simulation `fidelity`, `approver_policy`, and `MAX_*` thresholds are
read verbatim from the matched effect in the signed policy — no inference.

## 4. `remediation_class` enum (mirror of the retry matrix)

```
TERMINAL                       // not remediable for this action; forbidden/SoD/invalid
IMPOSSIBLE                     // structurally impossible (hard destructive precondition,
                               //   privilege non-monotonicity) — never yields ALLOW
RETRYABLE_BY_EVIDENCE          // provide fresh evidence of a kind, bound to a (new) action_hash
RETRYABLE_BY_SIMULATION        // provide structured simulation evidence >= min_fidelity
RETRYABLE_BY_ACTION_MODIFICATION // a *different* action (smaller scope/cost, reversible target,
                               //   truthfully-set fact) would avoid this rule -> new action_hash
HUMAN_ONLY                     // requires an out-of-band human approver signature
```

`TERMINAL`/`IMPOSSIBLE` entries **must** carry no retry token and must not appear as a way to
turn this action's DENY into ALLOW (invariant I3).

## 5. `reason_code` — stable machine codes

Reuse the existing `errors.py` codes where an error already exists, and add remediation-only
codes for the "condition unmet but not an error" cases:

| situation | reason_code |
|---|---|
| approval present but action modified | `E_ACTION_HASH_MISMATCH` (existing) |
| approval bound to wrong policy | `E_POLICY_MISMATCH` (existing) |
| approval expired | `E_EXPIRED` (existing) |
| approval nonce replay | `E_NONCE_REPLAY` (existing) |
| approval scope too narrow | `E_SCOPE_VIOLATION` (existing) |
| approver == requester (SoD) | `E_SCOPE_VIOLATION` (existing) |
| stale state | `E_STALE_STATE` (existing) |
| evidence bound to another action | `E_EVIDENCE_BINDING` (existing) |
| missing required evidence (soft) | `R_MISSING_EVIDENCE` (new, remediation-only) |
| missing hard destructive precondition | `R_HARD_PRECONDITION` (new; terminal) |
| missing simulation / low fidelity | `R_MISSING_SIMULATION` (new) |
| missing attestation | `R_MISSING_ATTESTATION` (new) |
| absent approver | `R_MISSING_APPROVER` (new) |
| threshold exceeded (scope/cost/blast) | `R_THRESHOLD_EXCEEDED` (new) |
| irreversibility exceeded | `R_IRREVERSIBILITY_EXCEEDED` (new) |
| forbidden fact set | `R_FORBIDDEN_FACT` (terminal) |
| privilege non-monotonic | `R_PRIV_NON_MONOTONIC` (terminal) |
| self-authored ticket | `R_TICKET_SOD` (terminal) |

New `R_*` codes are additive and namespaced apart from the `E_*` error codes so no existing
consumer misreads them as hard errors.

## 6. Worked examples (real rules from `policy.py`)

**DEPLOY (R2), no signed artifact, no HIGH simulation → SIMULATE_AND_RETRY** (min-severity
of the two unmet: REQUEST_MORE_EVIDENCE(2) vs SIMULATE_AND_RETRY(3) → 2 is dispositive):

```
outcome: "REQUEST_MORE_EVIDENCE", dispositive_rules: ["R2"]
remediation.required_changes: [
  {condition_id:"R2:MUST_HAVE", operator:"MUST_HAVE", operation:"DEPLOY",
   severity_tier:"REQUEST_MORE_EVIDENCE", remediation_class:"RETRYABLE_BY_EVIDENCE",
   reason_code:"R_MISSING_EVIDENCE",
   required:{kind:"signed_artifact", bound_to:"<action_hash>", min_fidelity:null},
   satisfies_alone:false, binding:{action_hash:"…", policy_hash:"…", rebind_required:true}}
]
remediation.all_unmet_conditions (FULL only): [ …R2:MUST_HAVE…, 
  {condition_id:"R2:REQUIRE_SIMULATION", operator:"REQUIRE_SIMULATION",
   severity_tier:"SIMULATE_AND_RETRY", remediation_class:"RETRYABLE_BY_SIMULATION",
   reason_code:"R_MISSING_SIMULATION",
   required:{kind:"simulation", min_fidelity:"HIGH", structured_only:true, bound_to:"…"}} ]
```

Note `satisfies_alone:false` and the dominance visible via `severity_tier`: supplying the
artifact alone still leaves the SIMULATE requirement (had it been dispositive).

**DB_DELETE (R3), missing verified backup → DENY (hard, terminal):**

```
outcome: "DENY", dispositive_rules: ["R3"]
remediation.required_changes: [
  {condition_id:"R3:MUST_HAVE", operator:"MUST_HAVE", operation:"DB_DELETE",
   severity_tier:"DENY", remediation_class:"IMPOSSIBLE", reason_code:"R_HARD_PRECONDITION",
   required:{}, satisfies_alone:false,
   binding:{action_hash:"…", policy_hash:"…", rebind_required:false}}
]
```

No retry path is offered — the hard destructive precondition is terminal for this action
(invariant I3). A caller may of course construct a *different*, reversible action, but that
is a new action_hash and a fresh evaluation, not a "retry" of this DENY.

**DB_MUTATION (R7), affected_count 25000 > 10000 → ESCALATE_TO_HUMAN:**

```
outcome: "ESCALATE_TO_HUMAN", dispositive_rules:["R7"]
remediation.required_changes: [
  {condition_id:"R7:MAX_SCOPE", operator:"MAX_SCOPE", operation:"DB_MUTATION",
   severity_tier:"ESCALATE_TO_HUMAN", remediation_class:"RETRYABLE_BY_ACTION_MODIFICATION",
   reason_code:"R_THRESHOLD_EXCEEDED",
   required:{fact:"affected_count", current:"25000", limit:"10000",
             options:["ACTION_MODIFICATION: reduce affected_count <= 10000",
                      "HUMAN_ONLY: obtain approver"]},
   satisfies_alone:false, binding:{…, rebind_required:true}}
]
```

The decision stays ESCALATE (not softened to a self-service retry). The annotation merely
observes that a smaller-scope *new* action would not trip R7's MAX_SCOPE.

## 7. Invariants a conforming implementation must uphold

- Populating `remediation` must not read from or write to `D`'s inputs; it runs after `D`.
- For any DENY, every `required_changes` entry has `remediation_class ∈ {TERMINAL, IMPOSSIBLE}`
  and empty/absent retry targets.
- `satisfies_alone` is `true` only if the condition's tier equals the dispositive tier **and**
  no other unmet condition exists at any tier.
- `remediation` bytes are reproducible from `(audit record, signed policy)` — a conformance
  test can assert `recompute(remediation) == emitted(remediation)`.
