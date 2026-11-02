import { expect, test } from '@playwright/test';
import { GPU } from './gpu';
import { demoProfile, LONG_WAIT } from './helpers';

// In software (SwiftShader, headless Chrome's default) the page waits on the GPU process for over
// 200 ms now and then, with its own thread idle: that measures the renderer, not Narcisse. CI has
// no GPU, so it stays in software there.
test.use({ launchOptions: { args: process.env.CI ? [] : GPU } });

test('no long task over 200 ms on the graph while a scan streams into it', async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    const w = window as unknown as { longTasks: number[] };
    w.longTasks = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) w.longTasks.push(entry.duration);
    }).observe({ type: 'longtask', buffered: true });
  });
  const id = await demoProfile(request, 'Jeanne Exemple (graphe en direct)');
  const started = await request.post(`/api/profiles/${id}/scans`, { data: {} });
  const { id: scanId } = (await started.json()) as { id: number };
  await page.goto(`/profils/${id}`);
  const canvas = page.getByTestId('graph-canvas');
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute('data-nodes', /\d+/);
  const first = Number(await canvas.getAttribute('data-nodes'));
  // From here on: the page is loaded (its code and shaders compiled), traces keep arriving.
  await page.evaluate(() => {
    (window as unknown as { longTasks: number[] }).longTasks = [];
  });
  // Click about while traces keep arriving.
  await page.getByRole('combobox', { name: /Chercher une trace/ }).fill('jeanne');
  await page.keyboard.press('Escape');
  await expect
    .poll(
      async () =>
        (
          (await (await request.get(`/api/scans/${scanId}`)).json()) as {
            status: string;
          }
        ).status,
      { timeout: LONG_WAIT },
    )
    .toBe('done');
  await expect
    .poll(async () => Number(await canvas.getAttribute('data-nodes')))
    .toBeGreaterThan(first);

  const longTasks = await page.evaluate(
    () => (window as unknown as { longTasks: number[] }).longTasks,
  );
  expect(longTasks.filter((d) => d > 200)).toEqual([]);
});
