/**
 * Typed request/response models mirroring the DilChat backend OpenAPI 3.1
 * contract (see docs/DILCHAT_MOBILE_API_CONTRACT_MAP.md). These are hand-written
 * to match the committed schema; the contract-drift check compares this file's
 * covered operations against the live OpenAPI document.
 *
 * NOTE: There are deliberately NO Guna / Koota / compatibility types here. Phase 1
 * exposes account, birth profile, invitation, pairing, and consent-UX only.
 */

export interface RegisterRequest {
  email: string;
  password: string;
}
export interface RegisterResponse {
  user_id: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}
export interface RefreshRequest {
  refresh_token: string;
}
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type?: string;
}

export interface UserMeResponse {
  id: string;
  email: string;
  status: string;
  created_at: string;
}

export type BirthTimePrecision = "EXACT" | "APPROXIMATE" | "UNKNOWN";
export type AmbiguityResolution = "EARLIER" | "LATER";

export interface UtcIntervalModel {
  start: string;
  end: string;
}

export interface BirthProfileCreateRequest {
  preferred_name: string;
  birth_date: string; // YYYY-MM-DD
  birth_time_precision: BirthTimePrecision;
  birth_time_local?: string | null; // HH:MM[:SS]
  uncertainty_minutes?: number | null; // 1..720
  ambiguity_resolution?: AmbiguityResolution | null;
  birthplace_label: string;
  iana_timezone: string;
  latitude: number;
  longitude: number;
}

export interface BirthProfileResponse {
  id: string;
  version: number;
  preferred_name: string;
  birth_date: string;
  birth_time_precision: BirthTimePrecision;
  has_birth_time: boolean;
  uncertainty_minutes: number | null;
  birthplace_label: string;
  iana_timezone: string;
  input_confidence: number;
  utc_birth_instant: string | null;
  utc_interval: UtcIntervalModel | null;
}

export interface InvitationCreateResponse {
  invitation_id: string;
  token: string;
  expires_at: string;
}

export interface MemberModel {
  user_id: string;
  scope_slot: string;
  status: string;
}
export interface CoupleResponse {
  couple_id: string;
  status: string;
  members: MemberModel[];
}
