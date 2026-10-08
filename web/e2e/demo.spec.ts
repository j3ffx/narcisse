import { expect, test } from '@playwright/test';
import { demoProfile, results, run, startScanFromUi } from './helpers';

test('a profile is created and given seeds from the UI', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Nouveau profil' }).click();
  await page.getByLabel('Nom du profil').fill('Jeanne Exemple (UI)');
  await page.getByRole('button', { name: 'Créer' }).click();
  await expect(page.getByRole('heading', { name: 'Jeanne Exemple (UI)' })).toBeVisible();

  await page.getByLabel('Valeur').fill('Jeanne Exemple');
  await page.getByRole('button', { name: 'Ajouter' }).click();
  await expect(page.getByTestId('seed')).toHaveCount(1);

  await page.getByLabel('Valeur').fill('Jeanne Exemple');
  await page.getByRole('button', { name: 'Ajouter' }).click();
  await expect(page.getByRole('alert')).toHaveText('Cet élément est déjà dans le profil.');

  await page.getByRole('button', { name: 'Surveillé' }).click();
  await expect(page.getByRole('button', { name: 'Ignoré' })).toBeVisible();
});

test('a scan shows results live, every state, and can be retried', async ({ page, request }) => {
  const id = await demoProfile(request, 'Jeanne Exemple (scan)');
  await startScanFromUi(page, id);

  // Results arrive one by one, not in a block at the end.
  await expect(results(page).first()).toBeVisible();
  const early = await results(page).count();
  await expect.poll(() => results(page).count()).toBeGreaterThan(early);

  await expect(run(page, 'Pseudo').getByText('Limité par la source')).toBeVisible();
  await expect(run(page, 'Pseudo').getByText(/reprise dans/)).toBeVisible();
  const failed = run(page, 'Domaine');
  await expect(failed.getByText('En erreur')).toBeVisible();
  await expect(failed.getByText('demo.example est indisponible pour le moment.')).toBeVisible();

  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Terminé')).toBeVisible({
    timeout: 30_000,
  });
  await failed.getByRole('button', { name: 'Réessayer' }).click();
  await expect(failed.getByText('En cours').or(failed.getByText('En file'))).toBeVisible();
  await expect(failed.getByText('Terminé')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Résultats \(48/)).toBeVisible();
});

test('pause and resume answer at once and hold across a reload', async ({ page, request }) => {
  const id = await demoProfile(request, 'Jeanne Exemple (pause)');
  await startScanFromUi(page, id);
  await expect(results(page).first()).toBeVisible();

  await page.getByRole('button', { name: 'Pause' }).click();
  // Optimistic: shown before the server answers.
  await expect(page.getByRole('button', { name: 'Reprendre' })).toBeVisible({ timeout: 100 });
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('En pause')).toBeVisible();

  // The browser goes away and comes back: same state.
  await page.reload();
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('En pause')).toBeVisible();
  const held = await results(page).count();
  await page.waitForTimeout(1500);
  expect(await results(page).count()).toBeLessThanOrEqual(held + 4);

  await page.getByRole('button', { name: 'Reprendre' }).click();
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('En cours')).toBeVisible();
  await expect.poll(() => results(page).count()).toBeGreaterThan(held + 4);
});

test('a scan is cancelled from the activity centre', async ({ page, request }) => {
  const id = await demoProfile(request, 'Jeanne Exemple (annulation)');
  await startScanFromUi(page, id);
  await expect(results(page).first()).toBeVisible();

  await page.getByRole('button', { name: /Activité/ }).click();
  const card = page.getByTestId('activity-scan').filter({ hasText: 'Jeanne Exemple (annulation)' });
  await card.getByRole('button', { name: 'Annuler' }).click();
  await page.getByRole('button', { name: 'Annuler le scan' }).click();
  await expect(card.getByText('Annulé').first()).toBeVisible({ timeout: 100 });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Annulé')).toBeVisible();
});

test('no long task over 200 ms while a scan streams', async ({ page, request }) => {
  await page.addInitScript(() => {
    const w = window as unknown as { longTasks: number[] };
    w.longTasks = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) w.longTasks.push(entry.duration);
    }).observe({ type: 'longtask', buffered: true });
  });
  const id = await demoProfile(request, 'Jeanne Exemple (fluidité)');
  await startScanFromUi(page, id);
  await expect(results(page).first()).toBeVisible();
  // Use the page while results keep coming.
  await page.getByRole('button', { name: /Activité/ }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('searchbox', { name: 'Chercher dans les résultats' }).fill('forum');
  await page.getByRole('searchbox', { name: 'Chercher dans les résultats' }).fill('');
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Terminé')).toBeVisible({
    timeout: 30_000,
  });

  const longTasks = await page.evaluate(
    () => (window as unknown as { longTasks: number[] }).longTasks,
  );
  expect(longTasks.filter((d) => d > 200)).toEqual([]);
});
