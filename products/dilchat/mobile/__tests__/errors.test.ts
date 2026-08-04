import { ApiError, httpErrorFromBody, userMessageFor } from "@/api/errors";

describe("httpErrorFromBody", () => {
  it("maps a 401 to an auth error", () => {
    const err = httpErrorFromBody(401, { detail: "expired" });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.isAuthError).toBe(true);
    expect(err.isValidationError).toBe(false);
    expect(err.status).toBe(401);
  });

  it("treats an AUTH_SESSION_REVOKED code as an auth error regardless of status", () => {
    const err = httpErrorFromBody(400, { code: "AUTH_SESSION_REVOKED" });
    expect(err.isAuthError).toBe(true);
  });

  it("maps a 422 to a validation error", () => {
    const err = httpErrorFromBody(422, { detail: "bad field" });
    expect(err.isValidationError).toBe(true);
    expect(err.isAuthError).toBe(false);
    expect(err.status).toBe(422);
  });

  it("prefers a problem+json detail as the message", () => {
    expect(httpErrorFromBody(400, { detail: "specific reason" }).message).toBe("specific reason");
    expect(httpErrorFromBody(400, { title: "a title" }).message).toBe("a title");
    expect(httpErrorFromBody(400, {}).message).toContain("400");
  });

  it("captures a machine-readable code", () => {
    expect(httpErrorFromBody(409, { code: "INVITATION_CONSUMED", detail: "used" }).code).toBe("INVITATION_CONSUMED");
  });
});

describe("userMessageFor", () => {
  it("returns an offline message for a network error", () => {
    expect(userMessageFor(new ApiError({ kind: "network", message: "x" }))).toMatch(/offline/i);
  });

  it("returns a timeout message for a timeout error", () => {
    expect(userMessageFor(new ApiError({ kind: "timeout", message: "x" }))).toMatch(/timed out/i);
  });

  it("returns a session-expired message for an auth error", () => {
    expect(userMessageFor(httpErrorFromBody(401, { detail: "nope" }))).toMatch(/session has expired/i);
  });

  it("passes through a non-auth http message", () => {
    expect(userMessageFor(httpErrorFromBody(409, { detail: "This invitation was already used." }))).toBe(
      "This invitation was already used.",
    );
  });

  it("returns a generic message for a non-ApiError value", () => {
    expect(userMessageFor(new Error("raw"))).toMatch(/something went wrong/i);
    expect(userMessageFor("weird")).toMatch(/something went wrong/i);
  });
});
