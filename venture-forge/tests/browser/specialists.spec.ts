import { test, expect } from "@playwright/test";
test.use({ actionTimeout: 10000 });

test("all thirteen specialists produce reviewed handoffs in a connected pipeline", async ({ page }) => {
  test.setTimeout(180000);
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await page.getByLabel("Email address").fill("agents-browser@test.local");
  await page.getByRole("button", { name: "Continue with email", exact: true }).click();
  await page.getByLabel("Password", { exact: true }).fill("browser-test-only-password");
  await page.getByRole("button", { name: "Enter your workspace" }).click();
  await expect(page.getByRole("heading", { name: "Create your Venture Passport" })).toBeVisible();
  const origin = "http://127.0.0.1:3001";
  const created = await page.request.post("/api/v1/ventures", { headers: { Origin: origin, "Idempotency-Key": "specialist-browser-venture" }, data: { name: "Specialist Fieldnotes", idea: "Help founders test a dated pilot offer with real customer evidence.", customer_segment: "Independent founders", geography: "India", first_hypothesis: "Founders will commit to a dated pilot offer." } });
  expect(created.status()).toBe(201); let p = await created.json();
  const evidence = await page.request.post(`/api/v1/ventures/${p.venture.id}/evidence`, { headers: { Origin: origin, "Idempotency-Key": "specialist-browser-source" }, data: { expected_revision: p.venture.revision, hypothesis_id: p.hypotheses[0].id, title: "Seed customer observation", kind: "interview", participant_code: "P01", content: "The participant described a manual workflow and declined an immediate purchase.", locator: "Test-only note at 14:22", consent: "notes_only", collected_on: new Date().toISOString().slice(0, 10), relation: "contradicts", limitations: "One interview; no confirmed purchase." } });
  expect(evidence.status()).toBe(201); p = await evidence.json(); const source = p.evidence[0].id;
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Agent Pipelines", exact: true }).click();
  await page.getByLabel("Pipeline", { exact: true }).selectOption("complete");
  await page.getByLabel("Pipeline objective", { exact: true }).fill("Review the thirteen specialists and preserve the contrary customer finding.");
  await page.getByRole("button", { name: "Create connected pipeline" }).click();
  const catalog = await (await page.request.get("/api/v1/agents")).json();
  expect(catalog.model.default_mode).toBe("AUTO");
  expect(catalog.agents.every((a: { model_requirements: { reasoning: string } }) => a.model_requirements.reasoning)).toBe(true);
  const template = catalog.templates.find((t: { id: string }) => t.id === "complete");
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const params: Record<string, Record<string, unknown>> = {
    market: { total_accounts: 1000, serviceable_accounts: 500, reachable_accounts: 80, capacity: 20, price: "100", unit: "Founder accounts" },
    competitor: { alternatives: [{ name: "Manual workflow", kind: "status_quo", source_id: source }] },
    finance: { price: "100.000000000000001", volume: 10, direct_cost: "400", fixed_cost: "300", collected_cash: "800", cash_balance: "2000", acquisition_spend: "500", new_customers: 5, average_revenue_per_customer: "100", customer_lifetime_periods: "12" },
    experiment: { intervention: "Invite ten founders to a dated pilot meeting.", metric: "Dated commitment", threshold_percent: "30", minimum_n: 10, end_date: tomorrow, stop_rule: "Stop at ten observations" },
    ecosystem: { opportunities: [{ name: "Test-only programme", official_url: "https://example.org/programme", source_id: source, last_checked: new Date().toISOString().slice(0, 10), closes_on: tomorrow, geography: "India", eligibility: "unknown" }] },
  };
  for (const stage of template.stages) {
    const spec = catalog.agents.find((a: { id: string }) => a.id === stage.agent_id);
    const button = page.locator(".pipeline-stage").filter({ has: page.getByText(spec.name, { exact: true }) });
    await expect(button).toContainText("READY"); await button.click();
    const console = page.getByRole("region", { name: `${spec.name} specialist` });
    if (stage.agent_id === "home") {
      await console.getByText("Hybrid routing, privacy and execution limits", { exact: true }).click();
      await expect(console.getByLabel("Execution mode", { exact: true })).toHaveValue("AUTO");
      await expect(console.getByLabel("Processing policy", { exact: true })).toHaveValue("cloud_allowed");
      await console.getByLabel("Processing policy", { exact: true }).selectOption("local_only");
      await expect(console.getByLabel("Model profile", { exact: true })).toHaveValue("");
      await expect(console.getByText("No model profiles are ready.", { exact: false })).toBeVisible();
    }
    for (const [key, value] of Object.entries(params[stage.agent_id] || {})) {
      if (Array.isArray(value)) {
        for (const item of value) {
          await console.getByRole("button", { name: key === "alternatives" ? "Add alternative" : "Add opportunity" }).click();
          for (const [property, v] of Object.entries(item)) {
            const field = console.locator(`[name^="parameter:${key}:"][name$=":${property}"]`).last();
            if (["source_id", "kind", "eligibility"].includes(property)) await field.selectOption(String(v));
            else await field.fill(String(v));
          }
        }
      } else await console.locator(`[name="parameter:${key}"]`).fill(String(value));
    }
    await console.getByText("Choose scoped evidence and accepted inputs", { exact: true }).click();
    await console.locator(".agent-check").filter({ hasText: "Seed customer observation" }).getByRole("checkbox").check();
    const financialRequest = stage.agent_id === "finance" ? page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/agent-runs")) : null;
    await console.getByRole("button", { name: `Run ${spec.name}`, exact: true }).click();
    if (financialRequest) {
      const body = (await financialRequest).postDataJSON();
      expect(body.parameters.price).toBe("100.000000000000001");
      expect(body.parameters.acquisition_spend).toBe("500");
      expect(body.parameters.new_customers).toBe(5);
    }
    await expect(console.getByRole("button", { name: "Record specialist review" })).toBeVisible({ timeout: 20000 });
    expect(await console.getByRole("button", { name: "Record specialist review" }).count()).toBe(1);
    await console.getByLabel("Review rationale").fill("Accept the bounded proposal and investigate its named unknowns before claiming validation.");
    await console.getByRole("button", { name: "Record specialist review" }).click();
    await expect(button).toContainText("ACCEPTED");
    await expect(console.getByRole("button", { name: "Record specialist review" })).toHaveCount(0);
  }
  await expect(page.getByText("COMPLETED · 13/13", { exact: true })).toBeVisible();
  const saved = await (await page.request.get(`/api/v1/ventures/${p.venture.id}/passport`)).json();
  expect(saved.agent_runs.filter((r: { status: string }) => r.status === "ACCEPTED")).toHaveLength(13);
  expect(saved.completed_cycles).toBe(0);
  expect(saved.handoffs.length).toBeGreaterThan(13);
  const financials = saved.agent_runs.find((r: { agent_id: string }) => r.agent_id === "finance").result.data.financials;
  expect(financials.cac_inr).toBe("100.00");
  expect(financials.ltv_revenue_inr).toBe("1200.00");
  expect(financials.ltv_gross_profit_inr).toBe("720.00");
  expect(saved.agent_runs.every((r: { result: { mode: string }; trace: { route?: { reason: string } }[] }) => r.result.mode === "RULE" && r.trace[0].route?.reason === "NO_MODEL_CONFIGURED")).toBe(true);
  await page.screenshot({ path: ".local/specialist-pipeline-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: ".local/specialist-pipeline-mobile.png", fullPage: true });
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Agent Pipelines", exact: true }).click();
  await expect(page.getByText("COMPLETED · 13/13", { exact: true })).toBeVisible();
  // Public catalog fixture verifies configured controls without enabling a paid request.
  await page.route("**/api/v1/agents", async route => {
    const response = await route.fetch(); const body = await response.json();
    body.model.configured = true;
    body.model.profiles = [
      { name: "cloud-reasoning", provider: "anthropic", model_id: "test-cloud-model", ready: true, location: "cloud", reasoning: "high", context_tokens: 128000, structured_outputs: true, tool_calling: true },
      { name: "private-local", provider: "ollama", model_id: "test-local-model", ready: true, location: "local", reasoning: "high", context_tokens: 128000, structured_outputs: true, tool_calling: true },
    ];
    await route.fulfill({ response, json: body });
  });
  await page.getByRole("navigation").getByRole("button", { name: "Research Desk", exact: true }).click();
  await page.getByText("Run the Research Desk specialist", { exact: true }).click();
  const configured = page.getByRole("region", { name: "EvidenceScout specialist" });
  await expect(configured.getByLabel("Execution mode", { exact: true })).toHaveValue("AUTO");
  const consent = configured.locator('[name="model-consent"]');
  await expect(consent).toBeVisible(); await expect(consent).not.toBeChecked();
  await expect(consent).toHaveAttribute("required", "");
  await configured.getByLabel("Model profile", { exact: true }).selectOption("cloud-reasoning");
  await configured.getByLabel("Processing policy", { exact: true }).selectOption("local_only");
  await expect(configured.getByLabel("Model profile", { exact: true })).toHaveValue("");
  await expect(configured.getByLabel("Model profile", { exact: true }).locator('option[value="cloud-reasoning"]')).toHaveCount(0);
  await configured.getByLabel("Model profile", { exact: true }).selectOption("private-local");
  await expect(configured.getByText("Allow this run’s scoped context to be processed by configured local models only.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: ".local/hybrid-router-mobile.png", fullPage: true });
  await configured.getByLabel("Execution mode", { exact: true }).selectOption("RULE");
  await expect(configured.locator('[name="model-consent"]')).toHaveCount(0);
  expect(errors).toEqual([]);
});
