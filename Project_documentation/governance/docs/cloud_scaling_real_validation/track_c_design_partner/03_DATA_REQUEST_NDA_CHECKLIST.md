# Data-Request + NDA Checklist (per partner)

**INTERNAL + partner-facing.** Operationalizes `../STRATEGY_IMPLEMENTATION_PLAN.md`
§5. Two gates in order: **(A) NDA / data-handling must close BEFORE any ingestion**,
then **(B) the data asks**. Historical Prometheus/HPA exports are the
single highest-leverage item — they power the offline replay that estimates how often
the costly episode happens for this partner.

> **Hard rule:** no partner data is fetched, copied, or replayed until Section A is
> fully checked. If in doubt, do not ingest.

---

## A. NDA / data-handling gate (close first)
- [ ] **Mutual NDA signed** (or partner's NDA accepted) covering metrics, incidents,
      and any cost figures shared.
- [ ] **Data-handling terms agreed** in writing:
  - [ ] storage location + access list (who on our side can see it);
  - [ ] retention + **deletion-on-request / end-of-pilot** commitment;
  - [ ] **no redistribution**; results shared back to the partner before any external use.
- [ ] **Scope of read-only access** defined (which cluster, which namespaces, which
      Prometheus endpoint) — **read-only token / RBAC only; zero write permissions.**
- [ ] **PII / sensitive-label check:** confirm exports carry metric series only — no
      request bodies, no customer identifiers, no secrets. Agree a label-scrub if any
      metric names leak sensitive context.
- [ ] **Named contacts:** partner data owner + our data owner; partner **SRE
      adjudicator** identified (see Section B).
- [ ] **Right to withdraw** stated: partner can stop the pilot and require deletion at
      any time.

## B. Data asks (the §5 list)
Priority key — **★ critical** (replay can't start without it), ◆ important, ○ helpful.

| # | Item | Pri | Why it matters | Min → Ideal |
|---|---|---|---|---|
| 1 | **Prometheus / HPA metric exports** | ★ | Powers offline replay → the frequency estimate. The five signals (CPU, memory, p99 latency, error rate, queue depth) + HPA current/desired replicas. | 6 mo, 1 cluster → 12 mo, several clusters |
| 2 | **Replica history** (current/desired over time, per key deployment) | ★ | Reconstructs each scaling decision the verdict re-judges. | key deployments → all autoscaled deployments |
| 3 | **HPA / Karpenter / KEDA scaling-event logs** | ◆ | Marks when/why a scale-out fired — anchors each verdict to a real action. | HPA events → full autoscaler audit log |
| 4 | **Incident timelines** for the period | ◆ | Lets us overlap flagged episodes with real incidents (Tier-A test). | major incidents → full incident log |
| 5 | **Postmortems** | ◆ | Confirms whether scaling amplified an incident, and attributes cost. | top postmortems → all for the window |
| 6 | **Cost assumptions** ($/replica-hour or cluster spend) | ◆ | Prices each episode for the cost model — **for the partner's own episode pricing, not a savings claim**. | a $/replica-hour estimate → real cluster spend |
| 7 | **Read-only shadow permission** on ≥1 representative cluster | ★ | Live read-only run (Track A) — precision on real noisy metrics. **Zero write perms.** | 1 cluster, ~2 wks → ongoing, multiple clusters |
| 8 | **SRE adjudicator** committed to label flagged episodes true/false | ★ | Without adjudication, flags are unproven. ~30 min/week. | 1 named SRE → SRE + cost owner |

## C. The frictionless path (lead with this)
1. **Read-only shadow** on one cluster (item 7) — the easiest yes; no write access, no
   production risk, off at will.
2. **Historical export** (items 1–2) — highest leverage; replay turns months of their
   past into a frequency estimate within weeks.
3. **One SRE, 30 min/week** (item 8) — the trust step; nothing counts as evidence
   without it.

Items 3–6 enrich the cost/incident attribution and can follow once the relationship
and NDA are in place.

## D. Handover format (make it easy for them)
- [ ] Prometheus: `/api/v1/query_range` export (CSV/JSON) **or** a snapshot / read
      replica — whichever is least work for them.
- [ ] Replica history & scaling events: kube-state-metrics series or HPA/Karpenter
      event export.
- [ ] Incidents/postmortems: whatever format exists (tickets, docs) — we adapt.
- [ ] Confirm we provide a short **ingestion adapter** for their export format; they
      don't reshape data for us.

---

## Per-partner status (copy one block per org)
```
Org:                         ____
NDA signed (date):           ____
Data-handling terms (date):  ____
Read-only scope agreed:      ____  (cluster / namespaces / prom endpoint)
PII/label check done:        yes / no
SRE adjudicator named:       ____
─────────────────────────────────────────────
[ ] 1 Prometheus/HPA exports   range: ____   received: ____
[ ] 2 Replica history          scope: ____   received: ____
[ ] 3 Scaling-event logs       received: ____
[ ] 4 Incident timelines       received: ____
[ ] 5 Postmortems              received: ____
[ ] 6 Cost assumptions         $/replica-hr: ____  or spend: ____
[ ] 7 Read-only shadow access  cluster: ____  granted: ____
[ ] 8 SRE adjudicator booked   cadence: ____
Ingestion can begin (A complete + ≥ item 1):   yes / no
```
