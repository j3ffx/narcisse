import { Button } from '@/components/ui/button';
import type { GraphGroup } from '@/lib/graph';
import { KIND_LABELS } from '@/lib/labels';
import { XIcon } from 'lucide-react';
import { KIND_ICONS } from './kinds';

const SHOWN = 100;

/** A group of traces drawn as one node: what it holds, and a way to open it. */
export function GroupPanel({
  group,
  title,
  onOpen,
  onPick,
  onClose,
}: {
  group: GraphGroup;
  title: string;
  onOpen: () => void;
  /** Opens the group on one of its traces. */
  onPick: (id: number) => void;
  onClose: () => void;
}) {
  const members = [...group.members].sort((a, b) => a.display.localeCompare(b.display));
  return (
    <aside
      aria-label="Détail du groupe"
      className="flex max-h-full flex-col gap-4 overflow-y-auto rounded-lg border bg-card p-4"
      data-testid="group-panel"
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-heading text-lg font-semibold">Groupe</h2>
        <Button variant="ghost" size="icon-sm" aria-label="Fermer le détail" onClick={onClose}>
          <XIcon aria-hidden />
        </Button>
      </div>
      <p className="font-medium break-all">{title}</p>
      <Button className="w-fit" onClick={onOpen}>
        Déplier les {group.members.length} traces
      </Button>
      <ul className="grid gap-1 text-sm">
        {members.slice(0, SHOWN).map((member) => {
          const Icon = KIND_ICONS[member.kind];
          return (
            <li key={member.id} className="flex items-center gap-2">
              <Icon aria-label={KIND_LABELS[member.kind]} className="size-4 shrink-0" />
              <button
                type="button"
                className="truncate text-left underline-offset-2 hover:underline focus-visible:underline"
                onClick={() => onPick(member.id)}
                title={member.display}
              >
                {member.display}
              </button>
            </li>
          );
        })}
      </ul>
      {members.length > SHOWN && (
        <p className="text-sm text-muted-foreground">
          … et {members.length - SHOWN} autres : déplie le groupe pour les voir.
        </p>
      )}
    </aside>
  );
}
