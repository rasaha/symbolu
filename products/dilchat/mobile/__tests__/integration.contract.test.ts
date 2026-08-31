/**
 * Contract-level integration test.
 *
 * This drives the REAL HttpClient and the REAL typed endpoint functions
 * (@/api/endpoints) against a mocked global.fetch that returns contract-shaped
 * responses. It is NOT a live-server test — it asserts that the client sends the
 * correct method/path/bearer for each step of the mobile journey and parses the
 * committed response shapes. It never hits a network.
 */
import { HttpClient, type TokenProvider } from "@/api/client";
import { AuthApi, BirthProfileApi, ChatApi, CoupleApi, UserApi } from "@/api/endpoints";
import { getApiBaseUrl } from "@/config/env";
import type { BirthProfileCreateRequest } from "@/api/types";

const BASE = getApiBaseUrl();

interface Recorded {
  method: string;
  path: string;
  auth: string | null;
  body: unknown;
}

function makeFetch(): { fetchMock: jest.Mock; calls: Recorded[]; reply: (status: number, body: unknown) => void } {
  const calls: Recorded[] = [];
  const queue: { status: number; body: unknown }[] = [];
  const fetchMock = jest.fn(async (url: string, init: RequestInit) => {
    const headers = (init.headers ?? {}) as Record<string, string>;
    calls.push({
      method: init.method ?? "GET",
      path: url.replace(BASE, ""),
      auth: headers["Authorization"] ?? null,
      body: init.body ? JSON.parse(init.body as string) : undefined,
    });
    const next = queue.shift() ?? { status: 200, body: null };
    return {
      status: next.status,
      ok: next.status >= 200 && next.status < 300,
      text: async () => (next.body === undefined ? "" : JSON.stringify(next.body)),
    } as unknown as Response;
  });
  return { fetchMock, calls, reply: (status, body) => queue.push({ status, body }) };
}

