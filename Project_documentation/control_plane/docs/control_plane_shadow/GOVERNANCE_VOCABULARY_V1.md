# Governance Vocabulary V1 (FROZEN)

*Phase 4. Frozen canonical vocabularies for the integrated system, fixed BEFORE any
outcome-bearing integration run. Source of truth: `control_plane_shadow/vocabulary.py`
(`VOCAB_VERSION = "gov_vocab_v1"`). Original component terms are preserved in provenance and
normalized only through the explicit tables below.*

## Canonical vocabularies

**Assertion dispositions** (what the system may state):
`ALLOW · QUALIFY · REJECT · ESCALATE · INDETERMINATE`

**Action dispositions** (what the system may do):
`ALLOW · DENY · APPROVE · CONSTRAIN · ESCALATE · INDETERMINATE`

**Execution eligibility** (what can run):
`ELIGIBLE · INELIGIBLE · CONDITIONALLY_ELIGIBLE · INDETERMINATE`

**Execution outcome** (what happened):
`SUCCESS · FAILURE · NOT_ATTEMPTED · UNKNOWN`

Assertion and action vocabularies are kept **separate** (a system may assert without acting,
and act without a new assertion). `QUALIFY` exists only for assertions; `APPROVE`/`CONSTRAIN`
only for actions.

## Forbidden collapses (task rule, asserted in code + tested)

The following normalizations are prohibited; `vocabulary.FORBIDDEN_COLLAPSES` encodes them and
a unit test proves no mapping performs them:

- `APPROVE` ↛ `ALLOW` (approval-required ≠ permitted)
- `QUALIFY` ↛ `CONSTRAIN` (a qualified assertion ≠ a constrained action)
- `REJECT` ↛ `DENY` (may-not-state ≠ may-not-do)
- `INDETERMINATE` ↛ `DENY` (unknown ≠ prohibited — fail-closed *handling* differs from *labeling*)
- `UNAVAILABLE` ↛ `PROHIBITED` (a missing component is not a denial verdict)

Fail-closed **handling** of INDETERMINATE (refuse to act) is preserved at the orchestrator
level; it is not achieved by *relabeling* INDETERMINATE as DENY, so the distinct cause stays
auditable.

## Real → canonical mappings (with provenance)

### ExecutionGate — exact 1:1, zero information loss
`execution_gate.states.EligibilityState` already equals the canonical execution-eligibility
vocabulary: `ELIGIBLE→ELIGIBLE`, `INELIGIBLE→INELIGIBLE`, `CONDITIONALLY_ELIGIBLE→
CONDITIONALLY_ELIGIBLE`, `INDETERMINATE→INDETERMINATE`.

### TAP-E4 `GovStatus` → AssertionDisposition — AUTHORED, lossy (semantic gap)
| Source `GovStatus` | Canonical | Rationale |
|---|---|---|
| `GOVERNING` | `ALLOW` | a governing authority supports the statement |
| `GOVERNING_WITH_EXCEPTION` | `QUALIFY` | governed but with an exception ⇒ qualified (not constrained) |
| `NO_GOVERNING_AUTHORITY` | `REJECT` | no basis to assert |
| `CONFLICTED` | `ESCALATE` | authority conflict ⇒ human (not auto-deny) |
| `INSUFFICIENT_BASIS` | `INDETERMINATE` | unknown (not reject) |
| `UNRESOLVED` | `INDETERMINATE` | unknown |

**Loss:** the 8-axis confidence vector, conflict/gap detail, and full provenance are NOT
represented by the disposition alone — they are carried in the contract payload but do not
alter the disposition. **Semantic gap:** E4 resolves *which authority governs a situation*, not
*whether a model's claim may be asserted*; this mapping is an approximation (see
`SEMANTIC_MAPPING_SPEC.md`).

### ActionGate six outcomes → ActionDisposition — low loss
| Source outcome | Canonical | Rationale |
|---|---|---|
| `ALLOW` | `ALLOW` | permitted |
| `ALLOW_WITH_CONSTRAINTS` | `CONSTRAIN` | permitted under constraints (not collapsed to ALLOW) |
| `ESCALATE_TO_HUMAN` | `APPROVE` | human approval required |
| `REQUEST_MORE_EVIDENCE` | `INDETERMINATE` | insufficient evidence (not DENY) |
| `SIMULATE_AND_RETRY` | `INDETERMINATE` | must simulate first (not DENY) |
| `DENY` | `DENY` | prohibited; a hard `MUST_HAVE`-unmet on an irreversible class is the hard-safety-block |

**Loss:** `applied_constraints`, `dispositive_rules`, `action_hash`, `policy_hash` are preserved
in the payload (not in the disposition). Canonical `ESCALATE` is **reserved** for
orchestrator-level escalation and is not emitted by this engine (which uses `APPROVE` for its
human path) — recorded so the absence is not mistaken for a mapping bug.

## Change control

`gov_vocab_v1` is frozen. Any change is a new version (`gov_vocab_v2`), never an in-place edit,
and requires re-running the adapter-fidelity and end-to-end evaluations under the new version.
