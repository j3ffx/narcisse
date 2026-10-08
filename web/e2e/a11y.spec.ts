import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { demoProfile, results, startScanFromUi } from './helpers';

async function audit(page: Page) {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
}

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test('every screen meets WCAG 2.1 AA', async ({ page, request }) => {
      const id = await demoProfile(request, `Jeanne Exemple (${colorScheme})`);
      await page.goto('/');
      await expect(page.getByRole('heading', { name: 'Profils' })).toBeVisible();
      await audit(page);

      await page.goto(`/profils/${id}`);
      await expect(page.getByTestId('seed')).toHaveCount(4);
      await audit(page);

      await startScanFromUi(page, id);
      await expect(results(page).first()).toBeVisible();
      await audit(page);

      await page.getByRole('button', { name: /Activité/ }).click();
      await expect(page.getByRole('dialog', { name: 'Activité' })).toBeVisible();
      await audit(page);
    });
  });
}
