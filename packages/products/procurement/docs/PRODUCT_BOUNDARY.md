# Product Boundary

Ugence Procurement has a deliberately narrow scope: it governs the **approval of a
purchase and the authorized dispatch of a supplier action**. Everything outside
that boundary is explicitly out of scope and not shipped.

## What it is

A governed purchase-approval and authorized-supplier-action product that walks a
purchase request through a complete, audited governance lifecycle:

```
purchase request → deterministic validation → deterministic policy assessment
→ advisory recommendation → HUMAN approval decision → governed action request
(exactly bound to the approved supplier / budget / amount) → neutral authorization
→ EXPLICIT supplier dispatch → observed supplier outcome → reconciliation
→ compensation-when-required
```

It enforces authority boundaries in types, services, and API — not merely in
documentation (see [AUTHORITY_MODEL.md](AUTHORITY_MODEL.md)).

## What it is NOT

| It is NOT | It does NOT |
|---|---|
| an ERP | manage inventory |
| a purchasing marketplace | do accounting or ledger posting |
| an inventory system | process invoices |
| an accounting system | process payments |
| an invoice/payment system | provide production SAP Ariba / Coupa / ServiceNow / Oracle connectors |
| an autonomous purchasing agent | perform AI scoring or autonomous purchasing behavior |

There is **no** AI scoring model, **no** autonomous approval, and **no** autonomous
purchasing behavior. The only supplier adapter shipped is a **deterministic,
offline reference adapter** — not a real supplier or ERP connector. No live
enterprise pilot has occurred; no production certification is claimed.

## Scope discipline

- The product owns the **purchase domain**; the kernel owns the **governance chain**. Procurement never re-implements governance.
- The supplier is an *external system* reached only through the neutral execution port. Procurement models the supplier's outcomes but does not embed any supplier's protocol.
- Budget authority is expressed as **policy** consulted through the kernel control-plane port; there is no procurement-specific authorization engine.
- Enterprise connectors, persistence backends, and web transports are **future** work described (not implemented) in [NEXT_PHASES.md](NEXT_PHASES.md).

Staying inside this boundary is what lets the entire workflow remain deterministic,
offline-verifiable, and free of production/ERP claims.
