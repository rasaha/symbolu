// The deployment request header (P3E §15). The private hosted profile serves the SPA
// and the API from one origin and refuses a mutating `/api` request without
// `X-Ugence-Request: GovernanceStudio`. The plain studio-api is served cross-origin
// and allowlists `Content-Type` alone, so the header must never reach it.
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEPLOYMENT_REQUEST_HEADER,
  DEPLOYMENT_REQUEST_VALUE,
  deploymentHeaders,
  explainPlan,
} from "@/api/client";
import { registerSystem, listRegistrations } from "@/api/client-v2";
import { apiBaseUrl } from "@/lib/config";

const apiOrigin = new URL(apiBaseUrl).origin;

describe("deploymentHeaders", () => {
  it("names the header the deployment middleware checks", () => {
    expect(DEPLOYMENT_REQUEST_HEADER).toBe("X-Ugence-Request");
    expect(DEPLOYMENT_REQUEST_VALUE).toBe("GovernanceStudio");
  });

  it("rides a mutating request to a same-origin API", () => {
    expect(deploymentHeaders("POST", "https://studio.example:8443", "https://studio.example:8443")).toEqual({
      "X-Ugence-Request": "GovernanceStudio",
    });
  });

  it("never rides a read", () => {
    for (const m of ["GET", "HEAD", "OPTIONS", undefined]) {
      expect(deploymentHeaders(m, "https://studio.example:8443", "https://studio.example:8443")).toEqual({});
    }
  });

  it("never rides a request to a cross-origin API", () => {
    expect(deploymentHeaders("POST", "https://studio-web.example", "https://studio-api.example")).toEqual({});
    expect(deploymentHeaders("POST", "https://studio.example", "https://studio.example:8443")).toEqual({});
    expect(deploymentHeaders("POST", undefined, "https://studio.example")).toEqual({});
  });
});

describe("the two clients", () => {
  const ok = (body: unknown) =>
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function sentHeaders(): Record<string, string>[] {
    const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls;
    return calls.map(([, init]) => init.headers as Record<string, string>);
  }

  it("send the header on POST and not on GET when the API is this page's origin", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => ok({ result: { available: true } }));
    vi.spyOn(globalThis, "location", "get").mockReturnValue({ origin: apiOrigin } as Location);
    await registerSystem({} as never).catch(() => undefined);
    await listRegistrations().catch(() => undefined);
    await explainPlan("procurement").catch(() => undefined);
    const [post, get, v1post] = sentHeaders();
    expect(post[DEPLOYMENT_REQUEST_HEADER]).toBe(DEPLOYMENT_REQUEST_VALUE);
    expect(post["Content-Type"]).toBe("application/json");
    expect(get[DEPLOYMENT_REQUEST_HEADER]).toBeUndefined();
    expect(v1post[DEPLOYMENT_REQUEST_HEADER]).toBe(DEPLOYMENT_REQUEST_VALUE);
  });

  it("send no header when the API is another origin", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => ok({ result: { available: true } }));
    vi.spyOn(globalThis, "location", "get").mockReturnValue({ origin: "https://studio-web.example" } as Location);
    await registerSystem({} as never).catch(() => undefined);
    await explainPlan("procurement").catch(() => undefined);
    for (const h of sentHeaders()) expect(h[DEPLOYMENT_REQUEST_HEADER]).toBeUndefined();
  });
});
