import { test, expect } from '@playwright/test';

test('signup → dashboard → logout → login redirect', async ({ page }) => {
  const email = `e2e+${Date.now()}@example.com`;
  const password = 'supersecret1';

  // Unauthenticated visit redirects to /login.
  await page.goto('/dashboard');
  await page.waitForURL(/\/login/);

  // Sign up.
  await page.goto('/signup');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /create account/i }).click();

  await page.waitForURL(/\/dashboard/);
  await expect(page.getByText(email)).toBeVisible();

  // Sign out.
  await page.getByRole('button', { name: /sign out/i }).click();
  await page.waitForURL(/\/login/);
});
