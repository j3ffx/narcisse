import { lang, num, t } from '@/i18n';
// A profile's exports as the user keeps them: the CSV of its traces and a self-contained HTML
// report (no script, no outside resource, printable as PDF), both made from the API's complete
// export (`narcisse-export`, version 1) with the UI's own French texts. Pure functions, tested in
// report.test.ts.
import { ENTITY_STATUS_LABELS, KIND_LABELS, PROFILE_KIND_LABELS } from './labels';
import { REQUEST_STATUS_LABELS, actionText, formatDay } from './remediation';
import { RISK_LEVEL_LABELS, points, reasonEffect, reasonText, riskLevel } from './scores';
import { formatDate } from './time';
import type {
  ExposurePoint,
  FollowedRequest,
  GraphNode,
  ProfileDetail,
  ScoreReasons,
} from './types';

export interface ExportedTrace extends GraphNode {
  reasons: ScoreReasons;
}

export interface ProfileExport {
  format: 'narcisse-export';
  version: number;
  narcisse: string;
  exported_at: string;
  profile: ProfileDetail;
  exposure: { levels: Record<string, number>; exposure: number };
  traces: ExportedTrace[];
  evidence: { entity_id: number; url: string | null }[];
  requests: FollowedRequest[];
  history: ExposurePoint[];
}

type SourceTitle = (module: string) => string;

