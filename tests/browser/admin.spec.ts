import { expect, test } from "@playwright/test";

/**
 * Increment A: sign-in, permission-aware navigation, user administration, the
 * role editor, company settings and the audit trail, exercised through the
 * browser against the running application.
 */

// Credentials come from the environment. No password literal is committed, even
// a development one: a password in a repository has a way of ending up in a
// deployment.
const ADMIN_EMAIL = process.env.ZTECH_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.ZTECH_ADMIN_PASSWORD;
if (!ADMIN_PASSWORD) {
  throw new Error(
    "Set ZTECH_ADMIN_PASSWORD to the administrator password of the environment under test. " +
      "See docs/testing.md.",
  );
}
const SHOTS = "../../docs/evidence/screenshots";
const ORIGINAL_TRADE_NAME = process.env.ZTECH_TRADE_NAME ?? "Demo Trading";

type Page = import("@playwright/test").Page;

/**
 * Submit the sign-in form and wait for the server's answer.
 *
 * Waiting for the response matters: clicking returns as soon as the event is
 * dispatched, so a test that navigates straight afterwards would race the
 * in-flight login and land back on the sign-in screen with no session.
 */
async function submitSignIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  const response = page.waitForResponse((r) => r.url().includes("/api/auth/login/"));
  await page.getByRole("button", { name: "Sign in" }).click();
  return response;
}

/** Sign in and wait until the signed-in shell has actually rendered. */
async function signIn(page: Page, email: string, password: string) {
  const response = await submitSignIn(page, email, password);
  expect(response.status(), "sign-in should succeed").toBe(200);
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
}

/** Sign out and wait until the sign-in screen is back. */
async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
}

test("the sign-in screen refuses the wrong password without saying whether the account exists", async ({
  page,
}) => {
  await submitSignIn(page, ADMIN_EMAIL, "definitely-not-the-password");
  const withWrongPassword = await page.getByRole("alert").innerText();

  await page.reload();
  await submitSignIn(page, "nobody@nowhere.invalid", "definitely-not-the-password");
  const withUnknownAccount = await page.getByRole("alert").innerText();

  expect(withWrongPassword).toContain("not correct");
  expect(withUnknownAccount).toBe(withWrongPassword);
  await page.screenshot({ path: `${SHOTS}/01-sign-in-refused.png`, fullPage: true });
});

test("an administrator signs in and reaches every administration screen", async ({ page }) => {
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);

  await expect(page.getByRole("heading", { level: 1 })).toContainText("Welcome");
  await expect(page.getByRole("navigation", { name: "Main" })).toContainText("OMR");
  await expect(page.getByRole("navigation", { name: "Main" })).toContainText("Asia/Muscat");
  await page.screenshot({ path: `${SHOTS}/02-overview.png`, fullPage: true });

  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/03-users.png`, fullPage: true });

  await page.getByRole("link", { name: "Roles" }).click();
  await expect(page.getByRole("heading", { name: "Roles" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "System Administrator" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/04-roles.png`, fullPage: true });

  await page.getByRole("link", { name: "Company" }).click();
  await expect(page.getByRole("heading", { name: "Company" })).toBeVisible();
  // The Omani rial carries three decimal places; this is shown, not assumed.
  await expect(page.getByText("3 decimal places")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/05-company.png`, fullPage: true });

  await page.getByRole("link", { name: "Audit trail" }).click();
  await expect(page.getByRole("heading", { name: "Audit trail" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/06-audit.png`, fullPage: true });
});

