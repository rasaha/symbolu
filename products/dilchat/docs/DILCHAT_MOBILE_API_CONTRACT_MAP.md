# DilChat Mobile Phase 1 — API Contract Map

Every mobile action maps to an **existing** DilChat backend OpenAPI 3.1 operation
(generated from `products/dilchat` via `ugence_dilchat.scripts_openapi`). **No new
route, model, or migration was required for this vertical slice** — all endpoints
below already exist and are covered by the backend test suite.

> **Auth model.** Endpoints that operate on the caller's data require an
> `Authorization: Bearer <access_token>` header (ES256 JWT). The backend
> additionally checks the server-side session on every request, so a revoked /
> rotated / logged-out session is rejected even if the access token has not yet
> expired (`get_current_principal` in `api/deps.py`). Errors are problem+json with
> a machine `code` (e.g. `AUTH_REQUIRED`, `AUTH_SESSION_REVOKED`,
> `VALIDATION_ERROR`). There is no OpenAPI `securityScheme` object; the bearer
> requirement is enforced by the dependency, documented here.

| # | Mobile action | Method | Route | Request | Response (success) | Auth | Authorization behaviour | Errors | Retry | Idempotency | Privacy | Backend tests |
|---|---------------|--------|-------|---------|--------------------|------|-------------------------|--------|-------|-------------|---------|---------------|
| 1 | Register account | POST | `/v1/auth/register` | `RegisterRequest{email,password}` | `201 RegisterResponse{user_id,email}` | none | creates a new user; existing email returns a neutral error (no account-existence disclosure) | 422 | no auto-retry | client sends once; re-register with same email fails closed | credentials in body only, never logged | `test_flows.py`, `test_security_primitives.py` |
| 2 | Sign in | POST | `/v1/auth/login` | `LoginRequest{email,password}` | `200 TokenResponse{access_token,refresh_token,expires_in,token_type}` | none | verifies Argon2id password; issues access + rotating refresh | 422 (invalid creds, neutral) | no auto-retry | new session per login | tokens → SecureStore only | `test_flows.py` |
| 3 | Restore / refresh session | POST | `/v1/auth/refresh` | `RefreshRequest{refresh_token}` | `200 TokenResponse` | none (refresh token in body) | rotates refresh token; reuse of a rotated token revokes the chain | 422 (invalid/rotated) | **one** controlled refresh attempt per 401 | rotates; old token invalid after use | refresh token SecureStore only | `test_flows.py`, `test_security_primitives.py` |
| 4 | Load current user | GET | `/v1/users/me` | — | `200 UserMeResponse{id,email,status,created_at}` | **Bearer** | returns only the caller's own record | 401 | refresh-once then re-auth | safe to repeat | own account only | `test_flows.py` |
| 5 | Sign out (this device) | POST | `/v1/auth/logout` | — | `204` | **Bearer** | revokes the current session only | 401 | none | idempotent (already-revoked ⇒ still clears client) | — | `test_flows.py` |
| 6 | Sign out everywhere | POST | `/v1/auth/logout-all` | — | `204` | **Bearer** | revokes all of the caller's sessions | 401 | none | idempotent | — | `test_flows.py` |
| 7 | Create birth profile | POST | `/v1/birth-profiles` | `BirthProfileCreateRequest` | `201 BirthProfileResponse` | **Bearer** | writes the caller's own profile (RLS owner) | 422 | no auto-retry | one profile per user; re-post ⇒ conflict/replace per backend | own profile only | `test_flows.py`, `test_rls.py` |
| 8 | Load my birth profile | GET | `/v1/birth-profiles/me` | — | `200 BirthProfileResponse` | **Bearer** | returns only the caller's profile | 401 | refresh-once | safe to repeat | own profile only | `test_flows.py`, `test_rls.py` |
| 9 | Edit my birth profile | PATCH | `/v1/birth-profiles/me` | `BirthProfileCreateRequest` | `201 BirthProfileResponse` (new version) | **Bearer** | updates only the caller's profile; **cannot** touch a partner's | 422 | no auto-retry | server versions the profile (`version` increments) | own profile only | `test_flows.py`, `test_rls.py` |
| 10 | Create partner invitation | POST | `/v1/couples/invitations` | — | `201 InvitationCreateResponse{invitation_id,token,expires_at}` | **Bearer** | issues a single-use, expiring invitation owned by the caller | 401 | no auto-retry | new token each call | token shown once; never logged | `test_flows.py` |
| 11 | Accept invitation (pairing) | POST | `/v1/couples/invitations/{token}/accept` | — (token in path) | `200 CoupleResponse{couple_id,status,members[]}` | **Bearer** | consumes the invitation and pairs the two users; consumed/expired/own-invitation cases fail closed | 422 (invalid/expired/consumed) | no auto-retry (avoid double-consume) | consuming twice fails; simultaneous accept resolved by backend | reveals only couple id + member scope slots | `test_flows.py` |
| 12 | Load paired status | GET | `/v1/couples/current` | — | `200 CoupleResponse` (or empty/none when unpaired) | **Bearer** | returns only the couple the caller belongs to | 401 | refresh-once | safe to repeat | minimal relationship metadata only | `test_flows.py`, `test_rls.py` |
| 13 | Unpair | POST | `/v1/couples/{couple_id}/unpair` | — | `204` | **Bearer** | either member may unpair; revokes shared access immediately | 422 (not a member / not found → non-disclosure) | no auto-retry | idempotent-ish (already-unpaired ⇒ handled) | — | `test_flows.py`, `test_rls.py` |

## Notes on scope

- **Pairing consent** in Phase 1 is the explicit in-app affirmation the user makes
  **before** action 10 (create invitation) and action 11 (accept) — it gates those
  calls. The backend `POST /v1/consents` operation is a **shared-artifact** consent
  (consenting to publish a bounded summary into the SHARED scope) and is **out of
  scope** for Phase 1, because Phase 1 shares **no** compatibility artifact. It is
  intentionally not called by the mobile client.
- **Natal / astrology** endpoints (`/v1/natal/moon*`) exist but are **not** used by
  the mobile client — Phase 1 computes and displays **no** natal Moon, Nakshatra,
  Guna, or compatibility value. There is no Guna or compatibility route to call.
- **Error normalization.** All non-2xx responses are parsed as problem+json into a
  typed `ApiError{status, code, detail}`; the client distinguishes network errors
  from server errors and never logs tokens or request bodies containing credentials.

## Gaps

**None.** Every required Phase-1 action maps to an existing, tested backend
operation. No backend addition, database change, or migration was made in this
phase.
