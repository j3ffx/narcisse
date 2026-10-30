import { t } from '@/i18n';
import { cn } from 'cn';
import {
  RISK_LEVEL_LABELS,
  points,
  reasonEffect,
  reasonText,
  riskLevel,
  type RiskLevel,
} from '@/lib/scores';
import type { ScoreReason, ScoreReasons } from '@/lib/types';

// Decorative (the level is also written out): a dot of the level's colour.
const DOTS: Record<RiskLevel, string> = {
  low: 'bg-emerald-600 dark:bg-emerald-400',
  medium: 'bg-amber-500 dark:bg-amber-400',
  high: 'bg-orange-600 dark:bg-orange-400',
  critical: 'bg-red-600 dark:bg-red-400',
};

/** A risk level's dot (decorative: the level is written next to it). */
export function LevelDot({ level }: { level: RiskLevel }) {
  return <span aria-hidden className={cn('size-2 shrink-0 rounded-full', DOTS[level])} />;
}

/** A risk as « 72 / 100 · élevé », with its level's dot. */
export function RiskValue({ risk, className }: { risk: number; className?: string }) {
  const level = riskLevel(risk);
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)} data-level={level}>
      <span aria-hidden className={cn('size-2 shrink-0 rounded-full', DOTS[level])} />
      {points(risk)} / 100 · {RISK_LEVEL_LABELS[level]}
    </span>
  );
}

/** Why the scores are what they are: every rule that applied, and what it did. */
export function ScoreReasonsDetails({ reasons }: { reasons: ScoreReasons }) {
  if (!reasons.confidence.length && !reasons.risk.length) return null;
  return (
    <details className="grid gap-2 text-sm" data-testid="score-reasons">
      <summary className="w-fit cursor-pointer rounded font-medium underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
        {t().scores.why}
      </summary>
      <div className="mt-2 grid gap-3">
        <Rules title={t().scores.confidence} reasons={reasons.confidence} />
        <Rules title={t().scores.risk} reasons={reasons.risk} />
      </div>
    </details>
  );
}

function Rules({ title, reasons }: { title: string; reasons: ScoreReason[] }) {
  if (!reasons.length) return null;
  return (
    <div className="grid gap-1">
      <h4 className="text-xs font-semibold text-muted-foreground">{title}</h4>
      <ul className="grid gap-1">
        {reasons.map((reason, i) => (
          <li key={`${reason.code}-${i}`} className="flex items-baseline justify-between gap-3">
            <span>{reasonText(reason)}</span>
            <span className="shrink-0 font-mono text-xs tabular-nums">{reasonEffect(reason)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
