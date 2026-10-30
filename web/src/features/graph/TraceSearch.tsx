import { t } from '@/i18n';
import { Input } from '@/components/ui/input';
import { search } from '@/lib/graph';
import { KIND_LABELS } from '@/lib/labels';
import type { GraphNode } from '@/lib/types';
import { SearchIcon } from 'lucide-react';
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { KIND_ICONS } from './kinds';

/** Finds a trace by its text; picking one selects it (and the graph moves onto it). "/" focuses. */
export function TraceSearch({
  nodes,
  onPick,
  label = t().search.label,
  placeholder = t().search.placeholder,
  shortcut = true,
  className = 'relative min-w-56 flex-1 sm:max-w-sm',
}: {
  nodes: GraphNode[];
  onPick: (node: GraphNode) => void;
  label?: string;
  placeholder?: string;
  /** Whether "/" focuses it (one search per page). */
  shortcut?: boolean;
  className?: string;
}) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const found = useMemo(() => search(nodes, query, 12), [nodes, query]);

  useEffect(() => {
    if (!shortcut) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.key !== '/' || target.closest('input, textarea, [contenteditable]')) return;
      event.preventDefault();
      input.current?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shortcut]);

  const pick = (node: GraphNode) => {
    onPick(node);
    setOpen(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, found.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === 'Enter' && found[active]) {
      event.preventDefault();
      pick(found[active]);
    } else if (event.key === 'Escape') {
      setOpen(false);
    }
  };

  const expanded = open && query.trim() !== '';
  return (
    <div className={className}>
      <SearchIcon
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        ref={input}
        role="combobox"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={expanded && found[active] ? `${listId}-${active}` : undefined}
        aria-label={label}
        placeholder={placeholder}
        className="pl-8"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {expanded && (
        <ul
          id={listId}
          role="listbox"
          aria-label={t().search.found}
          className="absolute inset-x-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-lg bg-popover p-1 text-sm shadow-md ring-1 ring-foreground/10"
        >
          {found.length === 0 && (
            <li className="px-2 py-1.5 text-muted-foreground" role="presentation">
              {t().search.none}
            </li>
          )}
          {found.map((node, i) => {
            const Icon = KIND_ICONS[node.kind];
            return (
              <li
                key={node.id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={`flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 ${i === active ? 'bg-accent text-accent-foreground' : ''}`}
                // mousedown: picked before the input's blur closes the list
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(node);
                }}
                onMouseEnter={() => setActive(i)}
              >
                <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{node.display}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                  {KIND_LABELS[node.kind]}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
