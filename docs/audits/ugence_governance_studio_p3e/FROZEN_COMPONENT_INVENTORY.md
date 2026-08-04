# Frozen Component Inventory (P3E)

The deployment **bundle** identity is `governance-studio-private-hosted` **0.1.0**,
distinct from every component it packages:

| Component | Version | Packaged as |
|-----------|---------|-------------|
| Frontend | 0.2.0 | static build (`dist`) + `frontend-build.json` marker |
| Backend API | 0.1.0 (`governance_studio.api.v1`) | `create_app()` imported unmodified |
| AWC | 0.2.1 | dependency of the backend |
| Compiler | 0.2.0 | dependency of AWC |
| OpenAPI | sha256 `dc309eab…` (unchanged) | shipped read-only; hash-checked at startup |
| Platform digest | `d993093570…` (unchanged) | — |

Synthetic scenario bundle: `procurement`, `customer_support`, `cybersecurity_success`,
`cybersecurity_no_feasible_team`, pinned and hashed in
`deployment/governance-studio/synthetic-scenarios-manifest.json`
(`data_classification = SYNTHETIC_DEMONSTRATION_ONLY`).

The only new code is the `governance_studio_deployment` wrapper package — HTTPS,
access gate, synthetic enforcement, startup integrity, static serving. It changes no
ranking/composition/eligibility/replay/comparison/fallback/permission-proposal/what-if
behavior and no OpenAPI/AWC/compiler source.
