import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { NO_FILTER, isFiltering, type TraceFilter } from '@/lib/graph';
import { ENTITY_STATUS_LABELS, KIND_LABELS } from '@/lib/labels';
import type { EntityKind, EntityStatus, GraphNode } from '@/lib/types';
import { FilterIcon } from 'lucide-react';
import { useMemo, type ReactNode } from 'react';

const CONFIDENCES = [0, 0.3, 0.5, 0.7];
const STATUSES: EntityStatus[] = ['unreviewed', 'confirmed', 'false_positive'];

function toggle<T>(list: T[], value: T, on: boolean): T[] {
  return on ? [...list, value] : list.filter((v) => v !== value);
}

/** Filters by kind, source, status, confidence and date; shared by the graph and the list. */
export function TraceFilters({
  nodes,
  filter,
  onChange,
  sourceTitle,
}: {
  nodes: GraphNode[];
  filter: TraceFilter;
  onChange: (filter: TraceFilter) => void;
  sourceTitle: (name: string) => string;
}) {
  const kinds = useMemo(() => count(nodes.map((n) => n.kind)), [nodes]);
  const modules = useMemo(() => count(nodes.flatMap((n) => n.modules)), [nodes]);
  const active = isFiltering(filter);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant={active ? 'secondary' : 'outline'} aria-label="Filtres">
          <FilterIcon aria-hidden />
          Filtres{active ? ' (actifs)' : ''}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="grid max-h-[70dvh] w-80 gap-4 overflow-y-auto">
        <Group title="Types">
          {[...kinds].map(([kind, n]) => (
            <Choice
              key={kind}
              id={`kind-${kind}`}
              label={`${KIND_LABELS[kind as EntityKind]} (${n})`}
              checked={filter.kinds.includes(kind as EntityKind)}
              onChange={(on) =>
                onChange({ ...filter, kinds: toggle(filter.kinds, kind as EntityKind, on) })
              }
            />
          ))}
        </Group>
        <Group title="Sources">
          {[...modules].map(([name, n]) => (
            <Choice
              key={name}
              id={`module-${name}`}
              label={`${name === 'seed' ? 'Déclaré par toi' : sourceTitle(name)} (${n})`}
              checked={filter.modules.includes(name)}
              onChange={(on) => onChange({ ...filter, modules: toggle(filter.modules, name, on) })}
            />
          ))}
        </Group>
        <Group title="Statut">
          {STATUSES.map((status) => (
            <Choice
              key={status}
              id={`status-${status}`}
              label={ENTITY_STATUS_LABELS[status]}
              checked={filter.statuses.includes(status)}
              onChange={(on) =>
                onChange({ ...filter, statuses: toggle(filter.statuses, status, on) })
              }
            />
          ))}
        </Group>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-confidence">Confiance minimale</Label>
          <select
            id="filter-confidence"
            className="h-8 rounded-lg border bg-background px-2 text-sm"
            value={filter.minConfidence}
            onChange={(e) => onChange({ ...filter, minConfidence: Number(e.target.value) })}
          >
            {CONFIDENCES.map((c) => (
              <option key={c} value={c}>
                {c === 0 ? 'Toutes' : `${Math.round(c * 100)} % et plus`}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="filter-since">Vues depuis le</Label>
          <Input
            id="filter-since"
            type="date"
            value={filter.since ?? ''}
            onChange={(e) => onChange({ ...filter, since: e.target.value || null })}
          />
        </div>
        <Button variant="ghost" disabled={!active} onClick={() => onChange(NO_FILTER)}>
          Tout afficher
        </Button>
      </PopoverContent>
    </Popover>
  );
}

function count(values: string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return new Map([...counts].sort((a, b) => b[1] - a[1]));
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="grid gap-1.5">
      <legend className="mb-1 text-sm font-medium">{title}</legend>
      {children}
    </fieldset>
  );
}

function Choice({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox id={id} checked={checked} onCheckedChange={(c) => onChange(c === true)} />
      <Label htmlFor={id} className="font-normal">
        {label}
      </Label>
    </div>
  );
}