test("creating a user writes a real record and an audit entry", async ({ page }) => {
  const stamp = Date.now();
  const email = `browser.test.${stamp}@example.invalid`;

  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Users" }).click();
  await page.getByRole("button", { name: "Add user" }).click();

  await page.getByLabel("Full name").fill("Browser Test Person");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Job title").fill("Sales Executive");
  await page.getByLabel("Initial password").fill("Browser-Test-Passw0rd!");
  await page.getByLabel("Sales Representative").check();
  await page.screenshot({ path: `${SHOTS}/07-user-form.png`, fullPage: true });

  await page.getByRole("button", { name: "Create user" }).click();
  await expect(page.getByText("Created Browser Test Person.")).toBeVisible();

  // The record is really there: reload from the server rather than trusting the screen.
  await page.getByRole("button", { name: "Back to users" }).click();
  await page.getByPlaceholder("Search by name or email").fill("Browser Test Person");
  await expect(page.getByRole("cell", { name: email })).toBeVisible();

  await page.getByRole("link", { name: "Audit trail" }).click();
  await page.getByPlaceholder("Action, for example user.created").fill("user.created");
  await expect(page.getByRole("cell", { name: /Browser Test Person/ }).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/08-audit-after-create.png`, fullPage: true });
});

test("a sales representative is not offered administration and is refused it directly", async ({
  page,
  request,
}) => {
  const stamp = Date.now();
  const email = `rep.${stamp}@example.invalid`;
  const password = "Rep-Browser-Passw0rd!";

  // Create the representative through the interface as the administrator.
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto("/users/new");
  await page.getByLabel("Full name").fill("Rep Under Test");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Initial password").fill(password);
  await page.getByLabel("Sales Representative").check();
  await page.getByRole("button", { name: "Create user" }).click();
  await expect(page.getByText("Created Rep Under Test.")).toBeVisible();

  // Clear that first-sign-in password change, then sign in as the representative.
  await signOut(page);
  await signIn(page, email, password);
  await page.getByRole("link", { name: "Change password" }).click();
  await page.getByLabel("Current password").fill(password);
  await page.getByLabel("New password", { exact: true }).fill("Rep-Changed-Passw0rd!");
  await page.getByLabel("Confirm new password").fill("Rep-Changed-Passw0rd!");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByText("Your password has been changed.")).toBeVisible();

  // Administration is simply absent from the navigation.
  await expect(page.getByRole("navigation").getByRole("link", { name: "Users" })).toHaveCount(0);
  await expect(page.getByRole("navigation").getByRole("link", { name: "Roles" })).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/09-representative-navigation.png`, fullPage: true });

  // And typing the address in anyway is refused, because the refusal is the
  // server's, not the menu's.
  await page.goto("/users");
  await expect(page.getByRole("alert")).toContainText("do not have access");

  // Same answer for a direct API call that never touches the interface at all.
  const direct = await request.get("/api/users/", {
    headers: { Cookie: (await page.context().cookies()).map((c) => `${c.name}=${c.value}`).join("; ") },
  });
  expect(direct.status()).toBe(403);
  const body = await direct.json();
  expect(body.error.code).toBe("permission_denied");
  await page.screenshot({ path: `${SHOTS}/10-direct-access-refused.png`, fullPage: true });
});

test("a second editor is told their copy is stale instead of overwriting the first", async ({
  page,
  browser,
}) => {
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.goto("/company");
  await expect(page.getByLabel("Trading name")).toBeVisible();

  // A second session opens the same record before the first one saves.
  const second = await browser.newContext();
  const secondPage = await second.newPage();
  await signIn(secondPage, ADMIN_EMAIL, ADMIN_PASSWORD);
  await secondPage.goto("/company");
  await expect(secondPage.getByLabel("Trading name")).toBeVisible();

  await page.getByLabel("Trading name").fill(`First edit ${Date.now()}`);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Company settings saved.")).toBeVisible();

  await secondPage.getByLabel("Trading name").fill("Second edit");
  await secondPage.getByRole("button", { name: "Save changes" }).click();
  await expect(secondPage.getByText("changed by someone else")).toBeVisible();
  await secondPage.screenshot({ path: `${SHOTS}/11-stale-record-conflict.png`, fullPage: true });

  await second.close();

  // Put the trading name back. This suite runs against a shared database, so a
  // test that leaves a record renamed makes the next run depend on this one.
  await page.reload();
  await page.getByLabel("Trading name").fill(ORIGINAL_TRADE_NAME);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Company settings saved.")).toBeVisible();
});
