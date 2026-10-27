import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { demoProfile, results, startScanFromUi } from './helpers';

async function audit(page: Page) {
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

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme });

    test('every screen meets WCAG 2.1 AA', async ({ page, request }) => {
      test.setTimeout(60_000); // a dozen screens, a scan to wait for
      const id = await demoProfile(request, `Jeanne Exemple (${colorScheme})`);
      await page.goto('/');
      await expect(page.getByRole('heading', { name: 'Profils' })).toBeVisible();
      await audit(page);

      await page.goto(`/profils/${id}/elements`);
      await expect(page.getByTestId('seed')).toHaveCount(4);
      await audit(page);

      await page.goto(`/profils/${id}/recherche`);
      await expect(page.getByTestId('assisted-seed').first()).toBeVisible();
      await audit(page);

      await startScanFromUi(page, id);
      await expect(results(page).first()).toBeVisible();
      // Audited once it ends: a result arriving live would be measured halfway through its
      // fade-in. The failed run keeps an error and a retry button on the page.
      await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Terminé')).toBeVisible({
        timeout: 30_000,
      });
      await audit(page);

      await page.goto(`/profils/${id}`);
      await expect(page.getByTestId('graph-canvas')).toBeVisible();
      await audit(page);

      await page.goto(`/profils/${id}/liste`);
      await page.getByTestId('trace').first().getByRole('button').first().click();
      await expect(page.getByTestId('trace-panel').getByTestId('trace-value')).toBeVisible();
      await audit(page);
      await page.getByTestId('trace-panel').getByText('Pourquoi ces scores ?').click();
      await expect(page.getByTestId('score-reasons')).toHaveAttribute('open');
      await audit(page);
      await page
        .getByTestId('trace')
        .filter({ hasText: 'journal.example.net' })
        .first()
        .getByRole('button')
        .first()
        .click();
      await expect(page.getByTestId('remediation')).toBeVisible();
      await audit(page);
      await page.getByRole('button', { name: 'Préparer la demande' }).first().click();
      await expect(page.getByRole('dialog').getByLabel('Texte')).toBeVisible();
      await audit(page);
      await page.getByRole('button', { name: 'Je l’ai envoyée' }).click();
      await expect(page.getByTestId('followed')).toBeVisible();
      await audit(page);

      await page.goto(`/profils/${id}/a-faire`);
      await expect(page.getByTestId('request')).toHaveCount(1);
      await audit(page);

      await page.goto(`/profils/${id}/elements`);
      await expect(page.getByTestId('lead').first()).toBeVisible();
      await audit(page);

      await page.goto('/sources');
      await expect(page.getByTestId('source')).toHaveCount(1);
      await audit(page);

      await page.goto('/mot-de-passe');
      await expect(page.getByLabel('Mot de passe à vérifier')).toBeVisible();
      await audit(page);

      await page.goto('/reglages');
      await expect(page.getByTestId('github-token-state')).toBeVisible();
      await audit(page);

      await page.getByRole('button', { name: /Activité/ }).click();
      await expect(page.getByRole('dialog', { name: 'Activité' })).toBeVisible();
      await audit(page);
    });
  });
}
