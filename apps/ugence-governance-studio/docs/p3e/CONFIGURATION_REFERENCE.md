# Configuration Reference (P3E)

| Variable | Required | Meaning |
|----------|----------|---------|
| `UGENCE_STUDIO_DEPLOYMENT_MODE` | no | `production` (default) or `test` (loopback) |
| `UGENCE_STUDIO_USERNAME` | yes | operator username (no default) |
| `UGENCE_STUDIO_PASSWORD_HASH` | yes | `scrypt$…` hash (no default; generated offline) |
| `UGENCE_STUDIO_ALLOWED_HOSTS` | yes (prod) | comma-separated Host allowlist; wildcard rejected |
| `UGENCE_STUDIO_TLS_CERT_FILE` | yes | PEM certificate path |
| `UGENCE_STUDIO_TLS_KEY_FILE` | yes | PEM private key path (read-only mount) |
| `UGENCE_STUDIO_TRUSTED_PROXY` | no | `1` to trust `X-Forwarded-For` (only behind a real proxy) |
| `UGENCE_STUDIO_PORT` | no | application port (default 8443) |
| `UGENCE_STUDIO_ACCESS_LOG` | no | `1` to enable access logging (off by default) |
| `UGENCE_STUDIO_REVIEW_SERVICE_URL` | no | base URL of the governed review service, i.e. the governed runtime worker's private TLS listener (`https://host:8444`); `https` only outside loopback test mode, no credential, query or fragment. Handed to `build_studio_context(review_service_base_url=...)` and read nowhere else. Unset: the Review screens report a typed gap (`available: false`, capability `review_service`), never an empty queue. The profile's one permitted outbound destination (CR-2); the approver-proof header passes through to it verbatim and is never logged or stored (ID-1) |
| `UGENCE_STUDIO_CONSTITUTION_REGISTRY_PATH` | no | absolute path of a sqlite file under the writable runtime volume (`/var/run/ugence-studio/constitution-registry.sqlite3`); the policy registry the studio's activation root is composed over (front-door seam 1, FD-5). Read by `DeploymentConfig` only and handed to `build_studio_context(activation_root=...)`. The root uses the constitution authority's deny-by-default verifiers and a signer that refuses every act: preflight reports its real result, issuance and activation refuse, no key material exists. A path outside the volume or in memory is refused; a missing or unwritable directory fails startup integrity before bind. Unset: the Constitution screen reports the typed gap `constitution_preflight` |
| `UGENCE_STUDIO_TENANT_ID` | no | the one tenant the Authority screen displays (typed: NFC, no whitespace, no `|`); required with `UGENCE_STUDIO_POLICY_IDENTITIES`; a record of any other tenant is a typed refusal, never shown (front-door seam 2, FD-6) |
| `UGENCE_STUDIO_POLICY_IDENTITIES` | no | comma-separated typed policy identities, each `<policy_family>\|<policy_id>\|<scope>` (NFC, no whitespace, no duplicates; no discovery, no default); requires the registry path and the tenant. Handed to `build_studio_context(policy_registry=..., policy_identities=...)` as a read-only, tenant-bound view of the seam-1 registry; the Authority screen lists issued records for these identities and reads one record with its revocations and supersessions by canonical reference. Unset: the authority reads keep the typed gap `authority_registry`. The decision read keeps its gap `decision_authority_store` regardless (no durable store exists) |

Frozen packaged paths (`FRONTEND_DIR`, `SCENARIOS_ROOT`, `MANIFEST`, `OPENAPI`,
`APPROVED_OPS`) are set by the image and should not be overridden in production.
