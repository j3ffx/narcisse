import { useDelayed } from '@/hooks/useDelayed';
import { LoaderIcon } from 'lucide-react';

/** Says what is loading, after 300 ms (before that, a blank space reads as instant). */
export function Pending({ label }: { label: string }) {
  const shown = useDelayed(true);
  if (!shown) return null;
  return (
    <p role="status" className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
      <LoaderIcon aria-hidden className="size-4 motion-safe:animate-spin" />
      {label}
    </p>
  );
}
