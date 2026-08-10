# Reason-Code Taxonomy

*Phase 3 deliverable. A stable, machine-readable, auditable taxonomy — distinct from raw
provider error strings and mappable back to supporting evidence. Implemented as an enum in
`execution_gate/reason_codes.py`; changing a code's meaning is a breaking change requiring
a version bump.*

## Properties

- **Stable**: codes are append-only; existing codes never change meaning.
- **Machine-readable**: uppercase snake enum; no free text in the code itself.
- **Auditable**: every emitted code is paired with an `Evidence` record (source, timestamp,
  confidence, raw signal reference) so it traces to what was observed.
- **Distinct from provider strings**: raw errors (e.g. `InvalidClientTokenId`,
  `RESOURCE_EXHAUSTED`) are *normalized* into codes; the raw string is retained in evidence,
  never used as the code.

## Codes by category

### Network / transport
| Code | Meaning | Class | Typical raw signal |
|---|---|---|---|
| `NETWORK_BLOCKED` | Endpoint denied by network/proxy policy | CRITICAL-GOV/OP | proxy `403 CONNECT` |
| `DNS_FAILURE` | Host did not resolve | CRITICAL-OP | NXDOMAIN |
| `TLS_FAILURE` | TLS handshake/verification failed | CRITICAL-OP | cert error |

### Authentication / credential
| `AUTH_MISSING` | No credential present | CRITICAL-OP | env var unset |
| `AUTH_INVALID` | Credential rejected | CRITICAL-OP | `InvalidClientTokenId`, `invalid_token`, `401` |
| `AUTH_EXPIRED` | Credential expired | CRITICAL-OP | token exp in past |

### Billing / quota
| `BILLING_INACTIVE` | No active billing account | CRITICAL-OP | free-tier-only quota IDs |
| `FREE_TIER_ONLY` | Project limited to free tier | CRITICAL-OP | `*-FreeTier` quota metric |
| `QUOTA_EXHAUSTED` | Daily/token quota spent | OPERATIONAL | `429` per-day quota |
| `RATE_LIMITED` | Transient per-minute limit | OPERATIONAL | `429` per-minute + short RetryInfo |

### Model availability
| `MODEL_NOT_FOUND` | Model ID not served to account | CRITICAL-OP | `404 model_not_found` |
| `MODEL_DISABLED` | Known model turned off in registry | CRITICAL-OP | registry `enabled=false` |

### Region / residency / governance
| `REGION_UNAVAILABLE` | Model not offered in required region | CRITICAL-GOV | region list miss |
| `DATA_RESIDENCY_VIOLATION` | Serving region violates residency rule | CRITICAL-GOV | residency policy |
| `PROVIDER_NOT_APPROVED` | Provider not on enterprise allowlist | CRITICAL-GOV | governance config |

### Capability / request features
| `FEATURE_UNSUPPORTED` | Required feature (structured output, tools, modality) unsupported | CRITICAL-OP | capability metadata |
| `CONTEXT_TOO_SMALL` | Request exceeds model context | CRITICAL-OP | token count > limit |

### Operational limits
| `COST_LIMIT_EXCEEDED` | Projected cost over cap | CRITICAL-OP | cost estimate > cap |
| `LATENCY_LIMIT_EXCEEDED` | Observed/expected latency over SLA | OPERATIONAL | telemetry p95 |
| `RELIABILITY_BELOW_THRESHOLD` | Recent success rate below floor | OPERATIONAL | telemetry |
| `PROVIDER_DEGRADED` | Provider in partial outage | OPERATIONAL | health signal |

### Evidence quality
| `POLICY_STATE_UNKNOWN` | Governance state cannot be established | CRITICAL-GOV (fail-closed) | missing config |
| `TELEMETRY_STALE` | Evidence past TTL | OPERATIONAL | age > TTL |

### Positive sentinel
| `OK` | Condition satisfied | — | — |

## Mapping: raw provider signal → normalized code (examples, credentials removed)

| Raw signal observed in V1/V2 investigation | Normalized code |
|---|---|
| proxy `Tunnel connection failed: 403 Forbidden` (mistral/openai/dashscope/moonshot) | `NETWORK_BLOCKED` |
| Anthropic `404 not_found_error: model:` | `MODEL_NOT_FOUND` |
| Google `429 RESOURCE_EXHAUSTED` + `GenerateRequests...-FreeTier` | `FREE_TIER_ONLY` + `QUOTA_EXHAUSTED` |
| Google `429` + short `RetryInfo` only | `RATE_LIMITED` |
| Google `404` (`gemini-2.5-flash`) | `MODEL_NOT_FOUND` |
| AWS `InvalidClientTokenId` | `AUTH_INVALID` |
| Google OAuth `invalid_token` | `AUTH_INVALID` |

## Usage rule

An `EligibilityDecision` for a non-ELIGIBLE candidate MUST include the set of codes that
drove it, each with its evidence. ModelPolicy consumes codes (not raw strings) so its
exclusion logic is provider-neutral and auditable.
