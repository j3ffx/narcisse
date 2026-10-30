import { expect, test } from '@playwright/test';
import { audit, demoProfile, LONG_WAIT, results } from './helpers';

// A browser set to English: Narcisse follows it, down to the proofs a scan writes.
test.use({ locale: 'en-US' });

test.afterEach(async ({ request }) => {
  // The other tests read French: the choice goes back to the browser's.
  await request.patch('/api/preferences', { data: { ui_lang: 'auto' } });
});

test('speaks English to an English browser, and French once chosen', async ({ page, request }) => {
  test.setTimeout(240_000);
  const id = await demoProfile(request, 'Jeanne Exemple (English)');
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Profiles' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await audit(page);

  await page.goto(`/profils/${id}`);
  await page.getByRole('button', { name: 'Start a scan' }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect(page).toHaveURL(/\/scans\/\d+$/);
  await expect(results(page).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Finished')).toBeVisible({
    timeout: LONG_WAIT,
  });
  await expect(results(page).first()).toContainText('Fictitious result');
  await audit(page);

  await page.goto(`/profils/${id}/liste`);
  await page.getByTestId('trace').first().getByRole('button').first().click();
  await expect(page.getByTestId('trace-panel').getByText('Why these scores?')).toBeVisible();
  await audit(page);

  await page.goto('/sources');
  await expect(page.getByTestId('source')).toContainText('Demo module');
  await audit(page);

  await page.goto('/reglages');
  await audit(page);
  await page.getByRole('combobox', { name: 'Language' }).selectOption('fr');
  await expect(page.getByRole('heading', { name: 'Réglages' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
  await page.goto('/sources');
  await expect(page.getByTestId('source')).toContainText('Module de démonstration');
});
