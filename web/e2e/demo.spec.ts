import { expect, test, type Page } from '@playwright/test';
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

test('a trace marked "not me" leaves the list, and the choice holds', async ({ page, request }) => {
  const id = await demoProfile(request, 'Jeanne Exemple (tri)');
  await startScanFromUi(page, id);
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Terminé')).toBeVisible({
    timeout: 30_000,
  });
  const first = results(page).first();
  const value = await first.getByTestId('result-value').innerText();

  await first.getByRole('button', { name: 'Pas moi' }).click();
  await expect(results(page).filter({ hasText: value })).toHaveCount(0, { timeout: 100 });

  await page.getByLabel('Afficher les « pas moi »').check();
  const back = results(page).filter({ hasText: value }).first();
  await expect(back).toHaveAttribute('data-status', 'false_positive');

  await back.getByRole('button', { name: 'C’est moi' }).click();
  await page.reload();
  await expect(results(page).filter({ hasText: value }).first()).toHaveAttribute(
    'data-status',
    'confirmed',
  );
});

test('the sources and the settings explain themselves', async ({ page }) => {
  await page.goto('/sources');
  await expect(page.getByTestId('source')).toHaveCount(1); // demo mode: the demo module only
  await expect(page.getByText('aucun site (rien ne sort de ta machine)')).toBeVisible();

  await page.goto('/reglages');
  const github = page.getByRole('region', { name: 'Token GitHub (facultatif)' });
  await expect(github.getByTestId('github-token-state')).toHaveText('Aucun token enregistré.');
  await github.getByRole('textbox', { name: 'Token' }).fill('fake-test-token');
  await github.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(github.getByTestId('github-token-state')).toHaveText('Un token est enregistré.');
  await github.getByRole('button', { name: 'Retirer' }).click();
  await expect(github.getByTestId('github-token-state')).toHaveText('Aucun token enregistré.');

  const fediverse = page.getByRole('region', { name: 'Instances Mastodon et Fediverse' });
  await fediverse.getByRole('textbox', { name: 'Instance' }).fill('https://Social.Example.org/');
  await fediverse.getByRole('button', { name: 'Ajouter' }).click();
  await expect(fediverse.getByRole('listitem')).toHaveText('social.example.org');
  await fediverse.getByRole('button', { name: 'Retirer social.example.org' }).click();
  await expect(fediverse.getByText('Aucune instance ajoutée.')).toBeVisible();
});

test('the graph and the list show the same traces and follow one selection', async ({
  page,
  request,
}) => {
  const id = await demoProfile(request, 'Jeanne Exemple (graphe)');
  await startScanFromUi(page, id);
  await expect(page.getByRole('heading', { name: /Scan/ }).getByText('Terminé')).toBeVisible({
    timeout: 30_000,
  });

  await page.goto(`/profils/${id}`);
  await expect(page.getByTestId('graph-canvas')).toBeVisible();
  const count = await page.getByTestId('trace-count').textContent();

  await page.getByRole('link', { name: 'Liste' }).click();
  await expect(page.getByTestId('trace-count')).toHaveText(count!);
  // Search, pick: the trace is selected and its detail opens.
  await page.getByRole('combobox', { name: /Chercher une trace/ }).fill('forum.example.org');
  await page.getByRole('option').first().click();
  const panel = page.getByTestId('trace-panel');
  await expect(panel.getByTestId('trace-value')).toContainText('forum.example.org');
  await expect(page).toHaveURL(/trace=\d+/);
  await panel.getByRole('button', { name: 'C’est moi' }).click();
  await expect(panel.getByText('Statut').locator('+ dd')).toHaveText('C’est moi');

  // The same trace, selected in the graph.
  await panel.getByRole('link', { name: 'Voir dans le graphe' }).click();
  await expect(page.getByTestId('graph-canvas')).toBeVisible();
  await expect(page.getByTestId('trace-panel').getByTestId('trace-value')).toContainText(
    'forum.example.org',
  );
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('trace-panel')).toHaveCount(0);

  // Filters cut the list down to one kind.
  await page.getByRole('link', { name: 'Liste' }).click();
  await page.getByRole('button', { name: 'Filtres' }).click();
  await page.getByLabel(/^Email/).check();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('trace-count')).toContainText(' sur ');
  // Emails only, and the identity everything hangs from.
  for (const row of await page.getByTestId('trace').all()) {
    await expect(row).toContainText(/Email|Identité/);
  }
});

