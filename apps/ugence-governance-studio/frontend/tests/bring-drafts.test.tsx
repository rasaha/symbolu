// Bring Your Workflow phase 3A (ADR §24, BW-3A): the one thing the screen may keep.
//
// The draft form sends the gated document, its declared version and the client's
// digest to the one draft write of the v2 contract and nothing else; the answer is
// shown as the server gave it — lifecycle DRAFT, the claimed owner PRESENTED_UNPROVEN,
// conferring nothing; a typed refusal is a refusal and a gap is a gap; the list is read
// on request, never on load; and loading a kept draft puts the server's canonical
// document back through the gate with its lineage pre-filled. Nothing here approves,
// compiles, publishes or exports, and the source still opens no connection of its own.
import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { App } from "@/app/App";
import { CLAIMED_OWNER_ASSURANCE, DISCLAIMER } from "@/features/bring/BringYourWorkflowScreen";
import exampleV1 from "@/features/bring/example-workflow-ir.v1.json";
import savedFixture from "./fixtures/bring.draft-saved.json";
import readFixture from "./fixtures/bring.draft-read.json";
import listFixture from "./fixtures/bring.drafts-list.json";
import listAllFixture from "./fixtures/bring.drafts-list-all.json";
import validateFixture from "./fixtures/bring.validate.json";
import { installFetchMock, renderWithProviders } from "./testUtils";

const ROUTE = "/bring-your-workflow";
const FRONTEND = path.resolve(__dirname, "..");
type Mock = ReturnType<typeof installFetchMock>;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function apiCalls(fetchMock: Mock) {
  return fetchMock.mock.calls.map(([url, init]) => `${(init as RequestInit)?.method ?? "GET"} ${String(url).replace(/^https?:\/\/[^/]+/, "")}`).filter((c) => c.includes("/api/"));
}

function lastBody(fetchMock: Mock, suffix: string): Record<string, unknown> {
  const call = [...fetchMock.mock.calls].reverse().find(([url]) => String(url).endsWith(suffix));
  if (!call) throw new Error(`no request to ${suffix}`);
  return JSON.parse(String((call[1] as RequestInit)?.body ?? "{}"));
}

async function loadExample(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByTestId("bring-load-example"));
  await screen.findByTestId("bring-summary");
  await screen.findByTestId("bring-draft");
}

describe("BW-3A — keeping a validated document as a draft", () => {
  it("states the amended disclaimer, names the claimed owner's assurance, and offers no draft control before a document", async () => {
    installFetchMock();
    renderWithProviders(<App />, ROUTE);
    await screen.findByRole("heading", { name: "Bring Your Workflow" });
    expect(DISCLAIMER).toContain("unapproved DRAFT");
    expect(DISCLAIMER).toContain("does not execute, compile, approve or publish");
    expect(CLAIMED_OWNER_ASSURANCE).toBe("PRESENTED_UNPROVEN");
    expect(screen.queryByTestId("bring-draft")).not.toBeInTheDocument();
    expect(screen.getByTestId("bring-drafts")).toBeInTheDocument();
  });

  it("sends exactly the gated document, its version, the client digest and the typed fields, and shows the server's record", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await loadExample(user);
    expect(screen.getByTestId("bring-draft-save")).toBeDisabled();
    await user.type(screen.getByTestId("bring-draft-title"), "Procurement intake");
    await user.type(screen.getByTestId("bring-draft-owner"), "directory://people/owner-1");
    await user.type(screen.getByTestId("bring-draft-notes"), "guided example");
    // the digest is computed asynchronously in the browser; wait for it so the body carries it
    await waitFor(() => expect(screen.getByTestId("bring-summary")).toHaveTextContent(validateFixture.integrity.computed_digest.slice(7, 15)));
    await user.click(screen.getByTestId("bring-draft-save"));
    const saved = await screen.findByTestId("bring-draft-saved");
    const body = lastBody(fetchMock, "/api/v2/workflow-drafts");
    expect(Object.keys(body).sort()).toEqual(["claimed_owner_ref", "contract_version", "notes", "registration_digest", "registration_ref", "source_digest", "supersedes", "title", "workflow"]);
    expect(body.workflow).toEqual(exampleV1);
    expect(body.contract_version).toBe("workflow_ir.v1");
    expect(body.title).toBe("Procurement intake");
    expect(body.claimed_owner_ref).toBe("directory://people/owner-1");
    expect(body.source_digest).toBe(validateFixture.integrity.computed_digest);
    // never sent from the browser: the tenant, the id, the lifecycle, the recorder
    for (const never of ["tenant_id", "draft_id", "lifecycle", "recorded_by", "claimed_owner_assurance"]) expect(body).not.toHaveProperty(never);
    expect(within(saved).getByTestId("bring-draft-id")).toHaveTextContent(savedFixture.draft_id);
    expect(within(saved).getByTestId("bring-draft-lifecycle")).toHaveTextContent("DRAFT");
    expect(within(saved).getByTestId("bring-draft-owner-status")).toHaveTextContent("PRESENTED_UNPROVEN");
    expect(within(saved).getByTestId("bring-draft-confers")).toHaveTextContent(/^nothing/);
    expect(saved).toHaveTextContent("client and server agree");
    expect(apiCalls(fetchMock).filter((c) => c.includes("/api/v2/"))).toEqual(["POST /api/v2/workflow-drafts"]);
  });

  it("a typed refusal is shown as a refusal and a missing drafts file as a gap, never as success", async () => {
    installFetchMock({ draftDuplicate: true });
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await loadExample(user);
    await user.type(screen.getByTestId("bring-draft-title"), "Procurement intake");
    await user.click(screen.getByTestId("bring-draft-save"));
    expect(await screen.findByTestId("bring-draft-refusal")).toHaveTextContent("draft_duplicate");
    expect(screen.queryByTestId("bring-draft-saved")).not.toBeInTheDocument();
    vi.unstubAllGlobals();
    installFetchMock({ draftsGap: true });
    await user.click(screen.getByTestId("bring-draft-save"));
    expect(await screen.findByTestId("bring-draft-gap")).toHaveTextContent("workflow_drafts");
  });

  it("editing the document clears the draft answer like every other result", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await loadExample(user);
    await user.type(screen.getByTestId("bring-draft-title"), "Procurement intake");
    await user.click(screen.getByTestId("bring-draft-save"));
    await screen.findByTestId("bring-draft-saved");
    await user.click(screen.getByTestId("bring-clear"));
    expect(screen.queryByTestId("bring-draft-saved")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bring-draft")).not.toBeInTheDocument();
  });
});

