# Adapter Provenance & Registry

> The adapter registry is an **immutable, resolved projection** consumed during a
> pilot — not a mutable policy-administration database. Machine-readable companions:
> `docs/adapter_registry_schema.json`, `docs/adapter_capabilities.json`.

## Registry projection

Per adapter the registry declares the approved source identity, approved versions,
approved hosts/endpoints, approved signal types, the maximum trust level a signal
may claim, freshness/response limits, the credential-resolver **reference** (never
the credential), the enabled flag, and policy refs. `authorize(...)` fails closed
on an unregistered adapter, an unregistered source, a disabled adapter, an
unapproved version, a cross-tenant use, or an over-claimed trust level.

## Supply-chain trust (MVP 1D level)

Each adapter result preserves adapter package identity, adapter version, source
identity, source endpoint class, and the registry projection version. This phase
does **not** claim cryptographic code signing. For the configured shadow trust
level,

```
approved adapter id + approved version + approved source + verified response digest
```

is sufficient. A future phase may add signed producers (trust level 3) behind the
same registry.

## Provenance fingerprints

Deterministic, domain-separated SHA-256 fingerprints cover the adapter request, the
normalized source response, the adapter result, each pilot evaluation input/output,
each reviewer-feedback record, each metrics snapshot, and the pilot report. None
include credentials, network socket metadata, local temporary paths, retry jitter,
object addresses, or insertion timestamps unrelated to semantics. Transport timing
may be recorded as an operational metric but is excluded from semantic fingerprints.
