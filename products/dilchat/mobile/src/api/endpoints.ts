/**
 * Typed endpoint functions, one per mobile action in the API contract map.
 * Each takes an HttpClient. Auth-less calls (register/login/refresh) pass
 * auth:false; everything else sends the bearer token.
 */
import type { HttpClient } from "@/api/client";
import type {
  BirthProfileCreateRequest,
  BirthProfileResponse,
  ConversationResponse,
  CoupleResponse,
  InvitationCreateResponse,
  LoginRequest,
  MessageCreateRequest,
  MessageListResponse,
  MessageResponse,
  ReadStateResponse,
  RegisterRequest,
  RegisterResponse,
  TokenResponse,
  UserMeResponse,
} from "@/api/types";

export const AuthApi = {
  register: (c: HttpClient, body: RegisterRequest) =>
    c.post<RegisterResponse>("/v1/auth/register", body, false),
  login: (c: HttpClient, body: LoginRequest) =>
    c.post<TokenResponse>("/v1/auth/login", body, false),
  refresh: (c: HttpClient, refresh_token: string) =>
    c.post<TokenResponse>("/v1/auth/refresh", { refresh_token }, false),
  logout: (c: HttpClient) => c.post<void>("/v1/auth/logout"),
  logoutAll: (c: HttpClient) => c.post<void>("/v1/auth/logout-all"),
};

export const UserApi = {
  me: (c: HttpClient) => c.get<UserMeResponse>("/v1/users/me"),
};

export const BirthProfileApi = {
  get: (c: HttpClient) => c.get<BirthProfileResponse>("/v1/birth-profiles/me"),
  create: (c: HttpClient, body: BirthProfileCreateRequest) =>
    c.post<BirthProfileResponse>("/v1/birth-profiles", body),
  update: (c: HttpClient, body: BirthProfileCreateRequest) =>
    c.patch<BirthProfileResponse>("/v1/birth-profiles/me", body),
};

export const CoupleApi = {
  current: (c: HttpClient) => c.get<CoupleResponse | null>("/v1/couples/current"),
  createInvitation: (c: HttpClient) =>
    c.post<InvitationCreateResponse>("/v1/couples/invitations"),
  acceptInvitation: (c: HttpClient, token: string) =>
    c.post<CoupleResponse>(`/v1/couples/invitations/${encodeURIComponent(token)}/accept`),
  unpair: (c: HttpClient, coupleId: string) =>
    c.post<void>(`/v1/couples/${encodeURIComponent(coupleId)}/unpair`),
};

export const ChatApi = {
  /** The couple's single conversation; 404 when unpaired or revoked. */
  current: (c: HttpClient) => c.get<ConversationResponse>("/v1/conversations/current"),
  /**
   * Forward cursor pagination in ascending server_sequence order: no cursor
   * starts at the oldest message; next_cursor (opaque, server-minted) continues
   * toward newer ones while has_more is true.
   */
  listMessages: (c: HttpClient, conversationId: string, cursor?: string | null, limit?: number) => {
    // Built by hand: React Native's URLSearchParams.toString() is unimplemented
    // on the device runtime, so it must not be relied on here.
    const params: string[] = [];
    if (cursor) params.push(`cursor=${encodeURIComponent(cursor)}`);
    if (limit !== undefined) params.push(`limit=${encodeURIComponent(String(limit))}`);
    const qs = params.length ? `?${params.join("&")}` : "";
    return c.get<MessageListResponse>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/messages${qs}`,
    );
  },
  /** Idempotent on (conversation, sender, client_message_id): a retry with the
   * same key returns the original message instead of duplicating it. */
  sendMessage: (c: HttpClient, conversationId: string, body: MessageCreateRequest) =>
    c.post<MessageResponse>(`/v1/conversations/${encodeURIComponent(conversationId)}/messages`, body),
  /** Forward-only: the backend ignores a value at or below the stored one. */
  updateReadState: (c: HttpClient, conversationId: string, last_read_sequence: number) =>
    c.put<ReadStateResponse>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/read-state`,
      { last_read_sequence },
    ),
};
