import { t } from '@/i18n';
import { ReviewButtons } from '@/components/ReviewButtons';
import { KIND_LABELS, RELATION_LABELS } from '@/lib/labels';
import { useModules } from '@/lib/queries';
import type { Result } from '@/lib/types';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from 'cn';
import { ExternalLinkIcon } from 'lucide-react';
import { useRef } from 'react';

const ROW_HEIGHT = 92;

/** Only the rows near the viewport exist in the page: thousands of results scroll smoothly. */
export function ResultList({ items }: { items: Result[] }) {
  const parent = useRef<HTMLDivElement>(null);
  const modules = useModules();
  const titles = new Map(modules.data?.map((m) => [m.name, m.title]));
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual is fine here
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parent.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  return (
    <div
      ref={parent}
      className="max-h-[36rem] overflow-y-auto rounded-lg border"
      tabIndex={0}
      aria-label={t().scanPage.list}
    >
      <ul className="relative" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((row) => {
          const result = items[row.index]!;
          return (
            <li
              key={result.id}
              data-testid="result"
              data-status={result.entity.status}
              className={cn(
                'absolute inset-x-0 flex items-center gap-3 border-b px-3 motion-safe:animate-in motion-safe:fade-in',
                result.entity.status === 'false_positive' && 'opacity-60',
              )}
              style={{ height: ROW_HEIGHT, transform: `translateY(${row.start}px)` }}
            >
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="shrink-0 rounded bg-muted px-1.5 text-xs text-muted-foreground">
                    {KIND_LABELS[result.entity.kind]}
                  </span>
                  {result.entity.attributes.adult === true && (
                    <span className="shrink-0 rounded bg-red-100 px-1.5 text-xs text-red-900 dark:bg-red-950 dark:text-red-100">
                      site adulte
                    </span>
                  )}
                  <span className="truncate font-medium" data-testid="result-value">
                    {result.entity.display}
                  </span>
                  {result.url && (
                    <a
                      href={result.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="shrink-0 text-muted-foreground hover:text-foreground"
                      aria-label={t().scanPage.open(String(result.url))}
                    >
                      <ExternalLinkIcon aria-hidden className="size-4" />
                    </a>
                  )}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {result.relation
                    ? `${RELATION_LABELS[result.relation] ?? result.relation} · `
                    : ''}
                  {titles.get(result.module) ?? result.module}
                  {result.confidence !== null &&
                    ` · ${t().scanPage.confidence(Math.round(result.confidence * 100))}`}
                </p>
                {result.excerpt && (
                  <p className="truncate text-xs text-muted-foreground">{result.excerpt}</p>
                )}
              </div>
              <ReviewButtons entity={result.entity} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
