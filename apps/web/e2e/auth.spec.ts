import { test, expect } from '@playwright/test';

test('signup → dashboard → logout → login redirect', async ({ page }) => {
  const email = `e2e+${Date.now()}@example.com`;
  const password = 'supersecret1';

  // Unauthenticated visit redirects to /login.
  await page.goto('/dashboard');
  await page.waitForURL(/\/login/);

  // Sign up. The auth form uses placeholders rather than <label>s — the
  // login card is a verbatim Uiverse port and intentionally label-less.
  await page.goto('/signup');
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder(/Password/).fill(password);
  await page.getByRole('button', { name: /sign up/i }).click();

  await page.waitForURL(/\/dashboard/);
  await expect(page.getByText(email)).toBeVisible();

  // Sign out. The "Sign out" action lives inside a Radix DropdownMenu
  // attached to the user avatar in the topbar — open it first. The email
  // contains a `+` which is regex-special, so filter by visible text.
  await page.getByRole('button').filter({ hasText: email }).click();
  await page.getByRole('menuitem', { name: /sign out/i }).click();
  await page.waitForURL(/\/login/);
});
