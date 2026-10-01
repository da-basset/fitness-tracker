import { useCallback, useEffect, useRef, useState } from 'react';

import { OUTBOX_KEY, subscribe } from './bus';
import { readCache, writeCache } from './db';
import { pendingEvents, type OutboxRow } from './outbox';
import type { Fetched } from './request';

export const SYNCED_KEY = 'synced';

type State<T> = {
  data: T | undefined;
  loading: boolean;
  refreshing: boolean;
  offline: boolean;
  /** Set when the server answered 404, e.g. no active plan. */
  notFound: string | null;
  error: string | null;
  fetchedAt: string | null;
};

/**
 * Cache-first read: shows the last stored copy (with queued offline changes
 * laid over it) right away, then refreshes from the server and stores that.
 */
export function useResource<T>(
  key: string | null,
  fetcher: () => Promise<Fetched<T>>,
  overlay?: (data: T, pending: OutboxRow[]) => T
) {
  const [state, setState] = useState<State<T>>({
    data: undefined,
    loading: true,
    refreshing: false,
    offline: false,
    notFound: null,
    error: null,
    fetchedAt: null,
  });
  const fetcherRef = useRef(fetcher);
  const overlayRef = useRef(overlay);
  useEffect(() => {
    fetcherRef.current = fetcher;
    overlayRef.current = overlay;
  });

  const readLocal = useCallback(async () => {
    if (!key) return;
    const cached = await readCache<T>(key);
    if (!cached) return;
    const apply = overlayRef.current;
    const data = apply ? apply(cached.data, await pendingEvents()) : cached.data;
    setState((s) => ({ ...s, data, loading: false, fetchedAt: cached.fetchedAt }));
  }, [key]);

  const refresh = useCallback(async () => {
    if (!key) return;
    setState((s) => ({ ...s, refreshing: true }));
    const result = await fetcherRef.current();
    if (result.ok) {
      await writeCache(key, result.data);
      setState((s) => ({ ...s, offline: false, notFound: null, error: null }));
      await readLocal();
    } else if (result.kind === 'offline') {
      setState((s) => ({ ...s, offline: true }));
    } else if (result.kind === 'notFound') {
      setState((s) => ({ ...s, offline: false, notFound: result.message, data: undefined }));
    } else {
      setState((s) => ({ ...s, offline: false, error: result.message }));
    }
    setState((s) => ({ ...s, loading: false, refreshing: false }));
  }, [key, readLocal]);

  useEffect(() => {
    if (!key) return;
    readLocal().then(refresh);
    const unsubscribers = [
      subscribe(key, readLocal),
      subscribe(OUTBOX_KEY, readLocal),
      subscribe(SYNCED_KEY, refresh),
    ];
    return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
  }, [key, readLocal, refresh]);

  return { ...state, refresh };
}
