import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { get } from '@/lib/api';
import { inActivity, matches, withProgress, withResult, withRun, withScan } from '@/lib/live';
import { keys } from '@/lib/queries';
import type { Activity, LiveEvent, ResultsPage, ScanDetail } from '@/lib/types';

export type Connection = 'connecting' | 'live' | 'reconnecting';

const EVENT_TYPES: LiveEvent['type'][] = [
  'scan.created',
  'scan.updated',
  'run.updated',
  'run.progress',
  'result.created',
];

/**
 * Keeps the query cache in step with the server: a snapshot of the activity first, then every
 * event after it. EventSource reconnects by itself and resumes from the last event it got, so a
 * dropped connection or a closed laptop misses nothing. Events are applied once per frame, so a
 * burst of results never blocks the page.
 */
export function useLiveUpdates(): Connection {
  const client = useQueryClient();
  const [connection, setConnection] = useState<Connection>('connecting');

  useEffect(() => {
    let source: EventSource | null = null;
    let stopped = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let frame = 0;
    let pending: LiveEvent[] = [];

    const flush = () => {
      frame = 0;
      const batch = pending;
      pending = [];
      for (const event of batch) apply(client, event);
    };

    const connect = async () => {
      let activity: Activity;
      try {
        activity = await get<Activity>('/activity');
      } catch {
        setConnection('reconnecting');
        retry = setTimeout(() => void connect(), 2000);
        return;
      }
      if (stopped) return;
      client.setQueryData(keys.activity, activity);
      for (const scan of activity.scans) client.setQueryData(keys.scan(scan.id), scan);

      source = new EventSource(`/api/events?after=${activity.last_event_id}`);
      source.onopen = () => setConnection('live');
      source.onerror = () => setConnection('reconnecting');
      for (const type of EVENT_TYPES) {
        source.addEventListener(type, (message) => {
          pending.push({
            type,
            data: JSON.parse((message as MessageEvent<string>).data),
          } as LiveEvent);
          frame ||= requestAnimationFrame(flush);
        });
      }
      // The server lost track of what this page saw: start again from a fresh snapshot.
      source.addEventListener('reset', () => {
        source?.close();
        void client.invalidateQueries();
        void connect();
      });
    };

    void connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      cancelAnimationFrame(frame);
      source?.close();
    };
  }, [client]);

  return connection;
}

function apply(client: QueryClient, event: LiveEvent) {
  const update = (scanId: number, change: (s: ScanDetail) => ScanDetail, created?: ScanDetail) => {
    client.setQueryData<ScanDetail>(keys.scan(scanId), (scan) => (scan ? change(scan) : created));
    client.setQueryData<Activity>(keys.activity, (activity) =>
      activity ? inActivity(activity, scanId, change, created) : activity,
    );
  };

  switch (event.type) {
    case 'scan.created':
      update(event.data.id, () => event.data, event.data);
      void client.invalidateQueries({ queryKey: keys.scans(event.data.profile_id) });
      break;
    case 'scan.updated':
      update(event.data.id, (s) => withScan(s, event.data));
      void client.invalidateQueries({ queryKey: keys.scans(event.data.profile_id) });
      break;
    case 'run.updated':
      update(event.data.scan_id, (s) => withRun(s, event.data));
      break;
    case 'run.progress':
      update(event.data.scan_id, (s) => withProgress(s, event.data));
      break;
    case 'result.created': {
      const result = event.data;
      update(result.scan_id, (s) => withResult(s, result));
      // Every loaded list of this scan's results whose filter the new result passes.
      for (const [key, page] of client.getQueriesData<ResultsPage>({
        queryKey: keys.results(result.scan_id),
      })) {
        const filter = key[2] as { kind: string | null; q: string } | undefined;
        if (!page || !filter || !matches(result, filter.kind, filter.q)) continue;
        if (page.items.some((r) => r.id === result.id)) continue;
        // A list cut at its first page only learns that there is one more.
        const complete = page.items.length >= page.total;
        client.setQueryData<ResultsPage>(key, {
          items: complete ? [...page.items, result] : page.items,
          total: page.total + 1,
        });
      }
      break;
    }
  }
}
