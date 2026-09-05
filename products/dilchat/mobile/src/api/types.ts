/**
 * Typed request/response models mirroring the DilChat backend OpenAPI 3.1
 * contract (see docs/DILCHAT_MOBILE_API_CONTRACT_MAP.md). These are hand-written
 * to match the committed schema; the contract-drift check compares this file's
 * covered operations against the live OpenAPI document.
 *
 * NOTE: There are deliberately NO Guna / Koota / compatibility types here. The
 * client exposes account, birth profile, invitation, pairing, consent-UX, and
 * (Phase 3D) the secure 1:1 text chat only.
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

// --- Secure 1:1 chat (Phase 3D client over the merged Phase 3A backend) ----- //
// The conversation summary deliberately carries no message body; message bodies
// appear only in MessageResponse and are null for tombstoned (deleted) messages.

export interface ConversationResponse {
  conversation_id: string;
  couple_id: string;
  status: string;
  created_at: string;
  latest_sequence: number;
  last_read_sequence: number;
  member_user_ids: string[];
}

export interface MessageCreateRequest {
  client_message_id: string; // ^[A-Za-z0-9._:\-]{1,64}$ — idempotency key
  body: string; // 1..4000 code points, text only
}

export interface MessageResponse {
  message_id: string;
  conversation_id: string;
  sender_user_id: string;
  client_message_id: string;
  server_sequence: number;
  body: string | null; // null when the message is a tombstone
  created_at: string;
  deleted: boolean;
  deleted_at: string | null;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ReadStateUpdateRequest {
  last_read_sequence: number; // forward-only; the backend no-ops a backward value
}

export interface ReadStateResponse {
  conversation_id: string;
  user_id: string;
  last_read_sequence: number;
  updated_at: string;
}

// --- push devices (Phase 3C mobile slice, DILCHAT-D3C-M1/M2) ---------------- //
// A registration is a device installation owned by the user — never a session
// credential. The push token is write-only: no response ever carries it back.

export type DevicePlatform = "IOS" | "ANDROID" | "UNKNOWN";

export interface DeviceRegisterRequest {
  push_token: string; // SENSITIVE: never logged or displayed
  platform: DevicePlatform;
}

export interface DeviceResponse {
  device_id: string;
  platform: string;
  status: string;
  created_at: string;
  revoked_at: string | null;
}

export interface DeviceListResponse {
  devices: DeviceResponse[];
}