test('a trace found becomes one of the profile’s elements', async ({ page, request }) => {
  const id = await demoProfile(request, 'Jeanne Exemple (élément ajouté)');
  const started = await request.post(`/api/profiles/${id}/scans`, { data: {} });
  const { id: scanId } = (await started.json()) as { id: number };
  await expect
    .poll(
      async () =>
        ((await (await request.get(`/api/scans/${scanId}`)).json()) as { status: string }).status,
      { timeout: 30_000 },
    )
    .toBe('done');

  await page.goto(`/profils/${id}/liste`);
  await page.getByRole('combobox', { name: /Chercher une trace/ }).fill('forum.example.org');
  await page.getByRole('option').first().click();
  const panel = page.getByTestId('trace-panel');
  await panel.getByRole('button', { name: 'Ajouter comme élément' }).click();
  await expect(panel.getByText('Élément du profil')).toBeVisible();

  await page.getByRole('link', { name: 'Éléments' }).click();
  await expect(page.getByTestId('seed')).toHaveCount(5);
  await expect(page.getByTestId('seed').last()).toContainText('forum.example.org');
});

test('scores say why, actions say what to do, and leads become elements', async ({
  page,
  request,
}) => {
  const id = await demoProfile(request, 'Jeanne Exemple (scores et pistes)');
  const started = await request.post(`/api/profiles/${id}/scans`, { data: {} });
  const { id: scanId } = (await started.json()) as { id: number };
  await expect
    .poll(
      async () =>
        ((await (await request.get(`/api/scans/${scanId}`)).json()) as { status: string }).status,
      { timeout: 30_000 },
    )
    .toBe('done');

  // The most exposing trace first; its scores, and the rules behind them.
  await page.goto(`/profils/${id}/liste`);
  await page.getByRole('combobox', { name: 'Afficher d’abord' }).selectOption('risk');
  await page.getByTestId('trace').first().getByRole('button').first().click();
  const panel = page.getByTestId('trace-panel');
  await expect(panel.getByTestId('trace-risk')).toContainText('/ 100');
  await expect(panel.getByTestId('trace-confidence')).toContainText('/ 100');
  await panel.getByText('Pourquoi ces scores ?').click();
  await expect(panel.getByTestId('score-reasons')).toContainText('exposition de base');

  // What to do about a page: the request Narcisse prepares, signed with the profile's name.
  await page
    .getByTestId('trace')
    .filter({ hasText: 'journal.example.net' })
    .first()
    .getByRole('button')
    .first()
    .click();
  const sheet = panel.getByTestId('remediation');
  await expect(sheet.getByTestId('action').first()).toContainText('Demander au site');
  await expect(sheet.getByTestId('action').nth(1)).toContainText('Faire déréférencer');
  await sheet.getByRole('button', { name: 'Préparer la demande' }).first().click();
  const letter = page.getByRole('dialog');
  const text = letter.getByLabel('Texte');
  await expect(text).toHaveValue(/article 17/);
  await expect(text).toHaveValue(/https:\/\/journal\.example\.net\//);
  await expect(text).toHaveValue(
    /Jeanne Exemple \(scores et pistes\)\njeanne\.exemple@example\.org/,
  );
  await expect(letter.getByRole('link', { name: 'Ouvrir dans ma messagerie' })).toHaveAttribute(
    'href',
    /^mailto:\?subject=/,
  );
  await letter.getByRole('button', { name: 'English' }).click();
  await expect(text).toHaveValue(/Article 17/);

  // Sent: the request is followed, and « À faire » shows it with the profile's exposure.
  await letter.getByRole('button', { name: 'Je l’ai envoyée' }).click();
  await expect(letter).toBeHidden();
  await expect(sheet.getByTestId('followed')).toContainText('Envoyée le');
  await sheet.getByRole('link', { name: 'Voir dans « À faire »' }).click();
  await expect(page.getByTestId('exposure')).toContainText('Ton exposition');
  const followed = page.getByTestId('request');
  await expect(followed).toHaveCount(1);
  await expect(followed).toContainText('journal.example.net');
  await expect(followed.getByRole('combobox', { name: 'Statut' })).toHaveValue('sent');
  await followed.getByRole('combobox', { name: 'Statut' }).selectOption('waiting');
  await expect(followed.getByTestId('request-summary')).toContainText('En attente');
  await page.goto(`/profils/${id}/liste`);

  // Leads: one dismissed, one added as an element. (A lead's text may name another as the trace
  // it was found through: they are told apart by their own link.)
  await page.getByRole('link', { name: 'Éléments' }).click();
  const leads = page.getByTestId('lead');
  const lead = (value: string) =>
    leads.filter({ has: page.getByRole('link', { name: value, exact: true }) });
  await expect(leads.first()).toBeVisible();
  const dismissed = (await leads.first().getByRole('link').textContent())!;
  await lead(dismissed)
    .getByRole('button', { name: /^Écarter/ })
    .click();
  await expect(lead(dismissed)).toHaveCount(0);

  const added = (await leads.first().getByRole('link').textContent())!;
  await lead(added).getByRole('button', { name: 'Ajouter comme élément' }).click();
  await expect(page.getByTestId('seed')).toHaveCount(5);
  await expect(page.getByTestId('seed').last()).toContainText(added);
  await expect(lead(added)).toHaveCount(0);
  await page.reload();
  await expect(leads.first()).toBeVisible();
  await expect(lead(dismissed)).toHaveCount(0); // the choice holds
});

test('the assisted search prepares the queries and takes back what the user found', async ({
  page,
  request,
}) => {
  const id = await demoProfile(request, 'Jeanne Exemple (recherche)');
  await page.goto(`/profils/${id}/recherche`);
  // One group per element worth searching (the domain, the name, the email, the username).
  await expect(page.getByTestId('assisted-seed')).toHaveCount(4);
  const google = page
    .getByRole('link', { name: /Chercher "Jeanne Exemple \(recherche\)" sur Google/ })
    .first();
  await expect(google).toHaveAttribute('href', /^https:\/\/www\.google\.com\/search\?q=%22Jeanne/);
  await expect(google).toHaveAttribute('target', '_blank');

  await page
    .getByLabel('Adresse d’une page qui parle de toi')
    .fill('https://club.example.org/jeanne');
  await page.getByLabel('Ce qu’elle dit de toi (facultatif)').fill('Mon nom dans un compte rendu');
  await page.getByRole('button', { name: 'Ajouter à mes traces' }).click();
  await page.getByRole('link', { name: 'la voir dans le graphe' }).click();
  const panel = page.getByTestId('trace-panel');
  await expect(panel.getByTestId('trace-value')).toHaveText('https://club.example.org/jeanne');
  await expect(panel.getByText('Mon nom dans un compte rendu')).toBeVisible();
  await expect(panel.getByText('Statut').locator('+ dd')).toHaveText('C’est moi');
});

test('demo mode draws a fictitious graph of thousands of traces', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Graphe fictif' }).click();
  await page.getByRole('menuitem', { name: /500 traces/ }).click();
  await expect(page.getByRole('heading', { name: 'Graphe fictif (500 traces)' })).toBeVisible();
  await expect(page.getByTestId('graph-canvas')).toBeVisible();
  await expect(page.getByTestId('trace-count')).toContainText('traces');
});

