import { expect, test, type APIRequestContext } from '@playwright/test';
import { audit, demoProfile, LONG_WAIT } from './helpers';

type Note = { state: string; output: { verdict?: string } | null };

async function finishedScan(request: APIRequestContext, name: string): Promise<number> {
  const id = await demoProfile(request, name);
  const started = await request.post(`/api/profiles/${id}/scans`, { data: {} });
  const { id: scanId } = (await started.json()) as { id: number };
  await expect
    .poll(
      async () =>
        ((await (await request.get(`/api/scans/${scanId}`)).json()) as { status: string }).status,
      { timeout: LONG_WAIT },
    )
    .toBe('done');
  return id;
}

test.afterEach(async ({ request }) => {
  // The other tests run without an assistant, as a new user would.
  await request.patch('/api/preferences', { data: { llm_provider: 'none' } });
});

test('the assistant answers when asked, and changes nothing until the user applies it', async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  const id = await finishedScan(request, 'Jeanne Exemple (assistant)');
  const panel = page.getByTestId('trace-panel');
  const helper = panel.getByTestId('trace-assistant');

  // Off by default: nothing about an assistant on a trace.
  await page.goto(`/profils/${id}/liste`);
  await page.getByTestId('trace').first().getByRole('button').first().click();
  await expect(panel.getByTestId('trace-value')).toBeVisible();
  await expect(helper).toHaveCount(0);

  // Chosen in the settings, and tried.
  await page.goto('/reglages');
  await page.getByRole('radio', { name: /Assistant de démonstration/ }).check();
  await expect(page.getByTestId('assistant-state')).toHaveText(
    'Assistant de démonstration est prêt.',
  );
  await audit(page);
  await page.getByRole('button', { name: 'Essayer' }).click();
  await expect(page.getByText('Assistant de démonstration répond')).toBeVisible();

  // Asked to explain a trace: what is sent first, then its answer, rewritten by the user.
  await page.goto(`/profils/${id}/liste`);
  await page.getByTestId('trace').first().getByRole('button').first().click();
  await helper.getByText('Voir ce qui reste sur ta machine').click();
  await expect(helper.getByTestId('assistant-prompt')).toContainText('Jeanne Exemple (assistant)');
  await helper.getByRole('button', { name: 'Expliquer cette trace' }).click();
  const explanation = helper.getByTestId('annotation-explain');
  await expect(explanation).toContainText('Avis de l’IA');
  await expect(explanation).toContainText('Un compte public', { timeout: LONG_WAIT });
  await explanation.getByRole('button', { name: 'Modifier' }).click();
  await explanation.getByLabel('Ce que c’est').fill('Mon vieux compte de forum.');
  await explanation.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(explanation).toContainText('Modifié par toi.');
  await expect(explanation).toContainText('Mon vieux compte de forum.');
  await audit(page);

  // The traces still to review, asked about in one batch.
  await page.getByRole('button', { name: 'Trier avec l’IA' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByTestId('triage-count')).toHaveText(/^\d+ questions, une par trace\.$/);
  await audit(page);
  await dialog.getByRole('button', { name: 'Lancer le tri' }).click();
  await expect(dialog).toBeHidden();

  // An answer that settles it: the trace's status stays as it was until the user applies it.
  const graph = (await (await request.get(`/api/profiles/${id}/graph`)).json()) as {
    nodes: { id: number; kind: string }[];
  };
  let settled: { id: number; verdict: string } | undefined;
  await expect
    .poll(
      async () => {
        for (const node of graph.nodes) {
          if (node.kind === 'identity') continue;
          const notes = (await (
            await request.get(`/api/entities/${node.id}/annotations`)
          ).json()) as Note[];
          const verdict = notes.find((n) => n.state === 'done')?.output?.verdict;
          if (verdict === 'me' || verdict === 'not_me') {
            settled = { id: node.id, verdict };
            return true;
          }
        }
        return false;
      },
      { timeout: LONG_WAIT },
    )
    .toBe(true);
  await page.goto(`/profils/${id}/liste?trace=${settled!.id}`);
  const verdict = helper.getByTestId('annotation-triage');
  await expect(verdict.getByTestId('annotation-verdict')).toBeVisible();
  await expect(panel.getByText('À vérifier', { exact: true })).toBeVisible();
  await verdict.getByRole('button', { name: /^Appliquer/ }).click();
  await expect(verdict).toContainText('Appliqué au statut de la trace.');
  await expect(
    panel.getByText(settled!.verdict === 'me' ? 'C’est moi' : 'Pas moi', { exact: true }).first(),
  ).toBeVisible();
});