/** `narcisse-jeanne-exemple-2026-10-27.csv` */
export function exportName(data: ProfileExport, extension: string): string {
  const slug =
    data.profile.name
      .normalize('NFKD')
      .replace(/\p{M}/gu, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || 'profil';
  return `narcisse-${slug}-${data.exported_at.slice(0, 10)}.${extension}`;
}

/** The traces the user acts on: theirs (or not reviewed yet), not the identity. */
const kept = (data: ProfileExport) =>
  data.traces.filter((t) => t.kind !== 'identity' && t.status !== 'false_positive');

const sources = (trace: GraphNode, title: SourceTitle) =>
  trace.modules.map((m) => (m === 'seed' ? t().panel.declared : title(m))).join(', ');

function firstUrls(data: ProfileExport): Map<number, string> {
  const urls = new Map<number, string>();
  for (const proof of data.evidence) {
    if (proof.url && !urls.has(proof.entity_id)) urls.set(proof.entity_id, proof.url);
  }
  return urls;
}

function requestsByTrace(data: ProfileExport): Map<number, FollowedRequest> {
  return new Map(data.requests.map((r) => [r.entity.id, r]));
}

// CSV

function cell(value: string | number): string {
  const text = String(value);
  return /[";\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The traces, one per line: `;` and a BOM, so that Excel in French opens it as it is. */
export function toCsv(data: ProfileExport, title: SourceTitle): string {
  const urls = firstUrls(data);
  const requests = requestsByTrace(data);
  const header = t().report.csvHeader;
  const lines = kept(data).map((trace) => {
    const request = requests.get(trace.id);
    return [
      KIND_LABELS[trace.kind],
      trace.display,
      ENTITY_STATUS_LABELS[trace.status],
      trace.confidence === null ? '' : points(trace.confidence),
      trace.risk === null ? '' : points(trace.risk),
      trace.risk === null ? '' : RISK_LEVEL_LABELS[riskLevel(trace.risk)],
      sources(trace, title),
      trace.first_seen.slice(0, 10),
      trace.last_seen.slice(0, 10),
      trace.gone_at ? trace.gone_at.slice(0, 10) : '',
      trace.evidence_count ?? '',
      urls.get(trace.id) ?? '',
      request ? REQUEST_STATUS_LABELS[request.status] : '',
    ];
  });
  const BOM = String.fromCharCode(0xfeff);
  return `${BOM}${[header, ...lines].map((line) => line.map(cell).join(';')).join('\r\n')}\r\n`;
}

// HTML

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => ESCAPES[c]!);

const TOP = 20;
const LEVELS = ['critical', 'high', 'medium', 'low'] as const;

const STYLE = `
body{font:15px/1.5 system-ui,sans-serif;color:#1c1917;background:#fff;max-width:60rem;margin:2rem auto;padding:0 1rem}
h1{font-size:1.6rem;margin:0 0 .25rem}h2{font-size:1.2rem;margin:2rem 0 .5rem;border-bottom:1px solid #d6d3d1}
h3{font-size:1rem;margin:1rem 0 .25rem;word-break:break-all}
.muted{color:#57534e}.warn{background:#fef3c7;padding:.5rem .75rem;border-radius:.5rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #e7e5e4;vertical-align:top}
td.value{word-break:break-all}.levels{display:flex;gap:2rem}.levels b{display:block;font-size:1.6rem}
ul{margin:.25rem 0;padding-left:1.25rem}@media print{body{margin:0}h2{break-after:avoid}}
`;

/** A self-contained report of the profile: no script, no outside resource. */
export function toReport(data: ProfileExport, title: SourceTitle): string {
  const e = escapeHtml;
  const say = t().report;
  const traces = kept(data);
  const requests = requestsByTrace(data);
  const date = formatDay(data.exported_at);
  const present = traces.filter((t) => !t.gone_at);
  const top = [...present]
    .filter((t) => (t.risk ?? 0) > 0)
    .sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))
    .slice(0, TOP);

  const levels = LEVELS.map(
    (level) =>
      `<div><b>${data.exposure.levels[level] ?? 0}</b><span class="muted">${RISK_LEVEL_LABELS[level]}</span></div>`,
  ).join('');

  const history = data.history.length
    ? `<table><thead><tr><th>${say.scanOf}</th><th>${say.exposure}</th>${LEVELS.map((l) => `<th>${RISK_LEVEL_LABELS[l]}</th>`).join('')}</tr></thead><tbody>${data.history
        .map(
          (p) =>
            `<tr><td>${e(formatDate(p.taken_at))}</td><td>${num(p.exposure)}</td>${LEVELS.map((l) => `<td>${p.levels[l] ?? 0}</td>`).join('')}</tr>`,
        )
        .join('')}</tbody></table>`
    : `<p class="muted">${say.noHistory}</p>`;

  const topHtml = top.length
    ? top
        .map((trace) => {
          const request = requests.get(trace.id);
          const reasons = trace.reasons.risk
            .map((r) => {
              const effect = reasonEffect(r);
              return `<li>${e(reasonText(r))}${effect ? ` <span class="muted">(${e(effect)})</span>` : ''}</li>`;
            })
            .join('');
          const risk = points(trace.risk ?? 0);
          const level = RISK_LEVEL_LABELS[riskLevel(trace.risk ?? 0)];
          const scores = say.scores(risk, level, points(trace.confidence ?? 0));
          return `<h3>${e(trace.display)}</h3><p class="muted">${e(KIND_LABELS[trace.kind])} · ${e(scores)} · ${e(sources(trace, title))}</p>${reasons ? `<ul>${reasons}</ul>` : ''}${request ? `<p>${say.followed} ${e(actionText(request.action).title)} · ${REQUEST_STATUS_LABELS[request.status]}</p>` : ''}`;
        })
        .join('')
    : `<p class="muted">${say.noTop}</p>`;

  const requestRows = data.requests.length
    ? `<table><thead><tr>${say.requestHeader.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${data.requests
        .map(
          (r) =>
            `<tr><td class="value">${e(r.entity.display)}</td><td>${e(actionText(r.action).title)}</td><td>${e(r.service)}</td><td>${REQUEST_STATUS_LABELS[r.status]}</td><td>${r.sent_at ? e(formatDay(r.sent_at)) : ''}</td><td>${r.check === 'gone' ? say.gone : r.check === 'still_there' ? say.stillThere : ''}</td></tr>`,
        )
        .join('')}</tbody></table>`
    : `<p class="muted">${say.noRequest}</p>`;

  const all = `<table><thead><tr>${say.allHeader.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${[
    ...traces,
  ]
    .sort((a, b) => (b.risk ?? 0) - (a.risk ?? 0))
    .map(
      (trace) =>
        `<tr><td>${e(KIND_LABELS[trace.kind])}</td><td class="value">${e(trace.display)}${trace.gone_at ? ` <span class="muted">(${say.gone})</span>` : ''}</td><td>${ENTITY_STATUS_LABELS[trace.status]}</td><td>${trace.risk === null ? '' : points(trace.risk)}</td><td>${trace.confidence === null ? '' : points(trace.confidence)}</td><td>${e(trace.last_seen.slice(0, 10))}</td></tr>`,
    )
    .join('')}</tbody></table>`;

  return `<!doctype html>
<html lang="${lang()}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Narcisse — ${e(data.profile.name)} — ${e(date)}</title><style>${STYLE}</style></head>
<body>
<h1>${e(say.title(data.profile.name))}</h1>
<p class="muted">${e(say.subtitle(data.narcisse, date, PROFILE_KIND_LABELS[data.profile.kind], traces.length))}</p>
<p class="warn">${say.warning}</p>
<h2>${t().requests.exposure}</h2>
<div class="levels">${levels}</div>
<p class="muted">${say.exposureIntro}</p>
${history}
<h2>${say.top}</h2>
${topHtml}
<h2>${t().requests.yours}</h2>
${requestRows}
<h2>${say.all}</h2>
${all}
</body></html>
`;
}
