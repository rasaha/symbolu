/**
 * LIVE integration test — the PRODUCTION mobile API client + typed endpoints
 * driven against a real DilChat FastAPI backend and PostgreSQL 16 database.
 *
 * This is NOT a fetch mock. It exercises real JWT issuance, rotating refresh
 * tokens with reuse detection, request/response schemas, application/problem+json
 * errors, invitation lifecycle, consent-gated pairing, RLS-backed privacy
 * isolation, and unpairing revocation.
 *
 * Orchestration (fresh migrated DB + `uvicorn`) is performed by
 * scripts/run-integration.sh, which sets DILCHAT_INTEGRATION_BASE_URL. If that
 * variable is unset or the server is unreachable, this test FAILS — it never
 * silently skips (an absent backend must not read as a pass).
 *
 * Only synthetic identities and birth data are used.
 */
import { HttpClient, type TokenProvider } from "@/api/client";
import { AuthApi, BirthProfileApi, CoupleApi, UserApi } from "@/api/endpoints";
import { ApiError } from "@/api/errors";
import type { BirthProfileCreateRequest, TokenResponse } from "@/api/types";

const BASE = process.env.DILCHAT_INTEGRATION_BASE_URL;
const RUN = process.env.DILCHAT_INTEGRATION_RUN_ID ?? "local";

/** An in-memory session backing a real HttpClient, standing in for secure storage. */
class Session implements TokenProvider {
  access: string | null = null;
  refreshToken: string | null = null;
  authLost = false;
  readonly client: HttpClient;
  private readonly bare: HttpClient;

  constructor(base: string) {
    this.bare = new HttpClient(
      { getAccessToken: async () => null, refresh: async () => null, onAuthLost: () => undefined },
      base,
    );
    this.client = new HttpClient(this, base);
  }
  getAccessToken = async (): Promise<string | null> => this.access;
  refresh = async (): Promise<string | null> => {
    if (!this.refreshToken) return null;
    try {
      const t = await AuthApi.refresh(this.bare, this.refreshToken);
      this.access = t.access_token;
      this.refreshToken = t.refresh_token;
      return this.access;
    } catch {
      return null;
    }
  };
  onAuthLost = (): void => {
    this.authLost = true;
    this.access = null;
    this.refreshToken = null;
  };
  adopt(t: TokenResponse): void {
    this.access = t.access_token;
    this.refreshToken = t.refresh_token;
  }
  /** Refresh through the bare client so we can observe raw rotation/reuse. */
  rawRefresh(token: string): Promise<TokenResponse> {
    return AuthApi.refresh(this.bare, token);
  }
}

const email = (who: string): string => `dilchat.int.${RUN}.${who}@example.test`;
const PASSWORD = "IntegvT3st-Passphrase";

async function expectApiError(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    if (e instanceof ApiError) return e;
    throw e;
  }
  throw new Error("expected the request to reject with an ApiError, but it resolved");
}