test('in the graph: a path, groups, folds, and a view saved then restored', async ({
  page,
  request,
}) => {
  const made = await request.post('/api/demo/graph', { data: { nodes: 500 } });
  const { profile_id: id } = (await made.json()) as { profile_id: number };
  await page.goto(`/profils/${id}`);
  const canvas = page.getByTestId('graph-canvas');
  await expect(canvas).toHaveAttribute('data-nodes', /\d+/);
  const all = Number(await canvas.getAttribute('data-nodes'));

  // How is a trace related to the identity?
  await page.getByRole('combobox', { name: /Chercher une trace/ }).fill('jeanne');
  await page.getByRole('option').first().click();
  await page.getByRole('button', { name: 'toi', exact: true }).click();
  await expect(page.getByTestId('path')).toContainText('lien');

  // Grouped by site: far fewer nodes.
  const grouping = page.getByLabel('Regrouper');
  await grouping.selectOption('site');
  await expect
    .poll(async () => Number(await canvas.getAttribute('data-nodes')))
    .toBeLessThan(all / 2);

  // Saved, changed, restored.
  await page.getByRole('button', { name: 'Vues' }).click();
  await page.getByLabel('Enregistrer la vue actuelle').fill('Par site');
  await page.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(page.getByText('Vue « Par site » enregistrée.')).toBeVisible();
  await page.keyboard.press('Escape');
  await grouping.selectOption('none');
  await expect(canvas).toHaveAttribute('data-nodes', String(all));
  await page.getByRole('button', { name: 'Vues' }).click();
  await page.getByRole('button', { name: 'Par site', exact: true }).click();
  await expect(grouping).toHaveValue('site');

  // Leaves folded: fewer traces visible, all of them back once unfolded.
  await grouping.selectOption('none');
  await page.getByRole('button', { name: 'Replier les feuilles' }).click();
  await expect
    .poll(async () => Number(await canvas.getAttribute('data-visible')))
    .toBeLessThan(all);
  await page.getByRole('button', { name: 'Replier les feuilles' }).click();
  await expect(canvas).toHaveAttribute('data-visible', String(all));
});

