# Pilot Deployment Configuration

> `PilotDeploymentConfig` is immutable, versioned, and **fails closed**. It names
> explicit repositories/branches, an explicit tenant, bounded evaluation and
> concurrency, a durable store, and credential *references* — never a credential
> value. Machine-readable companion: `docs/pilot_deployment_config_schema.json`.

## Rejected configurations (fail closed)

Empty repository allowlist · wildcard/empty tenant · unrestricted repositories
(`*`, `owner/*`) · unrestricted/empty branches · a `*:write` credential scope ·
missing evaluation bound *and* pilot end · concurrency outside `1..4` · missing
durable store · inline credentials (`token`/`secret`/…) · unsupported schema
version.

## Loading

`load_pilot_config(mapping)` / `load_pilot_config_json(text)` read canonical JSON
(never executable Python) and validate. Inline credential *values* are refused;
only `credential_references` are read.

## Fingerprint

`fingerprint_pilot_config` is content-addressed over the config's names, refs, and
bounds. It **excludes credential values** — credential references contribute only
their reference id, resolver kind, source host, env-var name, and scopes. Restart
recovery uses this fingerprint to detect configuration drift.
