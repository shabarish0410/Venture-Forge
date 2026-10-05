import { test, expect } from "@playwright/test";

test("provider availability and extension attributes do not break sign-in hydration", async ({ page }) => {
  const hydrationErrors: string[] = [];
  page.on("console", message => { if (/hydrated|hydration|server rendered HTML/i.test(message.text())) hydrationErrors.push(message.text()); });
  page.on("pageerror", error => hydrationErrors.push(error.message));
  await page.addInitScript(() => {
    const decorate = () => {
      if (!document.documentElement) return false;
      document.documentElement.setAttribute("crxlauncher", "");
      document.documentElement.setAttribute("crxlauncher-bridged", "");
      return true;
    };
    if (!decorate()) {
      const observer = new MutationObserver(() => { if (decorate()) observer.disconnect(); });
      observer.observe(document, { childList: true, subtree: true });
    }
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome to the Forge." })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("crxlauncher", "");
  await expect(page.locator("html")).toHaveAttribute("crxlauncher-bridged", "");
  await expect(page.getByRole("button", { name: "Sign in with Google", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Sign in with GitHub", exact: true })).toBeDisabled();
  await page.screenshot({ path: ".local/sign-in-providers-desktop.png", fullPage: true, animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.screenshot({ path: ".local/sign-in-providers-mobile.png", fullPage: true, animations: "disabled" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(hydrationErrors).toEqual([]);
});

test("Google and GitHub buttons start the server flow and explain callback failures", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  await page.route("**/api/v1/auth/providers", route => route.fulfill({ json: { providers: [
    { id: "google", label: "Google", available: true, connected: false, email: null },
    { id: "github", label: "GitHub", available: true, connected: false, email: null },
  ] } }));
  const requests: { provider: string; mode: string }[] = [];
  await page.route("**/api/v1/auth/oauth/*/start", async route => {
    const provider = new URL(route.request().url()).pathname.split("/").at(-2)!;
    const body = route.request().postDataJSON();
    expect(body).toEqual({ mode: "sign_in" });
    requests.push({ provider, ...body });
    const error = provider === "google" ? "cancelled" : "account_exists";
    await route.fulfill({ json: { authorization_url: `http://127.0.0.1:3001/?auth_error=${error}` } });
  });
  await page.goto("/");
  await Promise.all([
    page.waitForURL("http://127.0.0.1:3001/?auth_error=cancelled", { waitUntil: "domcontentloaded" }),
    page.getByRole("button", { name: "Sign in with Google", exact: true }).click(),
  ]);
  await expect(page.getByRole("alert").filter({ hasText: "Sign-in was cancelled" })).toBeVisible();
  await expect(page).toHaveURL("http://127.0.0.1:3001/");
  await Promise.all([
    page.waitForURL("http://127.0.0.1:3001/?auth_error=account_exists", { waitUntil: "domcontentloaded" }),
    page.getByRole("button", { name: "Sign in with GitHub", exact: true }).click(),
  ]);
  await expect(page.getByRole("alert").filter({ hasText: "An account already uses this email" })).toBeVisible();
  await expect(page).toHaveURL("http://127.0.0.1:3001/");
  expect(requests).toEqual([{ provider: "google", mode: "sign_in" }, { provider: "github", mode: "sign_in" }]);
  expect(browserErrors).toEqual([]);
});
