import AxeBuilder from '@axe-core/playwright';
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

/**
 * How long to wait for a demo scan to finish (or a big graph to settle): about 20 s on a calm
 * machine; the margin is for a busy one, which runs everything several times slower.
 */
export const LONG_WAIT = 90_000;

/** Fails on any WCAG 2.1 AA violation on the page as it stands. */
export async function audit(page: Page) {
  // Contrast is measured on what settles on screen, not halfway through a fade-in.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity) // spinners
        .map((a) => a.finished.catch(() => null)),
    ),
  );
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
}
