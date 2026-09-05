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
import { AuthApi, BirthProfileApi, ChatApi, CoupleApi, UserApi } from "@/api/endpoints";
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
    let conversationId = "";

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

    it("pairing provisioned exactly one shared conversation, invisible to outsiders", async () => {
      const convA = await ChatApi.current(A.client);
      const convB = await ChatApi.current(B.client);
      expect(convA.conversation_id).toBe(convB.conversation_id);
      expect(convA.couple_id).toBe(coupleId);
      expect(convA.status).toBe("ACTIVE");
      conversationId = convA.conversation_id;
      // Unrelated user C has no conversation and cannot read this one (404, not 403).
      const noConv = await expectApiError(ChatApi.current(C.client));
      expect(noConv.status).toBe(404);
      const foreign = await expectApiError(ChatApi.listMessages(C.client, conversationId));
      expect(foreign.status).toBe(404);
    });

    it("sends are idempotent on client_message_id; the partner sees them in order", async () => {
      const first = await ChatApi.sendMessage(A.client, conversationId, {
        client_message_id: "live-k1",
        body: "hello from A",
      });
      expect(first.server_sequence).toBeGreaterThan(0);
      // Replaying the SAME key (the timeout-retry path) returns the ORIGINAL
      // message — same id, same sequence — never a duplicate.
      const replay = await ChatApi.sendMessage(A.client, conversationId, {
        client_message_id: "live-k1",
        body: "hello from A",
      });
      expect(replay.message_id).toBe(first.message_id);
      expect(replay.server_sequence).toBe(first.server_sequence);

      await ChatApi.sendMessage(B.client, conversationId, { client_message_id: "live-k2", body: "hi back" });
      await ChatApi.sendMessage(A.client, conversationId, { client_message_id: "live-k3", body: "how are you" });

      // B pages the history forward with the server-minted cursor.
      const page1 = await ChatApi.listMessages(B.client, conversationId, null, 2);
      expect(page1.messages).toHaveLength(2);
      expect(page1.has_more).toBe(true);
      const page2 = await ChatApi.listMessages(B.client, conversationId, page1.next_cursor);
      expect(page2.has_more).toBe(false);
      const all = [...page1.messages, ...page2.messages];
      expect(all.map((m) => m.body)).toEqual(["hello from A", "hi back", "how are you"]);
      const sequences = all.map((m) => m.server_sequence);
      expect([...sequences].sort((x, y) => x - y)).toEqual(sequences); // ascending
    });

    it("read state advances forward-only", async () => {
      const conv = await ChatApi.current(B.client);
      const latest = conv.latest_sequence;
      expect(latest).toBeGreaterThanOrEqual(3);
      const rs = await ChatApi.updateReadState(B.client, conversationId, latest);
      expect(rs.last_read_sequence).toBe(latest);
      // A backward write is a no-op: the stored value never regresses.
      const back = await ChatApi.updateReadState(B.client, conversationId, 1);
      expect(back.last_read_sequence).toBe(latest);
      const after = await ChatApi.current(B.client);
      expect(after.last_read_sequence).toBe(latest);
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
      // The conversation is revoked in the same transaction: no read, no send.
      // A FORMER member is denied with 403 (membership revoked; pinned by the
      // backend's tests/security/test_chat_authz.py), while never-members and
      // "no current conversation" stay 404 (anti-enumeration).
      const conv = await expectApiError(ChatApi.current(A.client));
      expect(conv.status).toBe(404);
      const read = await expectApiError(ChatApi.listMessages(B.client, conversationId));
      expect(read.status).toBe(403);
      const send = await expectApiError(
        ChatApi.sendMessage(A.client, conversationId, { client_message_id: "live-k4", body: "too late" }),
      );
      expect(send.status).toBe(403);
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
