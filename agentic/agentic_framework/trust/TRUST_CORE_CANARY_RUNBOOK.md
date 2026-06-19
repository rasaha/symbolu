# trust_core Canary Rollout Runbook

**Scope:** how to enable `TRUST_CORE` + `REVIEWED` safely in a canary, monitor it, and roll
back. Documentation only — no code, no Phase 2 observables, no ML, no CG, no VC brief.

**What the canary does (one sentence):** for the small slice of traffic JEPA flags, a
**JEPA-sole BLOCK becomes a human CONFIRM** (deny → ESCALATE, approve → ALLOWED); **no other
decision path changes** and **no silent ALLOW exists**. Default everywhere else stays
`LEGACY`/`PARITY`.

---

## 0. Signal shift you must understand first (SHADOW vs TRUST_CORE)

The same JEPA demotion reads **differently** before and during the canary, because under
TRUST_CORE the legacy runtime decision *is* the relaxed one:

| Window | What a JEPA-sole demotion looks like in the audit |
|---|---|
| **Pre-canary (SHADOW + REVIEWED)** | `trust_shadow`: `legacy=block, trust=confirm` → **`intended`** mismatch. This is the count you review in the preconditions. |
| **During canary (TRUST_CORE + REVIEWED)** | legacy now CONFIRMs, so `legacy=confirm, trust=confirm` → **`match`**. The demotion no longer shows as a mismatch. Monitor it instead via the **decision outcome** (CONFIRM/ESCALATE) on JEPA-driven calls and the **approval/denial rate**. |

So: `intended` is the *pre-flip* gate; once flipped, `intended` for these calls goes to ~0
and the live signal moves to "confirmation volume + approve/deny rate." `unsafe_relaxation`
and `unintended` must remain **0 in both windows**.

---

## 1. Preconditions (all must hold before enabling)

Run against the **production / live SHADOW store** (gateway already in `trust_mode="shadow"`,
`trust_authority_policy="reviewed"` so it records the flip candidate):

```bash
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_report \
    --store /var/data/governance_audit.db --entropy --fail-on-unintended
```