// Guard: without a live backend this whole file must fail, not skip.
if (!BASE) {
  describe("live backend integration", () => {
    it("requires DILCHAT_INTEGRATION_BASE_URL pointing at a running FastAPI backend", () => {
      throw new Error(
        "DILCHAT_INTEGRATION_BASE_URL is not set. Run via scripts/run-integration.sh, " +
          "which starts a fresh migrated PostgreSQL + FastAPI and sets this variable.",
      );
    });
  });
} else {
  const base = BASE;

  describe("live backend: onboarding → pairing → consent → privacy → unpair", () => {
    const A = new Session(base);
    const B = new Session(base);
    const C = new Session(base);
    let coupleId = "";

    it("reaches the backend health endpoint", async () => {
      const bare = new HttpClient(
        { getAccessToken: async () => null, refresh: async () => null, onAuthLost: () => undefined },
        base,
      );
      const health = await bare.get<{ status?: string }>("/v1/health");
      expect(health).toBeTruthy();
    });

    it("registers and authenticates three independent users", async () => {
      for (const [s, who] of [
        [A, "asha"],
        [B, "rohan"],
        [C, "chandni"],
      ] as const) {
        const reg = await AuthApi.register(s.client, { email: email(who), password: PASSWORD });
        expect(reg.email).toBe(email(who));
        const tok = await AuthApi.login(s.client, { email: email(who), password: PASSWORD });
        expect(tok.access_token).toBeTruthy();
        expect(tok.refresh_token).toBeTruthy();
        s.adopt(tok);
      }
      const me = await UserApi.me(A.client);
      expect(me.email).toBe(email("asha"));
    });

    it("each user owns a private birth profile; there is no route to read another's", async () => {
      const bodyA: BirthProfileCreateRequest = {
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
      const bodyB: BirthProfileCreateRequest = {
        preferred_name: "Rohan",
        birth_date: "1988-11-02",
        birth_time_precision: "APPROXIMATE",
        birth_time_local: "23:45",
        uncertainty_minutes: 30,
        birthplace_label: "Chennai",
        iana_timezone: "Asia/Kolkata",
        latitude: 13.08,
        longitude: 80.27,
      };
      const createdA = await BirthProfileApi.create(A.client, bodyA);
      expect(createdA.preferred_name).toBe("Asha");
      await BirthProfileApi.create(B.client, bodyB);

      const mineA = await BirthProfileApi.get(A.client);
      const mineB = await BirthProfileApi.get(B.client);
      // Each caller sees only their own private profile.
      expect(mineA.preferred_name).toBe("Asha");
      expect(mineB.preferred_name).toBe("Rohan");
      expect(mineA.id).not.toBe(mineB.id);

      // A user without a profile gets 404 (mapped to an empty state in the app),
      // never another person's data — there is no /birth-profiles/{id} route.
      const err = await expectApiError(BirthProfileApi.get(C.client));
      expect(err.status).toBe(404);
    });

    it("rejects self-acceptance and consumed tokens; pairs only on the partner's explicit accept", async () => {
      const inv = await CoupleApi.createInvitation(A.client);
      expect(inv.token).toBeTruthy();

      // Self-acceptance is refused by the backend (422 VALIDATION_ERROR).
      const selfErr = await expectApiError(CoupleApi.acceptInvitation(A.client, inv.token));
      expect(selfErr.status).toBe(422);
      expect(selfErr.code).toBe("VALIDATION_ERROR");

      // Partner B explicitly accepts (the consent gate lives client-side in the
      // app; the authenticated accept call IS the act of consent).
      const couple = await CoupleApi.acceptInvitation(B.client, inv.token);
      expect(couple.status).toBe("ACTIVE");
      expect(couple.members).toHaveLength(2);
      coupleId = couple.couple_id;

      // A consumed token cannot be reused by a third party (409 INVITATION_USED).
      const reuseErr = await expectApiError(CoupleApi.acceptInvitation(C.client, inv.token));
      expect(reuseErr.status).toBe(409);
      expect(["INVITATION_USED", "INVITATION_INVALID"]).toContain(reuseErr.code);
    });

    it("an invalid token is a 404 INVITATION_INVALID, not a leak", async () => {
      const err = await expectApiError(
        CoupleApi.acceptInvitation(C.client, "not-a-real-token-000000000000"),
      );
      expect(err.status).toBe(404);
      expect(err.code).toBe("INVITATION_INVALID");
    });

    it("both partners observe the pairing; an unrelated user cannot", async () => {
      const cur = await CoupleApi.current(A.client);
      const curB = await CoupleApi.current(B.client);
      expect(cur?.couple_id).toBe(coupleId);
      expect(curB?.couple_id).toBe(coupleId);
      // The paired payload carries no private birth fields — only slot metadata.
      for (const m of cur!.members) {
        expect(Object.keys(m).sort()).toEqual(["scope_slot", "status", "user_id"]);
      }
      // Unrelated user C sees no couple (404 → the app renders "no connection").
      const errC = await expectApiError(CoupleApi.current(C.client));
      expect(errC.status).toBe(404);
    });

    it("an already-paired user cannot open a new invitation (409 CONFLICT)", async () => {
      const err = await expectApiError(CoupleApi.createInvitation(A.client));
      expect(err.status).toBe(409);
      expect(err.code).toBe("CONFLICT");
    });

    it("unpairing immediately revokes shared access for both partners", async () => {
      await expect(CoupleApi.unpair(A.client, coupleId)).resolves.toBeUndefined();
      // Access is revoked at once — both sides now see no couple, and a stale
      // couple_id cannot restore it.
      const a = await expectApiError(CoupleApi.current(A.client));
      const b = await expectApiError(CoupleApi.current(B.client));
      expect(a.status).toBe(404);
      expect(b.status).toBe(404);
      const stale = await expectApiError(CoupleApi.unpair(B.client, coupleId));
      expect(stale.status).toBe(404);
    });

    it("refresh tokens rotate and reuse is detected (why the client single-flights refresh)", async () => {
      // Log C in fresh, capture its refresh token, then rotate once.
      const tok = await AuthApi.login(C.client, { email: email("chandni"), password: PASSWORD });
      const oldRefresh = tok.refresh_token;
      const rotated = await C.rawRefresh(oldRefresh);
      expect(rotated.refresh_token).not.toBe(oldRefresh);
      // Presenting the already-rotated token again triggers reuse detection (401).
      const reuse = await expectApiError(C.rawRefresh(oldRefresh));
      expect(reuse.status).toBe(401);
      expect(reuse.isAuthError).toBe(true);
    });
  });
}
