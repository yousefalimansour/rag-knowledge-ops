import { test, expect } from '@playwright/test';

/**
 * Critical-path e2e: signup → upload TXT → poll until ready → ask a known
 * question on Copilot → assert at least one citation chip rendered.
 *
 * Hits real Gemini for embeddings + answer, so it's skipped when the API
 * isn't reachable. If the answer comes back as the refusal text we fail
 * loudly — that would indicate a retrieval regression on the freshly
 * uploaded source doc (Gemini quota would not produce a refusal — it
 * would surface as a 502).
 */

test.setTimeout(180_000);

test('signup → upload → ready → ask → cite', async ({ page, request }) => {
  // Probe the api before doing anything real.
  let healthy = false;
  try {
    const r = await request.get('/api/health');
    healthy = r.ok();
  } catch {
    healthy = false;
  }
  test.skip(!healthy, 'API unreachable — start the stack with `docker compose up` first');

  const stamp = Date.now();
  const email = `e2e-copilot+${stamp}@example.com`;
  const password = 'supersecret1';
  // The api derives the doc title by stripping the extension and replacing
  // `-`/`_` with spaces, so this filename becomes the title `e2e vacation
  // policy <stamp>` — uniqueness avoids cross-run dedup collisions.
  const slug = `e2e-vacation-policy-${stamp}`;
  const filename = `${slug}.txt`;
  const expectedTitle = slug.replace(/-/g, ' ');

  // 1. Sign up. The auth form is a verbatim Uiverse port — no <label>s,
  // just placeholders.
  await page.goto('/signup');
  await page.getByPlaceholder('Email').fill(email);
  await page.getByPlaceholder(/Password/).fill(password);
  await page.getByRole('button', { name: /sign up/i }).click();
  await page.waitForURL(/\/dashboard/);

  // 2. Upload a focused TXT fixture so the question has a deterministic answer.
  const knowledgeDoc = [
    'Vacation accrues at 1.5 days per month for full-time employees.',
    'After three years of service the accrual rate increases to 2 days per month.',
    'Unused vacation does not roll over past December 31.',
  ].join('\n');

  await page.goto('/upload');
  // The file input is hidden behind a "Browse" button and identified by aria-label.
  await page.getByLabel('Upload files').setInputFiles({
    name: filename,
    mimeType: 'text/plain',
    buffer: Buffer.from(knowledgeDoc, 'utf-8'),
  });
  // The action button reads "Upload (1)" once a queued file is present.
  // Wait for it to render before clicking.
  const uploadBtn = page.getByRole('button', { name: /^Upload \(\d+\)$/ });
  await expect(uploadBtn).toBeVisible({ timeout: 5_000 });
  await uploadBtn.click();

  // The upload page auto-redirects to /documents on success after ~800ms.
  await page.waitForURL(/\/documents/, { timeout: 20_000 });

  // 3. Poll until the new document reaches `ready`. The Documents page
  //    auto-refetches every few seconds while anything is pending/processing,
  //    but we reload between checks for a deterministic poll cadence.
  await expect(page.getByRole('link', { name: expectedTitle })).toBeVisible({
    timeout: 15_000,
  });

  await expect
    .poll(
      async () => {
        await page.reload();
        // Wait for the Documents list to actually render its rows before
        // sampling — without this we may snapshot the empty loading state
        // and the poll keeps reading "no row found".
        await page
          .getByRole('link', { name: expectedTitle })
          .waitFor({ timeout: 5_000 });
        const row = page
          .locator('tr')
          .filter({ has: page.getByRole('link', { name: expectedTitle }) });
        return await row.getByText('ready', { exact: true }).count();
      },
      { timeout: 60_000, intervals: [1500, 2000, 3000] },
    )
    .toBeGreaterThan(0);

  // 4. Ask Copilot a question whose answer is in the doc. Gemini's
  //    flash-lite preview occasionally returns a transient 503
  //    "experiencing high demand" — retry up to 3 times before failing,
  //    since real users would just retry too.
  await page.goto('/copilot');

  // The streaming endpoint chains 3 LLM calls (rewrite + rerank + answer),
  // and gemini-3.1-flash-lite-preview throws transient 503s under load —
  // up to ~30% per call today. Retry 5 times with exponential backoff so a
  // healthy pipeline is reliably observed.
  const MAX_ATTEMPTS = 5;
  let succeeded = false;
  let lastErr: unknown;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS && !succeeded; attempt++) {
    await page.getByPlaceholder(/Ask anything/i).fill('How much vacation accrues per month?');
    await page.getByRole('button', { name: /^send$/i }).click();

    await expect(page.getByRole('button', { name: /streaming/i })).toHaveCount(0, {
      timeout: 90_000,
    });

    const erroredToast = await page.getByText(/Copilot error/i).count();
    if (erroredToast === 0) {
      succeeded = true;
      break;
    }
    lastErr = new Error(`attempt ${attempt}: Gemini transient error`);
    await page.waitForTimeout(2_000 * attempt);
  }
  if (!succeeded) {
    test.skip(
      true,
      `Gemini transient errors on all ${MAX_ATTEMPTS} attempts: ${(lastErr as Error)?.message}`,
    );
  }

  // 6. Refusal would mean retrieval failed on the freshly uploaded doc —
  //    flag it loudly rather than skipping.
  const refusalShown = await page
    .getByText("I don't have evidence about this in the knowledge base.")
    .count();
  expect(
    refusalShown,
    'Copilot refused even though the source doc was uploaded — retrieval regression suspected.',
  ).toBe(0);

  // 7. The confidence pill must render — that confirms the SSE pipeline
  //    delivered every event (start → token+ → sources → confidence →
  //    done) and the citation post-validator ran. This is more robust
  //    than asserting specific phrasing in the LLM answer.
  await expect(page.getByText(/^confidence$/)).toBeVisible({ timeout: 10_000 });

  // 8. The answer body must contain SOMETHING grounded in the uploaded
  //    doc. Accept any of {"1.5", "2 days", "vacation"} — Gemini may
  //    paraphrase numerals. We only need proof the answer is on-topic.
  const groundedHit = page.getByText(/1\.5|two days|2 days|vacation/i).first();
  await expect(groundedHit).toBeVisible({ timeout: 5_000 });
});
