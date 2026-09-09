# Client demo — the three governance surfaces

Thirteen minutes across three URLs. The claim being demonstrated is narrow and should stay
narrow: **this deployment decides, records and refuses; it does not execute.** Everything
below is reachable on the live deployment today; nothing needs seeding.

Deployment addresses, pass conditions and every `[V]`/`[I]`/`[G]` label are in
`RAILWAY_REFERENCE_DEPLOYMENT.md`. This document covers only what to show and what to say.

## Order, and why it is not the obvious one

Lead with the **Console**, not the Authority Plane. The Console runs a governed loop end to
end and refuses two of three scenarios for *different reasons* — the most persuasive thing
in the deployment. The Authority Plane, by contrast, reads an empty directory: it
demonstrates a boundary and an honest identity posture, but has no records to show, so it
closes well and opens badly.

| | Surface | Minutes | What it actually proves |
|---|---|---|---|
| 1 | Console | 5 | The loop runs, and two independent gates each refuse alone |
| 2 | Studio | 4 | Planning refuses too — and the client's own workflow can go in |
| 3 | Authority Plane | 4 | The read-only boundary, and identity stated honestly |

Open only the three client-facing URLs. Do not open Railway, and never show or name the
worker's internal address — the whole point of the plane is that the worker is unreachable
from a browser.

## 1 — Console (5 min)

Run all three scenarios, in this order. The ids are typed into the Governed Loop box.

| Scenario id | Outcome | The line to say |
|---|---|---|
| `k8s_rollout_restart_clean` | ALLOW | "Governance is not a refusal machine. A clean action clears." |
| `k8s_delete_during_freeze` | **HOLD** | "Policy said yes. Operational clearance said no." |
| `k8s_unsupported_claim` | **BLOCK** | "Policy said yes. The evidence gate said the claim isn't supported." |

The point lands on the second and third, and only if you show it: in both, **ActionGate
returns AUTHORIZED with `reasons: ['policy_allow']`** and the action is still stopped — by
a different stage answering a different question. Most governance tooling collapses those
into one approval step.

Say once, and do not repeat it: every disposition reads *OBSERVED (shadow) — nothing
changed*, and each carries a correlation id and a clearance id.

The **Audit** tab shows the decision trail. State its ceiling before anyone assumes
otherwise: it is one process's view of its own runs and is lost on restart (CP-4). It is a
demonstration of the record's shape, not a durable record.

Expect a `CONSOLE_ROUTE_WITHHELD` panel on the Governed Loop screen. Do not apologise for
it — it names two routes the packaged service deliberately does not serve (CP-3), and the
console shows a typed gap rather than an empty list.

## 2 — Governance Studio (4 min)

Four scenarios load. Open **Cybersecurity Incident Response (No Feasible Team)** and let
the expected state do the work: `NO_FEASIBLE_TEAM`, because only one approved provider
holds clearance level 4.

> "The planner's correct answer here is that it cannot staff this. A planner that always
> produces a team is not planning."

Then open the recommended demo, **Procurement Sourcing Workforce**, to show a clean plan.

Leave the synthetic-data banner visible and read it aloud once. If asked what the product
does: it plans and records, and declares that it does not execute or grant.

### Close the Studio segment with their workflow

**Bring Your Workflow**, top right of the header, route `/bring-your-workflow`. This is the
strongest answer to "but our workflows aren't your four scenarios", and it is live today —
no configuration, no seeding `[V]`.

If the client brings a `workflow_ir` JSON document, paste it or pick the file. If they
bring nothing, press **Load the guided example** — the procurement compiled workflow,
bundled with the screen.

Then walk one line of the *what the document declares* table, because it is doing the
work: declared version, node and edge counts, node kinds, declared dispositions, human
review and human authority requirements, referenced capabilities. Press **Validate**, then
**Adapt**, and if it is a technical audience **Compare adaptations** to show the same
workflow under `workflow_ir.v1` and `.v2`.

> "This reads a workflow you already have and tells you what it declares, whether it
> validates, and what governance it would need. It does not execute it, publish it or
> store it — the screen says so, and there is no server write behind it to do otherwise."

**Two things to be straight about, unprompted.** The document must already be Ugence
Workflow IR: there is no importer from LangChain, Langflow, CrewAI or similar, and
`/version` reports `langflow_import_implemented: false` `[V]`. And a submitted workflow does
not become a fifth scenario card — the catalog is four fixed ids `[V]`. Getting a client's
workflow into that form is scoping work, not a button.

## 3 — Authority Plane (4 min)

Start at the header: `AP-5 READS_FIRST`, `AP-3 IDP_VALIDATED_FIRST`, and the footer's
`REFERENCE_GRADE_SHADOW_ONLY`. The surface states its own assurance ceiling before showing
anything.

**The strongest artifact on this surface is the 405.** Have it ready in a browser console
on the plane's own origin:

```js
fetch('/api/authority/grants', {method:'POST'}).then(r => console.log(r.status))
```

> "There is no code path from this surface to a write. It is not switched off — the proxy
> forwards GET only, to four approved read paths. The four write operations are named and
> refused."

Then **Grants**, any typed token, and read the banner rather than the result:
`read_authenticated: false`, `PRESENTED_UNPROVEN`, `IN_PROCESS_ISSUER_ONLY`.

> "This distinguishes a presented identity from an enterprise-verified one. No identity
> provider is connected, and rather than presenting the read as trusted, it says so on
> every answer."

**Do not frame the empty result as a feature.** An empty directory returning zero is not
evidence of much, and a technical client will see that. What the zero result carries — the
identity envelope on every successful read — is the point; the count is not.

**Holders** answers the reverse question (who holds `approver` in a scope) and behaves the
same way. **Committee** and **Grant events** return typed 404s on an empty directory. Show
one only if refusal typing is the topic, and say plainly that it is empty:

> "No committee is loaded, so it returns an explicit typed refusal rather than a blank
> screen. Loading real organizational authority records is client-specific work that
> follows identity validation."

## Close, and the boundary to state

> "You have seen a governance boundary running in shadow mode: a loop that refuses on two
> independent grounds, a planner that declines to staff an infeasible team, a screen that
> reads a workflow you already have without running it, and an administrative surface that
> cannot write. What it does not yet have is your identity
> provider. Until that is validated end to end, no write or execution capability is served
> — and that is a property of the build, not a setting."

## Answer these honestly if asked

| Question | Answer |
|---|---|
| Is this running on real infrastructure? | Yes — a live cloud deployment, with the runtime worker private and reachable only by the plane. |
| Is the data real? | No. Synthetic throughout, and every screen says so. |
| Can it act on our systems? | No. No execution, no grants, no authorization on any surface here. |
| Is the audit trail durable? | No. In-memory, lost on restart. The shape is real; the durability is not. |
| Is identity verified? | No. Presented and unproven. That is why it says so on every read. |
| What would a pilot need? | The enterprise issuer validated end to end, then real authority records loaded. Writes come after that, not before. |
| Can it take our workflows? | Yes, on Bring Your Workflow — once expressed as Ugence Workflow IR. There is no converter from agent-framework code, and that conversion is scoping work. |

## Do not claim

Production readiness, pilot validation, enterprise-grade assurance, a certified image, or
that any identity here is verified. `/version` on the Studio API reports the maturity flags
directly, and an interested client can read them — including `pilot_validated: false` and
`production_certified: false`. It is a better outcome for them to hear it from you first.
