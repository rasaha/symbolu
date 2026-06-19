# Hallucinated Capability Observable (Phase 2 — deterministic)

**Status:** PROVISIONAL · advisory/confirm-only · shadow-recorded · inert by default. No ML,
no GPU, no hidden state. Third Phase 2 observable.

## Definition

Detect when an action **references, requests, or depends on a capability/tool that does not
exist or is unsupported** by the current registry/context — i.e. the model invented a tool or
claimed a capability the system cannot provide.

## Distinction from Permission Overclaim

| | exists? | actor permitted? | observable |
|---|---|---|---|
| **Permission Overclaim** | yes | **no** (lacks scope/authority/capability grant) | `permission_overclaim` |
| **Hallucinated Capability** | **no** (not registered / unsupported / impossible) | n/a | `hallucinated_capability` |

Overclaim asks "are you allowed to do this real thing?"; hallucination asks "does this thing
even exist here?". They never overlap: a name either resolves to a real capability (then
overclaim may apply) or it does not (then hallucination applies).

## Deterministic checks (no ML)

A `CapabilityContext` carries what the action **references** and what is **available**:

- `referenced_tools`, `referenced_capabilities` — names the action depends on.
- `available_tools`, `available_capabilities` — the registered/supported sets.
- `aliases` — known alias → canonical mapping (resolved before lookup).
- `impossible_capabilities` — names explicitly marked structurally impossible/unsupported.

Detection (pure set membership + alias resolution):

- `hallucinated_tool` — a referenced tool whose alias-resolved name is **not** in
  `available_tools`.
- `unsupported_capability` — a referenced capability whose resolved name is **not** in
  `available_capabilities`.
- `impossible_capability` — a referenced name resolving into `impossible_capabilities`
  (severe; an impossible claim, e.g. "read_other_tenant_secrets", "time_travel").

Verdict: `SAFE` when every reference resolves to something available; `UNSURE` for
hallucinated/unsupported references; `UNSAFE` for impossible claims. While PROVISIONAL all
escalations collapse to CONFIRM (kernel guarantee — a PROVISIONAL validator never blocks);
the `UNSAFE`/`UNSURE` split only matters after promotion to PROVEN. Identical inputs →
identical output; no thresholds, no scores.

## Taxonomy placement

`ObservableType.VALIDATOR`, `EvidenceStatus.PROVISIONAL` — an independent check that can
escalate to CONFIRM but never blocks until proven. Asymmetric: it only ever **raises** trust
(a hallucinated dependency is a reason to pause), never relaxes it.

## Inert by default (no production behaviour change)

Appended to the trust observation set **only** when an explicit `CapabilityContext` is
supplied (via `MCPToolCall.capability_context`) and it actually references something.
Production calls carry none → the observable is absent → the recorded/authoritative decision
is unchanged; existing parity / shadow-volume corpora are unaffected.

When a context is supplied (validation corpus, or a future caller that populates it from the
gateway registry), it participates in **shadow mode**, **parity reporting** (a
`hallucinated_capability` driver; stricter-only escalation classified `intended`), **audit
persistence** (`trust_shadow.drivers` + `trust_observations`), and **shadow_report
aggregation** (mismatch-by-driver). It can never produce `unsafe_relaxation` — it only raises.

## Promotion plan (PROVISIONAL → PROVEN)

Promotion would let an *impossible* (or any) hallucinated reference BLOCK rather than only
CONFIRM. It requires:

1. **Registry provenance.** `available_tools` / `available_capabilities` / `aliases` must come
   from the **authoritative** registry (not model-supplied), so "not available" is ground
   truth and cannot be gamed. This is the central gate for this observable.
2. **False-positive review.** Over a shadow window, every `hallucinated_capability` escalation
   spot-audited; no false-positive class traced to a stale/incomplete registry or a missing
   alias. Target false-positive rate agreed with the governance owner.
3. **Minimum shadow volume.** A program-wide minimum of governed calls carrying a capability
   context (calibrated; thin slices do not promote), with all violation kinds observed firing
   correctly on real traffic, not only the validation corpus.
4. **Safety invariants.** `shadow_report` shows **0 unsafe_relaxation, 0 unintended** with the
   observable active.
5. **Sign-offs.** Governance/safety (accepts hallucination as a blocking authority), audit/
   compliance (registry provenance + chain integrity), service/on-call — the same gate as the
   JEPA demotion.

Promotion is a one-line evidence change (`PROVISIONAL → PROVEN`) plus the impossible→BLOCK it
unlocks, itself parity-gated and differential-checked. **Not done here. No authority expansion.**
