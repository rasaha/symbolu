/**
 * Typed endpoint functions, one per mobile action in the API contract map.
 * Each takes an HttpClient. Auth-less calls (register/login/refresh) pass
 * auth:false; everything else sends the bearer token.
 */
import type { HttpClient } from "@/api/client";
import type {
  BirthProfileCreateRequest,
  BirthProfileResponse,
  CoupleResponse,
  InvitationCreateResponse,
  LoginRequest,
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
