import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { GraphViewState } from '@/lib/graph';
import { readViewState } from '@/lib/graph';
import { useDeleteView, useSaveView, useSavedViews } from '@/lib/queries';
import { BookmarkIcon, Trash2Icon } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

/** Named views of the graph: what is filtered, grouped, folded, selected, and where. */
export function SavedViews({
  profileId,
  current,
  onApply,
}: {
  profileId: number;
  /** The state to save, read when saving. */
  current: () => GraphViewState;
  onApply: (state: GraphViewState) => void;
}) {
  const views = useSavedViews(profileId);
  const save = useSaveView(profileId);
  const remove = useDeleteView(profileId);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(
      { name, state: current() as unknown as Record<string, unknown> },
      {
        onSuccess: (view) => {
          setName('');
          toast.success(t().views.savedToast(view.name));
        },
      },
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost">
          <BookmarkIcon aria-hidden />
          {t().views.title}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="grid w-80 gap-3">
        {views.data && views.data.length > 0 ? (
          <ul className="grid gap-1" aria-label={t().views.saved}>
            {views.data.map((view) => (
              <li key={view.id} className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  className="flex-1 justify-start truncate"
                  onClick={() => {
                    onApply(readViewState(view.state));
                    setOpen(false);
                  }}
                >
                  {view.name}
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t().views.delete(view.name)}
                  onClick={() => remove.mutate(view.id)}
                >
                  <Trash2Icon aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t().views.none}</p>
        )}
        <form onSubmit={submit} className="grid gap-1.5">
          <Label htmlFor="view-name">{t().views.saveCurrent}</Label>
          <div className="flex gap-2">
            <Input
              id="view-name"
              value={name}
              maxLength={100}
              placeholder={t().views.name}
              onChange={(e) => setName(e.target.value)}
            />
            <Button type="submit" disabled={!name.trim() || save.isPending}>
              {t().common.save}
            </Button>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
