import { expect, test, type Page } from '@playwright/test';

/**
 * How the graph holds up as it grows: for fictitious graphs of 500 to 20,000 traces, the time to
 * the first drawing, the layout's duration, the frame rate while the user pans and zooms, and the
 * long tasks (over 50 ms; over 200 ms the page feels stuck). Prints a table.
 */
const SIZES = (process.env.BENCH_SIZES ?? '500,5000,20000').split(',').map(Number);
const INTERACTION_MS = 4000;

interface Row {
  traces: number;
  drawn: number;
  firstDrawMs: number;
  layoutMs: number;
  fps: number;
  worstFrameMs: number;
  longTasks: number;
  worstTaskMs: number;
}

const rows: Row[] = [];
let renderer = '?';

async function watch(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { longTasks: number[] };
    w.longTasks = [];
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) w.longTasks.push(entry.duration);
    }).observe({ type: 'longtask', buffered: true });
  });
}

/** Drags and zooms over the canvas for a while, counting the frames drawn meanwhile. */
async function interact(page: Page): Promise<{ fps: number; worstFrameMs: number }> {
  const box = (await page.getByTestId('graph-canvas').boundingBox())!;
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  await page.evaluate(() => {
    const w = window as unknown as { frames: number[] };
    w.frames = [];
    const tick = (t: number) => {
      w.frames.push(t);
      if (w.frames.length < 100_000) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  const start = Date.now();
  let step = 0;
  while (Date.now() - start < INTERACTION_MS) {
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    for (let i = 0; i < 10; i++) {
      await page.mouse.move(cx + Math.sin(step + i / 3) * 200, cy + Math.cos(step + i / 3) * 120);
    }
    await page.mouse.up();
    await page.mouse.wheel(0, step % 2 ? 240 : -240);
    step++;
  }
  const frames = await page.evaluate(() => (window as unknown as { frames: number[] }).frames);
  const span = frames.at(-1)! - frames[0]!;
  const gaps = frames.slice(1).map((t, i) => t - frames[i]!);
  return {
    fps: Math.round(((frames.length - 1) / span) * 1000),
    worstFrameMs: Math.round(Math.max(...gaps)),
  };
}

for (const size of SIZES) {
  test(`graph of ${size} traces`, async ({ page, request }) => {
    const made = await request.post('/api/demo/graph', {
      data: { nodes: size },
      timeout: 120_000,
    });
    const { profile_id: id } = (await made.json()) as { profile_id: number };
    await watch(page);

    renderer = await page.evaluate(() => {
      const gl = document.createElement('canvas').getContext('webgl2');
      const info = gl?.getExtension('WEBGL_debug_renderer_info');
      return gl && info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : '?';
    });
    const opened = Date.now();
    await page.goto(`/profils/${id}`);
    const canvas = page.getByTestId('graph-canvas');
    await expect(canvas).toHaveAttribute('data-nodes', /\d+/, { timeout: 60_000 });
    const firstDrawMs = Date.now() - opened;
    await expect(canvas).not.toHaveAttribute('data-settling', /.*/, { timeout: 60_000 });
    const layoutMs = Date.now() - opened - firstDrawMs;
    const { fps, worstFrameMs } = await interact(page);
    const longTasks = await page.evaluate(
      () => (window as unknown as { longTasks: number[] }).longTasks,
    );
    rows.push({
      traces: size,
      drawn: Number(await canvas.getAttribute('data-nodes')),
      firstDrawMs,
      layoutMs,
      fps,
      worstFrameMs,
      longTasks: longTasks.length,
      worstTaskMs: Math.round(Math.max(0, ...longTasks)),
    });
  });
}

test.afterAll(() => {
  console.log(`\nGraph benchmark, headless Chrome, WebGL by ${renderer}`);
  console.table(rows);
});
