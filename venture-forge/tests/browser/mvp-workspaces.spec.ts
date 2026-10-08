import { test, expect, type Locator } from "@playwright/test";
test.use({ actionTimeout: 10000 });

async function fields(root: Locator, prefix: string, values: Record<string, unknown>) {
  for (const [key, value] of Object.entries(values)) {
    if (Array.isArray(value)) {
      const group = root.getByRole("group", { name: key.replaceAll("_", " "), exact: true });
      for (const item of value) {
        await group.getByRole("button", { name: /^Add / }).last().click();
        const record = group.locator(":scope > .mvp-record").last();
        await fields(record, `${prefix}:${key}:`, item);
      }
    } else if (value && typeof value === "object") {
      await fields(root, `${prefix}:${key}`, value as Record<string, unknown>);
    } else {
      const field = prefix.endsWith(":") ? root.locator(`[name^="${prefix}"][name$=":${key}"]`) : root.locator(`[name="${prefix}:${key}"]`);
      if (await field.evaluate(e => e.tagName === "SELECT")) await field.selectOption(String(value));
      else await field.fill(String(value));
    }
  }
}

test("priority MVP forms persist six reviewed workspaces, import finance drivers and export", async ({ page }) => {
  test.setTimeout(240000);
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Email address").fill("mvp-browser@test.local");
  await page.getByRole("button", { name: "Continue with email", exact: true }).click();
  await page.getByLabel("Password", { exact: true }).fill("browser-test-only-password");
  await page.getByRole("button", { name: "Enter your workspace" }).click();
  await expect(page.getByRole("heading", { name: "Create your Venture Passport" })).toBeVisible();
  const headers = { Origin: "http://127.0.0.1:3001", "Idempotency-Key": "mvp-browser-venture" };
  const created = await page.request.post("/api/v1/ventures", { headers, data: { name: "MVP Review", idea: "Help founders test a useful service before building a product.", customer_segment: "Independent founders", geography: "India", first_hypothesis: "Founders will pay for a pilot that saves time." } });
  expect(created.status()).toBe(201); let p = await created.json(); const base = `/api/v1/ventures/${p.venture.id}`;
  await page.reload();
  const nav = page.getByRole("navigation");
  await nav.getByRole("button", { name: "Research Desk", exact: true }).click();
  const passage = "The service costs INR 100 per founder each month.";
  await page.getByLabel("Read a local PDF or text file").setInputFiles({ name: "pricing.txt", mimeType: "text/plain", buffer: Buffer.from(passage) });
  await expect(page.getByLabel("Exact selected passage")).toHaveValue(passage);
  await page.getByLabel("Source limitations", { exact: true }).fill("Synthetic source for an isolated application test.");
  await page.locator('.mvp-reader select[name="consent"]').selectOption("public_source");
  await page.getByRole("button", { name: "Register selected passage", exact: true }).click();
  await expect(page.getByLabel("Exact selected passage")).toHaveCount(0);
  p = await (await page.request.get(base + "/passport")).json(); const source = p.evidence[0].id;
  const observed = await page.request.post(base + "/evidence", { headers: { ...headers, "Idempotency-Key": "mvp-interview" }, data: { expected_revision: p.venture.revision, hypothesis_id: p.hypotheses[0].id, title: "Consented test interview", kind: "interview", participant_code: "P01", content: "I copied the same records twice last Monday.", locator: "Synthetic interview note", consent: "quote_permitted", collected_on: new Date().toISOString().slice(0, 10), relation: "contextualizes", limitations: "One synthetic observation, not real validation." } });
  expect(observed.status()).toBe(201); p = await observed.json(); const interview = p.evidence.at(-1).id;
  await page.reload();
  const workflow = [
    { id: "home", nav: "Mentor Home", specialist: "ForgeGuide", values: { workspace: { payer: "Founder", unknowns: [{ question: "Will a founder pay?", impact: 5, uncertainty: 4 }], tasks: [{ action: "Interview one founder", completion_evidence: "Consented notes", source_id: interview }] } }, report: "Prioritized unknowns" },
    { id: "research", nav: "Research Desk", specialist: "EvidenceScout", values: { workspace: { scope: "Original public price", claims: [{ statement: passage, source_id: source, quote: passage }] } }, report: "Claim ledger" },
    { id: "market", nav: "Market Lab", specialist: "MarketMapper", values: { total_accounts: 1000, serviceable_accounts: 500, reachable_accounts: 80, capacity: 20, price: "100", unit: "Founder accounts", workspace: { inclusions: "Independent founder accounts", exclusions: "Inactive ventures", segments: [{ name: "Local founders", criteria: "Active local venture" }], selected_segment: "Local founders", selection_reason: "Reachable for direct tests" } }, report: "Beachhead decision" },
    { id: "customer", nav: "Customer Lab", specialist: "CustomerListener", values: { workspace: { observations: [{ theme: "Repeated copying", source_id: interview, quote: "I copied the same records twice", role: "buyer" }], decision_choice: "continue", decision_reason: "Test whether saving time leads to paid use" } }, report: "Theme synthesis" },
    { id: "competitor", nav: "Competitor Room", specialist: "RivalRadar", values: { alternatives: [{ name: "Existing service", kind: "direct", price_inr: "100", source_id: source }], workspace: { profiles: [{ alternative: "Existing service", source_id: source, quote: passage, price_period: "month", price_unit: "founder account" }] } }, report: "Competitor and substitute comparison" },
    { id: "model", nav: "Model Studio", specialist: "ModelArchitect", values: { workspace: { options: [{ name: "Subscription", relationship: "b2b", operating: "direct_service", delivery: "saas", pricing: "subscription", price_inr: "100", units_per_period: 10 }, { name: "Manual service", relationship: "b2b", operating: "direct_service", delivery: "managed_service", pricing: "one_time" }], selected_option: "Subscription", decision_reason: "Test recurring time saving", pricing_behavior: "Paid dated pilot", pricing_threshold: "Three of ten participants", canvas: [{ block: "customer_segments", value: "Independent founders" }] } }, report: "Three-option comparison" },
  ];
  const catalog = await (await page.request.get("/api/v1/agents")).json();
  for (const step of workflow) {
    await nav.getByRole("button", { name: step.nav, exact: true }).click();
    const toggle = page.getByText(`Run the ${step.nav} specialist`, { exact: true });
    if (await toggle.locator("..").getAttribute("open") === null) await toggle.click();
    const spec = catalog.agents.find((a: { id: string }) => a.id === step.id);
    const panel = page.getByRole("region", { name: `${spec.name} specialist`, exact: true });
    await panel.getByLabel("Specialist objective", { exact: true }).fill(`Review the ${step.id} MVP decision with explicit assumptions.`);
    await fields(panel, "parameter", step.values);
    await panel.getByRole("button", { name: `Run ${spec.name}`, exact: true }).click();
    await expect(panel.getByRole("button", { name: "Record specialist review" })).toBeVisible({ timeout: 20000 });
    await expect(panel.getByRole("heading", { name: step.report, exact: true })).toBeVisible();
    await panel.getByLabel("Review rationale", { exact: true }).fill("Accept this bounded test proposal while preserving its stated unknowns.");
    await panel.getByRole("button", { name: "Record specialist review" }).click();
    await expect(panel.locator(".agent-result .status")).toHaveText("ACCEPTED");
  }
  await nav.getByRole("button", { name: "Finance Lab", exact: true }).click();
  const financeToggle = page.getByText("Run the Finance Lab specialist", { exact: true });
  if (await financeToggle.locator("..").getAttribute("open") === null) await financeToggle.click();
  await page.getByText("Import reviewed Model Studio drivers", { exact: true }).click();
  await page.getByRole("button", { name: "Use drivers from Subscription", exact: true }).click();
  const finance = page.getByRole("region", { name: "FinancePilot specialist", exact: true });
  await expect(finance.locator('[name="parameter:price"]')).toHaveValue("100");
  await expect(finance.locator('[name="parameter:volume"]')).toHaveValue("10");
  await nav.getByRole("button", { name: "Model Studio", exact: true }).click();
  await page.getByText("Export selected accepted versions", { exact: true }).click();
  const exportPanel = page.locator("section.card").filter({ has: page.getByRole("heading", { name: "Preview and export reviewed work", exact: true }) });
  await exportPanel.getByLabel("Export purpose", { exact: true }).fill("Review the selected business model");
  await exportPanel.locator("label").filter({ hasText: "Review the model MVP decision" }).getByRole("checkbox").check();
  await exportPanel.getByRole("button", { name: "Preview selected export" }).click();
  await expect(exportPanel.getByRole("heading", { name: "Exact export preview" })).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await exportPanel.getByRole("button", { name: "Approve and download PDF" }).click();
  expect((await downloaded).suggestedFilename()).toBe("venture-forge.pdf");
  await page.screenshot({ path: ".local/mvp-model-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: ".local/mvp-model-mobile.png" });
  await page.reload();
  p = await (await page.request.get(base + "/passport")).json();
  expect(p.agent_runs.filter((r: { status: string }) => r.status === "ACCEPTED")).toHaveLength(6);
  expect(errors).toEqual([]);
});
