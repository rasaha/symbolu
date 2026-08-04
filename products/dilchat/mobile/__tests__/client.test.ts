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