describe("contract-level journey against a fetch mock", () => {
  const { fetchMock, calls, reply } = makeFetch();

  const provider: TokenProvider = {
    getAccessToken: async () => "ACCESS",
    refresh: async () => null,
    onAuthLost: () => undefined,
  };
  const client = new HttpClient(provider);

  beforeAll(() => {
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;
  });

  it("register -> login -> me -> profile -> invite -> accept -> current -> unpair", async () => {
    // register (auth:false)
    reply(200, { user_id: "u1", email: "a@example.com" });
    const reg = await AuthApi.register(client, { email: "a@example.com", password: "password123" });
    expect(reg).toEqual({ user_id: "u1", email: "a@example.com" });

    // login (auth:false)
    reply(200, { access_token: "AT", refresh_token: "RT", expires_in: 3600, token_type: "bearer" });
    const tok = await AuthApi.login(client, { email: "a@example.com", password: "password123" });
    expect(tok.access_token).toBe("AT");

    // me
    reply(200, { id: "u1", email: "a@example.com", status: "ACTIVE", created_at: "2026-01-01T00:00:00Z" });
    const me = await UserApi.me(client);
    expect(me.email).toBe("a@example.com");

    // create birth profile
    const body: BirthProfileCreateRequest = {
      preferred_name: "Asha",
      birth_date: "1990-05-14",
      birth_time_precision: "EXACT",
      birth_time_local: "08:30",
      uncertainty_minutes: null,
      birthplace_label: "Pune",
      iana_timezone: "Asia/Kolkata",
      latitude: 18.52,
      longitude: 73.85,
    };
    reply(201, {
      id: "bp1",
      version: 1,
      preferred_name: "Asha",
      birth_date: "1990-05-14",
      birth_time_precision: "EXACT",
      has_birth_time: true,
      uncertainty_minutes: null,
      birthplace_label: "Pune",
      iana_timezone: "Asia/Kolkata",
      input_confidence: 1,
      utc_birth_instant: "1990-05-14T03:00:00Z",
      utc_interval: null,
    });
    const bp = await BirthProfileApi.create(client, body);
    expect(bp.id).toBe("bp1");

    // create invitation
    reply(201, { invitation_id: "inv1", token: "TOKEN123", expires_at: "2026-08-05T00:00:00Z" });
    const inv = await CoupleApi.createInvitation(client);
    expect(inv.token).toBe("TOKEN123");

    // accept invitation
    reply(200, {
      couple_id: "c1",
      status: "ACTIVE",
      members: [
        { user_id: "u1", scope_slot: "PRIVATE_A", status: "ACTIVE" },
        { user_id: "u2", scope_slot: "PRIVATE_B", status: "ACTIVE" },
      ],
    });
    const accepted = await CoupleApi.acceptInvitation(client, "TOKEN123");
    expect(accepted.couple_id).toBe("c1");
    expect(accepted.members).toHaveLength(2);

    // current couple
    reply(200, { couple_id: "c1", status: "ACTIVE", members: accepted.members });
    const current = await CoupleApi.current(client);
    expect(current?.couple_id).toBe("c1");

    // unpair (204)
    reply(204, undefined);
    await expect(CoupleApi.unpair(client, "c1")).resolves.toBeUndefined();

    // ---- Assert the exact contract wire shape for each recorded call. ----
    expect(calls[0]).toMatchObject({ method: "POST", path: "/v1/auth/register", auth: null });
    expect(calls[1]).toMatchObject({ method: "POST", path: "/v1/auth/login", auth: null });
    expect(calls[2]).toMatchObject({ method: "GET", path: "/v1/users/me", auth: "Bearer ACCESS" });
    expect(calls[3]).toMatchObject({ method: "POST", path: "/v1/birth-profiles", auth: "Bearer ACCESS" });
    expect(calls[3]?.body).toMatchObject({ preferred_name: "Asha", iana_timezone: "Asia/Kolkata" });
    expect(calls[4]).toMatchObject({ method: "POST", path: "/v1/couples/invitations", auth: "Bearer ACCESS" });
    expect(calls[5]).toMatchObject({
      method: "POST",
      path: "/v1/couples/invitations/TOKEN123/accept",
      auth: "Bearer ACCESS",
    });
    expect(calls[6]).toMatchObject({ method: "GET", path: "/v1/couples/current", auth: "Bearer ACCESS" });
    expect(calls[7]).toMatchObject({ method: "POST", path: "/v1/couples/c1/unpair", auth: "Bearer ACCESS" });
  });

  it("chat journey: current conversation -> paged history -> idempotent send -> read state", async () => {
    const base = calls.length;

    // current conversation
    reply(200, {
      conversation_id: "conv1",
      couple_id: "c1",
      status: "ACTIVE",
      created_at: "2026-01-01T00:00:00Z",
      latest_sequence: 2,
      last_read_sequence: 0,
      member_user_ids: ["u1", "u2"],
    });
    const conv = await ChatApi.current(client);
    expect(conv.conversation_id).toBe("conv1");

    const msg = (seq: number, cid: string, body: string | null) => ({
      message_id: `m${seq}`,
      conversation_id: "conv1",
      sender_user_id: "u2",
      client_message_id: cid,
      server_sequence: seq,
      body,
      created_at: "2026-01-01T00:00:01Z",
      deleted: body === null,
      deleted_at: body === null ? "2026-01-01T01:00:00Z" : null,
    });

    // first page (no cursor), then the next page via the opaque server cursor
    reply(200, { messages: [msg(1, "ca", "hello")], next_cursor: "CURSOR1", has_more: true });
    const page1 = await ChatApi.listMessages(client, "conv1", null, 50);
    expect(page1.has_more).toBe(true);
    reply(200, { messages: [msg(2, "cb", null)], next_cursor: null, has_more: false });
    const page2 = await ChatApi.listMessages(client, "conv1", page1.next_cursor);
    expect(page2.messages[0]?.body).toBeNull(); // tombstone shape survives parsing

    // send, then replay the SAME client_message_id (idempotent retry after timeout)
    reply(201, msg(3, "client-key-1", "sent"));
    const sent = await ChatApi.sendMessage(client, "conv1", { client_message_id: "client-key-1", body: "sent" });
    expect(sent.server_sequence).toBe(3);
    reply(200, msg(3, "client-key-1", "sent")); // replay returns the ORIGINAL row
    const replayed = await ChatApi.sendMessage(client, "conv1", { client_message_id: "client-key-1", body: "sent" });
    expect(replayed.message_id).toBe(sent.message_id);

    // forward-only read state
    reply(200, { conversation_id: "conv1", user_id: "u1", last_read_sequence: 3, updated_at: "2026-01-01T02:00:00Z" });
    const rs = await ChatApi.updateReadState(client, "conv1", 3);
    expect(rs.last_read_sequence).toBe(3);

    // ---- Wire-shape assertions ----
    expect(calls[base + 0]).toMatchObject({ method: "GET", path: "/v1/conversations/current", auth: "Bearer ACCESS" });
    expect(calls[base + 1]).toMatchObject({
      method: "GET",
      path: "/v1/conversations/conv1/messages?limit=50",
      auth: "Bearer ACCESS",
    });
    expect(calls[base + 2]).toMatchObject({
      method: "GET",
      path: "/v1/conversations/conv1/messages?cursor=CURSOR1",
      auth: "Bearer ACCESS",
    });
    expect(calls[base + 3]).toMatchObject({ method: "POST", path: "/v1/conversations/conv1/messages", auth: "Bearer ACCESS" });
    expect(calls[base + 3]?.body).toEqual({ client_message_id: "client-key-1", body: "sent" });
    expect(calls[base + 4]?.body).toEqual({ client_message_id: "client-key-1", body: "sent" });
    expect(calls[base + 5]).toMatchObject({ method: "PUT", path: "/v1/conversations/conv1/read-state", auth: "Bearer ACCESS" });
    expect(calls[base + 5]?.body).toEqual({ last_read_sequence: 3 });
  });
});
