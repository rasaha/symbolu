import { HttpClient, type TokenProvider } from "@/api/client";
import { ApiError } from "@/api/errors";
import { getApiBaseUrl } from "@/config/env";

const BASE = getApiBaseUrl();

function jsonResponse(status: number, body: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => (body === undefined ? "" : JSON.stringify(body)),
  } as unknown as Response;
}

function emptyResponse(status: number): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => "",
  } as unknown as Response;
}

function makeProvider(over: Partial<TokenProvider> = {}): TokenProvider {
  return {
    getAccessToken: async () => "access-1",
    refresh: async () => "access-2",
    onAuthLost: () => undefined,
    ...over,
  };
}

describe("HttpClient", () => {
  const fetchMock = jest.fn();
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchMock.mockReset();
    (global as unknown as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;
    logSpy = jest.spyOn(console, "log").mockImplementation(() => undefined);
  });

  afterEach(() => {
    logSpy.mockRestore();
  });

  it("parses a success JSON body and sends the bearer token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { id: "u1" }));
    const client = new HttpClient(makeProvider());
    const data = await client.get<{ id: string }>("/v1/users/me");
    expect(data).toEqual({ id: "u1" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/v1/users/me`);
    expect((init.headers as Record<string, string>)["Authorization"]).toBe("Bearer access-1");
  });

  it("returns undefined for a 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce(emptyResponse(204));
    const client = new HttpClient(makeProvider());
    const data = await client.post<void>("/v1/couples/abc/unpair");
    expect(data).toBeUndefined();
  });

  it("throws an ApiError on a non-ok response", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(409, { code: "INVITATION_CONSUMED", detail: "used" }));
    const client = new HttpClient(makeProvider());
    await expect(client.post("/v1/couples/invitations/t/accept")).rejects.toMatchObject({
      status: 409,
      code: "INVITATION_CONSUMED",
    });
  });

  it("performs exactly one refresh + retry on a 401, then succeeds", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "u1" }));
    const refresh = jest.fn(async () => "access-2");
    const client = new HttpClient(makeProvider({ refresh }));
    const data = await client.get<{ id: string }>("/v1/users/me");
    expect(data).toEqual({ id: "u1" });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const secondInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect((secondInit.headers as Record<string, string>)["Authorization"]).toBe("Bearer access-2");
  });

  it("single-flights refresh: concurrent 401s trigger exactly ONE refresh", async () => {
    // The backend rotates refresh tokens and revokes the whole session chain on
    // reuse; parallel refreshes with the same token would force a spurious
    // sign-out. Requests with the stale token 401; the refreshed token succeeds.
    fetchMock.mockImplementation(async (_url: string, init: RequestInit) => {
      const auth = (init.headers as Record<string, string>)["Authorization"];
      return auth === "Bearer access-2"
        ? jsonResponse(200, { ok: true })
        : jsonResponse(401, { detail: "expired" });
    });
    const refresh = jest.fn(async () => {
      // Overlap window: both requests are parked on this single refresh.
      await new Promise((r) => setTimeout(r, 10));
      return "access-2";
    });
    const client = new HttpClient(makeProvider({ refresh }));
    const [a, b, c] = await Promise.all([
      client.get<{ ok: boolean }>("/v1/users/me"),
      client.get<{ ok: boolean }>("/v1/couples/current"),
      client.get<{ ok: boolean }>("/v1/birth-profiles/me"),
    ]);
    expect(a).toEqual({ ok: true });
    expect(b).toEqual({ ok: true });
    expect(c).toEqual({ ok: true });
    // One shared refresh for all three concurrent 401s — not three.
    expect(refresh).toHaveBeenCalledTimes(1);
    // Three initial 401s + three retries with the new token.
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("refreshes again for a later, non-overlapping 401 (in-flight promise resets)", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "u1" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "u2" }));
    const refresh = jest.fn(async () => "access-2");
    const client = new HttpClient(makeProvider({ refresh }));
    await client.get("/v1/users/me");
    await client.get("/v1/users/me");
    // Two separate (sequential) auth failures ⇒ two refreshes; the dedupe window
    // only collapses genuinely concurrent refreshes.
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("calls onAuthLost and rethrows when refresh fails on a 401", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "expired" }));
    const refresh = jest.fn(async () => null);
    const onAuthLost = jest.fn();
    const client = new HttpClient(makeProvider({ refresh, onAuthLost }));
    await expect(client.get("/v1/users/me")).rejects.toBeInstanceOf(ApiError);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(onAuthLost).toHaveBeenCalledTimes(1);
    // Only the original request was attempted (no retry without a new token).
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("maps a fetch rejection to a network ApiError", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("failed"));
    const client = new HttpClient(makeProvider());
    await expect(client.get("/v1/users/me")).rejects.toMatchObject({ kind: "network" });
  });

  it("never logs the bearer token", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    const client = new HttpClient(makeProvider());
    await client.get("/v1/users/me");
    const logged = logSpy.mock.calls.flat().join(" ");
    expect(logged).not.toContain("access-1");
  });
});