- [ ] **Report clean / exit 0** over a representative window (real risk levels, tools, tenants).
- [ ] **`unintended == 0`** (mapping faithful on real traffic).
- [ ] **`unsafe_relaxation == 0`** (no BLOCK/CONFIRM → ALLOW).
- [ ] **`intended` are JEPA-only and reviewed** — every `intended` row's `drivers ⊆ {jepa,
      execution_permission}` and accepted per `AUTHORITY_REVIEW.md`.
- [ ] **Hash chain valid** — `GovernanceAuditStore.verify_chain().valid is True`.
- [ ] **Sign-offs complete** — governance/safety, audit/compliance, service/on-call, product
      (`TRUST_CORE_FLIP_READINESS.md` §3), recorded against this window.
- [ ] **Confirmation flow capacity confirmed** — on-call accepts the projected extra CONFIRMs.

Do not proceed unless **every** box is checked.

---

## 2. Enablement

The flip is **per-`SafeMCPGateway` instance** via supported constructor controls:

```python
SafeMCPGateway(
    mcp_client=...,
    # ... existing wiring (domain_registry, shadow_registry, audit_store, etc.) unchanged ...
    trust_mode="trust_core",
    trust_authority_policy="reviewed",
)
```

Everything else (forbidden set, domain registry, shadow registry, escalation handler, audit
store) stays exactly as in the control gateway.

**Canary scoping — start smallest, ramp in stages:**

1. **Stage 0 — internal/low-risk tenant or a low-blast-radius tool group.** Route only that
   slice to a canary gateway built with the config above; all other traffic stays on the
   control gateway (`trust_mode="shadow"`).
2. **Stage 1 — small percentage (e.g. 1–5%).** Run control (`shadow`) and canary
   (`trust_core`+`reviewed`) side by side; route a fixed, sticky percentage to canary.
3. **Stage 2 — ramp (10% → 25% → 50%)** only while §5 stays green and §7 stays clear.

Keep the **control cohort on SHADOW+REVIEWED** throughout so you always have an apples-to-apples
"what legacy would have done" baseline in the same store.

---

## 3. What changes

- **JEPA-sole BLOCK → human CONFIRM**, routed through the existing async confirmation flow:
  - human **denies / times out** → `ESCALATE` (not executed),
  - human **approves** → `ALLOWED` with `human_confirmed=True` (audits as CONFIRM = `match`).
- Net effect: fewer hard blocks on JEPA-flagged calls; those calls now reach a human instead.

That is the **entire** behavioural delta.

---

## 4. What must NOT change (and how to verify)

| Invariant | Verify in the canary store |
|---|---|
| Forbidden-capability veto terminal | a forbidden-capability call → `decision_outcome=blocked` (driver `forbidden_capability`); never CONFIRM/ALLOW |
| Domain policy authoritative | a domain-BLOCKED tool → `blocked` (driver `domain`), regardless of canary |
| Shadow deterministic block | an unsanctioned/quarantined asset → `blocked`/`escalate` (driver `shadow`) |
| Approval flow | `requires_confirmation` tools still CONFIRM as before |
| Audit persistence | every canary call writes `trust_shadow`; `verify_chain().valid` stays True |
| No silent ALLOW | every `allowed` row on a JEPA-relaxed call has `human_confirmed=True`; there is **no** `allowed` with `human_confirmed=False` arising from a JEPA-sole relax |

Spot-check these on day 1 of the canary and after each ramp.

---

## 5. Monitoring

Primary tool is `shadow_report` over the **canary** slice of the live store (plus the control
slice for baseline). Re-run on a schedule and after each ramp.

| Metric | Source | Watch for |
|---|---|---|
| **Confirmation volume** | count of JEPA-driven CONFIRMs (events with `trust_shadow.drivers ⊇ {jepa}` and outcome CONFIRM/ESCALATE/approved-ALLOWED) | spikes beyond confirm-flow capacity |
| **Approve / deny rate** | among those: `allowed`+`human_confirmed=True` (approve) vs `escalate` (deny/timeout) | the **core learning signal** (see §8) |
| **trust_shadow mismatch** | `shadow_report` `mismatch_class` counts | any drift from expected |
| **unsafe_relaxation** | `shadow_report` count | **must stay 0** (hard stop) |
| **unintended** | `shadow_report` count (`--fail-on-unintended`) | **must stay 0** |
| **Over-block reduction** | JEPA-sole `blocked` count in the **control (SHADOW)** slice vs JEPA-driven CONFIRM count in canary | the intended benefit; quantify |
| **Human-confirm latency** | escalation handler timing / `execution_time_ms` on confirmed calls | latency SLO breach |
| **Error / timeout rate** | `decision_outcome ∈ {error, timeout}` rate, canary vs control | any relative increase |

Baseline every metric against the control (SHADOW) cohort so canary deltas are attributable.

---

## 6. Rollback

Rollback is the **same supported control**, instant, no data migration, no schema change:

- **To SHADOW:** rebuild/reconfigure the canary gateway with `trust_mode="shadow"` (keeps
  recording `trust_shadow`; legacy acts; evidence collection continues).
- **To LEGACY:** `trust_mode="legacy"` (full stop; trust core not computed).
- **Policy to PARITY:** `trust_authority_policy="parity"` — disables the relax even if
  `trust_mode` stays `trust_core` (a second independent off-switch).

**Verify rollback:**
- A known JEPA-sole scenario now returns `blocked` again (the relax is off).
- No new `allowed`+`human_confirmed=True` rows attributable to a JEPA relax appear after the
  switch.
- `verify_chain().valid is True` (chain continuous across the switch).
- Route 100% back to the control gateway if in doubt.

Default production config is already `LEGACY`/`PARITY`, so **reverting the canary cohort to the
control path is sufficient** — no global change required.

---

## 7. Stop conditions (halt the canary, roll back to SHADOW immediately)

**Automatic (any one trips rollback):**
- `unsafe_relaxation > 0` — a BLOCK/CONFIRM became ALLOW. **Hard stop, investigate before any
  re-enable.**
- `unintended > 0` — a mapping gap on real traffic.
- Audit hash-chain verification fails.
- Human-confirm latency exceeds its SLO, or a denial/timeout **spike** on canary vs control.
- Error/timeout rate rises materially on canary vs control.

**Manual:**
- Any operator/on-call concern, capacity pressure on the confirm flow, or an unexplained shift
  in approve/deny rate. Bias to rollback; the canary is cheap to re-arm.

On any stop: switch canary cohort to `shadow`, confirm §6 verification, then triage from the
persisted `trust_shadow` + driver trace before re-enabling.

---

## 8. Post-canary decision

Decide from the **approve/deny rate** on JEPA-relaxed calls plus the §5 metrics:

| Observation | Decision |
|---|---|
| Clean (0 unsafe/0 unintended), latency OK, humans **approve most** JEPA-sole blocks | JEPA was **over-blocking** → **expand** the canary; consider, as a *separate* reviewed step, demoting JEPA further toward advisory/log-only (gated, differential-checked — not in this runbook). |
| Clean, but humans **deny most** JEPA-sole blocks | JEPA was **catching real risk** → **keep narrow** or **re-promote JEPA** toward blocking; do **not** demote further. The human-in-the-loop is doing useful work. |
| Mixed / inconclusive | **Keep canary** at current size; gather more volume before deciding. |
| Any stop condition or operator concern | **Rollback** to SHADOW; re-triage. |

Whatever the choice: it is **reviewed and recorded**, the default stays opt-in, and any further
JEPA authority change (demote-further or re-promote) is its own parity-gated, differential-checked
change — **out of scope for this canary**. No Phase 2 observables, ML, CG, or VC work is implied
by this rollout.
