import { expect, test, type Page } from '@playwright/test';
import { audit } from './helpers';

/** The welcome page shows on the user's own side with no profile: this server runs the demo and
 * holds other tests' profiles, so the browser is told otherwise. Nothing real is ever reached. */
async function asFirstStart(page: Page) {
  await page.route('**/api/info', async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      json: { ...(await response.json()), demo: false, can_switch: true },
    });
  });
  await page.route('**/api/profiles', (route) =>
    route.request().method() === 'GET' ? route.fulfill({ json: [] }) : route.fallback(),
  );
}

test.afterEach(async ({ request }) => {
  await request.patch('/api/preferences', { data: { welcomed: false } });
});

test('someone new is told what Narcisse is for, once, before their first profile', async ({
  page,
  request,
}) => {
  await asFirstStart(page);
  await page.goto('/');
  await expect(page.getByTestId('welcome')).toBeVisible();
  await expect(page.getByTestId('welcome')).toContainText('Qui tu peux chercher');
  await audit(page);

  await page.getByRole('button', { name: 'J’ai compris, commencer' }).click();
  await expect(page.getByRole('heading', { name: 'Profils' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Profils' })).toBeVisible();
  await expect(page.getByTestId('welcome')).toHaveCount(0);
  expect((await (await request.get('/api/preferences')).json()).welcomed).toBe(true);
});

test('the example starts Narcisse on the demo side, then the page reloads', async ({ page }) => {
  await asFirstStart(page);
  let asked = 0;
  await page.route('**/api/side', (route) => {
    asked += 1;
    // The side has changed: the page sees the demo from now on, and goes back to the start.
    void page.unroute('**/api/info');
    return route.fulfill({ status: 202, json: null });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Essayer avec un exemple' }).click();
  await expect(page.getByTestId('welcome')).toHaveCount(0);
  expect(asked).toBe(1);
});

test('a new version is told only once asked for, and never by default', async ({
  page,
  request,
}) => {
  await asFirstStart(page);
  await request.patch('/api/preferences', { data: { welcomed: true } });
  let asked = 0;
  await page.route('**/api/update', (route) => {
    asked += 1;
    return route.fulfill({
      json: { latest: '99.0.0', url: 'https://github.com/j3ffx/narcisse/releases/latest' },
    });
  });
  await page.goto('/reglages');
  const box = page.getByRole('checkbox', { name: 'Me prévenir quand une nouvelle version sort' });
  await expect(box).not.toBeChecked();
  await expect(page.getByTestId('new-version')).toHaveCount(0);
  expect(asked).toBe(0);

  await box.click();
  await expect(page.getByTestId('new-version')).toContainText('Narcisse 99.0.0 est disponible.');
  await audit(page);

  await box.click();
  await expect(page.getByTestId('new-version')).toHaveCount(0);
  await request.patch('/api/preferences', { data: { check_updates: false } });
});

test('a new profile says what to do next, until its first scan', async ({ page, request }) => {
  const created = await request.post('/api/profiles', {
    data: { name: 'Jeanne Exemple (étapes)' },
  });
  const { id } = (await created.json()) as { id: number };
  await page.goto(`/profils/${id}`);
  await expect(page.getByTestId('next-step')).toContainText('Première étape');
  await page.getByRole('link', { name: 'Aller aux éléments' }).click();
  await expect(page).toHaveURL(/elements$/);
  await request.post(`/api/profiles/${id}/seeds`, {
    data: { kind: 'username', value: 'jeanne.exemple' },
  });
  await page.reload();
  await expect(page.getByTestId('next-step')).toContainText('Prochaine étape');
  await audit(page);
});