describe("BW-3A — the drafts a deployment keeps", () => {
  it("lists on request and never on load, heads only unless asked, and loads a kept draft back through the gate with its lineage", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await screen.findByTestId("bring-drafts-show");
    expect(apiCalls(fetchMock).filter((c) => c.includes("/api/v2/"))).toEqual([]);
    await user.click(screen.getByTestId("bring-drafts-show"));
    const list = await screen.findByTestId("bring-drafts-list");
    expect(within(list).getByTestId("bring-drafts-count")).toHaveTextContent(String(listFixture.count));
    expect(within(list).getAllByTestId("bring-drafts-row")).toHaveLength(listFixture.result.length);
    expect(list).toHaveTextContent("PRESENTED_UNPROVEN");
    await user.click(screen.getByTestId("bring-drafts-all"));
    await user.click(screen.getByTestId("bring-drafts-show"));
    await waitFor(() => expect(screen.getByTestId("bring-drafts-count")).toHaveTextContent(String(listAllFixture.count)));
    expect(screen.getAllByTestId("bring-drafts-row")).toHaveLength(listAllFixture.result.length);
    // by the id cell, not by text: the superseded row names this id as its successor too
    const head = screen.getAllByTestId("bring-drafts-row").find((row) => row.querySelectorAll("td")[1]?.textContent === readFixture.draft_id);
    if (!head) throw new Error("the head revision is not listed");
    await user.click(within(head).getByTestId("bring-drafts-load"));
    await screen.findByTestId("bring-draft-loaded");
    // the kept document went through the gate like anything pasted
    expect(within(screen.getByTestId("bring-summary")).getByTestId("bring-node-count")).toHaveTextContent("9");
    expect(screen.getByTestId("bring-draft-title")).toHaveValue(readFixture.record.draft.title);
    expect(screen.getByTestId("bring-draft-supersedes")).toHaveValue(readFixture.draft_id);
    expect(apiCalls(fetchMock).filter((c) => c.includes("/api/v2/"))).toEqual([
      "GET /api/v2/workflow-drafts",
      "GET /api/v2/workflow-drafts?include_superseded=true",
      `GET /api/v2/workflow-drafts/${readFixture.draft_id}`,
    ]);
  });

  it("has no serious axe violations with the draft form and the list shown", async () => {
    installFetchMock();
    const user = userEvent.setup();
    const { container } = renderWithProviders(<App />, ROUTE);
    await loadExample(user);
    await user.click(screen.getByTestId("bring-drafts-show"));
    await screen.findByTestId("bring-drafts-list");
    expect(await axe(container, { rules: { "color-contrast": { enabled: false } } })).toHaveNoViolations();
  });

  it("the screen's source offers no approve, compile, publish, export or submit control and reaches the v2 surface only through the approved client", () => {
    const text = readFileSync(path.join(FRONTEND, "src", "features", "bring", "BringYourWorkflowScreen.tsx"), "utf-8");
    for (const banned of ["/api/v2/", "fetch(", "localStorage", "sessionStorage"]) expect(text).not.toContain(banned);
    for (const control of ["Approve", "Compile", "Publish", "Export to", "Submit for approval", "Activate"]) {
      expect(text, `control ${control}`).not.toMatch(new RegExp(`>\\s*${control}`));
    }
    expect(text).toContain('from "@/api/client-v2"');
    const manifest = JSON.parse(readFileSync(path.join(FRONTEND, "security", "approved-v2-api-operations.json"), "utf-8"));
    for (const id of ["v2_workflow_drafts_save", "v2_workflow_drafts_list", "v2_workflow_drafts_read"]) expect(manifest.approved_operation_ids).toContain(id);
  });
});
