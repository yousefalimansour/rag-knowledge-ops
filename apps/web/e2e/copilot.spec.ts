import { test, expect } from '@playwright/test';

/**
 * Critical-path e2e: signup → upload TXT → poll until ready → ask a known
 * question on Copilot → assert at least one citation chip rendered.
 *
 * Hits real Gemini for embeddings + answer, so it's skipped when the stack
 * isn't reachable or when GOOGLE_API_KEY is missing.
 */

test('upload → poll ready → ask → cite', async ({ page, request }) => {
  // Probe the api before doing anything real — bail with clear skip if the
  // stack isn't running on the configured port.
  let healthy = false;
  try {
    const r = await request.get('/api/health');
    healthy = r.ok();
  } catch {
    healthy = false;
  }
  test.skip(!healthy, 'API unreachable — start the stack with `docker compose up` first');

  const email = `e2e-copilot+${Date.now()}@example.com`;
  const password = 'supersecret1';

  // 1. Sign up.
  await page.goto('/signup');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /create account/i }).click();
  await page.waitForURL(/\/dashboard/);

  // 2. Upload a focused TXT fixture so the question has a deterministic answer.
  const knowledgeDoc = [
    'Vacation accrues at 1.5 days per month for full-time employees.',
    'After three years of service the accrual rate increases to 2 days per month.',
    'Unused vacation does not roll over past December 31.',
  ].join('\n');

  await page.goto('/upload');
  await page.setInputFiles('input[type=file]', {
    name: 'vacation-policy.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from(knowledgeDoc, 'utf-8'),
  });
  await page.getByRole('button', { name: /upload|start/i }).first().click();

  // 3. Poll the documents list until the new doc reaches `ready`. Allow up
  //    to 60s — embedding the file end-to-end can take a few seconds on a
  //    cold container.
  await page.goto('/documents');
  await expect
    .poll(
      async () => {
        await page.reload();
        const ready = await page
          .getByRole('row', { name: /vacation-policy\.txt/i })
          .getByText(/ready/i)
          .count();
        return ready;
      },
      { timeout: 60_000, intervals: [1500, 2000, 3000] },
    )
    .toBeGreaterThan(0);

  // 4. Ask Copilot a question whose answer is in the document.
  await page.goto('/copilot');
  await page.getByPlaceholder(/Ask anything/i).fill('How much vacation accrues per month?');
  await page.getByRole('button', { name: /^send$/i }).click();

  // 5. Wait for streaming to settle (button text flips back from "Streaming…").
  await expect(page.getByRole('button', { name: /^send$/i })).toBeVisible({
    timeout: 45_000,
  });

  // 6. The answer must include at least one numbered citation chip OR be the
  //    refusal — but since we just uploaded the source, refusal would be a
  //    real regression worth failing the run on.
  const refusalShown = await page
    .getByText("I don't have evidence about this in the knowledge base.")
    .count();
  if (refusalShown > 0) {
    throw new Error(
      'Copilot returned the refusal text even though the source doc was uploaded — this indicates ' +
        'a retrieval regression or that Gemini quota is exhausted.',
    );
  }
  await expect(page.getByRole('button', { name: /Open source 1/i })).toBeVisible({
    timeout: 5_000,
  });
});
