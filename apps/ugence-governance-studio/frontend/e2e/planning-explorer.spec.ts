import { test, expect, type Page } from "@playwright/test";

// P3D direct scenario E2E (§34) against the REAL local P3B backend, live frozen data.
const MATURITY = /no business-action authorization/i;

async function open(page: Page, id: string) {
  await page.goto(`/scenarios/${id}`);
  await expect(page.getByTestId("verification-state")).toBeVisible();
}
const nav = (page: Page, name: string) => page.getByRole("link", { name, exact: true }).click();

test("Procurement — full planning flow", async ({ page }) => {
  await open(page, "procurement");

  await nav(page, "Ranking");
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByRole("button", { name: /show breakdown/i }).first().click();
  await expect(page.getByText(/score decomposition/i)).toBeVisible();

  await nav(page, "Composition");
  await expect(page.getByText(/^Composition$/)).toBeVisible();
  await expect(page.getByTestId("non-greedy")).toBeVisible();

  await nav(page, "Permissions");
  await expect(page.getByTestId("proposal-notice")).toContainText(/do not grant/i);

  await nav(page, "Fallbacks");
  await expect(page.getByTestId("fallback-summary")).toBeVisible();

  await nav(page, "Replay");
  await expect(page.getByTestId("replay-result")).toContainText(/fingerprints match/i);

  await nav(page, "Comparison");
  await expect(page.getByTestId("plan-diff")).toBeVisible();

  await nav(page, "What-If");
  await page.getByTestId("whatif-apply").click();
  await expect(page.getByTestId("whatif-result")).toBeVisible();
  await expect(page.getByTestId("whatif-result")).toContainText(/COMPLETE|NO_FEASIBLE_TEAM|Complete|No feasible/i);
  await page.getByTestId("whatif-reset").click();
  await expect(page.getByTestId("whatif-result")).toHaveCount(0);

  await expect(page.getByText(MATURITY).first()).toBeVisible();
});

test("Customer Support — ranking, composition, permission, fallback, what-if", async ({ page }) => {
  await open(page, "customer_support");
  await nav(page, "Ranking");
  await expect(page.getByRole("table")).toBeVisible();
  await nav(page, "Composition");
  await expect(page.getByText(/^Composition$/)).toBeVisible();
  await nav(page, "Permissions");
  await expect(page.getByTestId("proposal-notice")).toBeVisible();
  await nav(page, "Fallbacks");
  await expect(page.getByTestId("fallback-summary")).toBeVisible();
  await nav(page, "What-If");
  await page.getByLabel("Perturbation (bounded)").selectOption("TIGHTEN_COST_CEILING");
  await page.getByLabel("ceiling").fill("0");
  await page.getByTestId("whatif-apply").click();
  await expect(page.getByTestId("whatif-result")).toBeVisible();
});

test("Cybersecurity Feasible — constrained team + evidence-expiry what-if", async ({ page }) => {
  await open(page, "cybersecurity_success");
  await nav(page, "Composition");
  await expect(page.getByText(/Complete/)).toBeVisible();
  await nav(page, "Fallbacks");
  await expect(page.getByTestId("fallback-summary")).toBeVisible();
  await nav(page, "What-If");
  await page.getByLabel("Perturbation (bounded)").selectOption("EXPIRE_EVIDENCE");
  await page.getByTestId("whatif-apply").click();
  await expect(page.getByTestId("whatif-result")).toBeVisible();
});

test("Cybersecurity No Feasible Team — honest NO_FEASIBLE_TEAM", async ({ page }) => {
  await open(page, "cybersecurity_no_feasible_team");
  await nav(page, "Composition");
  await expect(page.getByTestId("no-feasible-team")).toBeVisible();
  // no fabricated assignment table, no permission proposal for an unassigned role
  await expect(page.getByText(/selected primary/i)).toHaveCount(0);
  await nav(page, "Permissions");
  await expect(page.getByText(/no permission proposals/i)).toBeVisible();
  await nav(page, "What-If");
  await page.getByLabel("Perturbation (bounded)").selectOption("FORBID_PROVIDER");
  await page.getByTestId("whatif-apply").click();
  await expect(page.getByTestId("whatif-result")).toBeVisible();
});
