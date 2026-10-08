import { useEffect, useState } from 'react';

/** True once `active` has lasted `delay` ms: quick loads show nothing, slow ones say so. */
export function useDelayed(active: boolean, delay = 300): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setShown(true), delay);
    return () => {
      clearTimeout(timer);
      setShown(false);
    };
  }, [active, delay]);
  return active && shown;
}
