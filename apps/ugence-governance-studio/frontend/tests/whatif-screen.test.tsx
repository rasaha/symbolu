import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders } from "./testUtils";

afterEach(() => vi.unstubAllGlobals());

type Mock = ReturnType<typeof installFetchMock>;

async function lastWhatIfBody(fetchMock: Mock): Promise<{ operation: string; params: Record<string, unknown> }> {
  const call = [...fetchMock.mock.calls].reverse().find(([url]) => String(url).includes("/what-if"));
  if (!call) throw new Error("no what-if request captured");
  return JSON.parse(String((call[1] as RequestInit)?.body ?? "{}"));
}

const selectOp = async (user: ReturnType<typeof userEvent.setup>, op: string) => {
  await user.selectOptions(screen.getByLabelText("Perturbation (bounded)"), op);
};

describe("C2 — what-if screen posts the exact per-operation payload", () => {
  it("EXPIRE_EVIDENCE shows no parameter controls and posts empty params", async () => {
    const user = userEvent.setup();
    const fetchMock = installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "EXPIRE_EVIDENCE");
    expect(screen.queryByLabelText("cost ceiling")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    expect(await lastWhatIfBody(fetchMock)).toEqual({ operation: "EXPIRE_EVIDENCE", params: {} });
  });

  it("FORBID_PROVIDER posts { provider } from the pinned registry", async () => {
    const user = userEvent.setup();
    const fetchMock = installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "FORBID_PROVIDER");
    const provider = screen.getByLabelText("provider") as HTMLSelectElement;
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    const body = await lastWhatIfBody(fetchMock);
    expect(body.operation).toBe("FORBID_PROVIDER");
    expect(Object.keys(body.params)).toEqual(["provider"]);
    expect(body.params.provider).toBe(provider.value); // submitted value equals displayed selection
    expect(provider.value).not.toBe(""); // no silent empty default
  });

  it("TIGHTEN_PROVIDER_CONCENTRATION posts an integer limit_pct", async () => {
    const user = userEvent.setup();
    const fetchMock = installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "TIGHTEN_PROVIDER_CONCENTRATION");
    await user.type(screen.getByLabelText("limit %"), "40");
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    expect(await lastWhatIfBody(fetchMock)).toEqual({ operation: "TIGHTEN_PROVIDER_CONCENTRATION", params: { limit_pct: 40 } });
  });

  it("REMOVE_CANDIDATE splits the pinned agent ref into agent_id + agent_version", async () => {
    const user = userEvent.setup();
    const fetchMock = installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "REMOVE_CANDIDATE");
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    const body = await lastWhatIfBody(fetchMock);
    expect(body.operation).toBe("REMOVE_CANDIDATE");
    expect(Object.keys(body.params).sort()).toEqual(["agent_id", "agent_version"]);
    expect(String(body.params.agent_id)).not.toContain("@");
  });

  it("a numeric op cannot be applied while empty (Apply disabled, no silent default)", async () => {
    const user = userEvent.setup();
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "TIGHTEN_COST_CEILING");
    expect(screen.getByTestId("whatif-apply")).toBeDisabled();
    expect(screen.getByTestId("whatif-invalid")).toBeInTheDocument();
  });

  it("switching operations drops stale parameters", async () => {
    const user = userEvent.setup();
    const fetchMock = installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "TIGHTEN_COST_CEILING");
    await user.type(screen.getByLabelText("cost ceiling"), "5");
    await selectOp(user, "FORBID_PROVIDER"); // switch away
    expect(screen.queryByLabelText("cost ceiling")).not.toBeInTheDocument();
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    const body = await lastWhatIfBody(fetchMock);
    expect(body.operation).toBe("FORBID_PROVIDER");
    expect(body.params).not.toHaveProperty("ceiling"); // no stale param leaked
  });

  it("baseline is API-supplied and stable across two applies (immutable baseline)", async () => {
    const user = userEvent.setup();
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "FORBID_PROVIDER");
    await user.click(screen.getByTestId("whatif-apply"));
    const first = within(await screen.findByTestId("whatif-result")).getByText(/baseline/i).closest("div")!;
    const baselineText = first.textContent;
    // reset and apply a different operation; the baseline fingerprint must be unchanged
    await user.click(screen.getByTestId("whatif-reset"));
    await selectOp(user, "REQUIRE_RESIDENCY");
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    const second = within(screen.getByTestId("whatif-result")).getByText(/baseline/i).closest("div")!;
    expect(second.textContent).toBe(baselineText);
  });

  it("reset clears only the client-held what-if result", async () => {
    const user = userEvent.setup();
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    await selectOp(user, "FORBID_PROVIDER");
    await user.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    await user.click(screen.getByTestId("whatif-reset"));
    await waitFor(() => expect(screen.queryByTestId("whatif-result")).not.toBeInTheDocument());
    expect(screen.getByTestId("whatif-notice")).toBeInTheDocument(); // baseline view intact
  });
});