test('the traces still answer the pointer once the graph is dragged about', async ({
  page,
  request,
}) => {
  const made = await request.post('/api/demo/graph', { data: { nodes: 500 } });
  const { profile_id: id } = (await made.json()) as { profile_id: number };
  await page.goto(`/profils/${id}`);
  const canvas = page.getByTestId('graph-canvas');
  await expect(canvas).toHaveAttribute('data-nodes', /\d+/);
  await expect(canvas).not.toHaveAttribute('data-settling', { timeout: 30_000 });
  const box = (await canvas.boundingBox())!;
  expect(await sweepFindsTrace(page, box)).toBe(true);

  // The stage dragged from a spot with no trace under it, let go while still moving: the graph
  // glides on (inertia), which redraws it without reprocessing anything.
  let from = { x: 0, y: 0 };
  for (const [dx, dy] of [
    [30, 30],
    [30, 90],
    [90, 30],
    [90, 90],
  ] as const) {
    from = { x: box.x + dx, y: box.y + dy };
    await page.mouse.move(from.x, from.y);
    await page.waitForTimeout(150);
    if ((await canvas.evaluate((el) => getComputedStyle(el).cursor)) !== 'pointer') break;
  }
  await page.mouse.down();
  await page.mouse.move(from.x + 120, from.y + 60, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(1000);

  expect(await sweepFindsTrace(page, box)).toBe(true);
});

/** Whether the pointer, swept across the canvas, comes over a trace (sigma then shows a hand). */
async function sweepFindsTrace(
  page: Page,
  box: { x: number; y: number; width: number; height: number },
): Promise<boolean> {
  await page.getByTestId('graph-canvas').evaluate((el) => {
    const w = window as unknown as { overTrace: boolean };
    w.overTrace = false;
    new MutationObserver(() => {
      if (el.style.cursor === 'pointer') w.overTrace = true;
    }).observe(el, { attributeFilter: ['style'] });
  });
  for (let row = 1; row <= 5; row++) {
    const y = box.y + (box.height * row) / 6;
    await page.mouse.move(box.x + 10, y);
    await page.mouse.move(box.x + box.width - 10, y, { steps: 60 });
  }
  await page.waitForTimeout(200);
  return page.evaluate(() => (window as unknown as { overTrace: boolean }).overTrace);
}

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
      { timeout: 30_000 },
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
