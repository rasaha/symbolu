# Installing ugence-actiongate-provider

```bash
pip install ugence-actiongate-provider
```

Core installs only `ugence-governance-provider-framework` (which pulls
`ugence-governance-contracts` transitively). The default in-process provider path is
network-free.

## Optional extras

| Extra | Adds | Use when |
|---|---|---|
| `decision-authority` | `ugence-governance-provider-framework[adapters]` (Decision Authority kernel) | you run the framework **action control-plane** integration (`ActionGovernanceControlPlaneAdapter`) |
| `dev` | `pytest`, `build` | developing/testing the package |
| `all` | the adapter closure | convenience superset |

```bash
pip install "ugence-actiongate-provider[decision-authority]"
```

## Legacy compatibility

Installing `dgm-actiongate-provider` (the legacy wheel name) pulls this canonical
wheel and provides the `actiongate_provider` compatibility namespace. Prefer
`ugence-actiongate-provider` in new dependency declarations.

Requires Python ≥ 3.10.
