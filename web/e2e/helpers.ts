import { expect, type APIRequestContext, type Page } from '@playwright/test';

/** A fictitious profile with one seed of each kind the demo module reacts to differently. */
export async function demoProfile(request: APIRequestContext, name: string): Promise<number> {
  const response = await request.post('/api/profiles', { data: { name } });
  expect(response.ok()).toBe(true);
  const { id } = (await response.json()) as { id: number };
  for (const [kind, value] of [
    ['name', name],
    ['username', 'jeanne.exemple'],
    ['email', 'jeanne.exemple@example.org'],
    ['domain', 'jeanne-exemple.example.org'],
  ]) {
    const seed = await request.post(`/api/profiles/${id}/seeds`, { data: { kind, value } });
    expect(seed.ok()).toBe(true);
  }
  return id;
}

export async function startScanFromUi(page: Page, profileId: number): Promise<void> {
  await page.goto(`/profils/${profileId}`);
  await page.getByRole('button', { name: 'Lancer un scan' }).click();
  await page.getByRole('button', { name: 'Lancer', exact: true }).click();
  await expect(page).toHaveURL(/\/scans\/\d+$/);
}

export const results = (page: Page) => page.getByTestId('result');
export const run = (page: Page, kind: string) => page.getByTestId('run').filter({ hasText: kind });
