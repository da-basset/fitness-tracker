import * as Network from 'expo-network';
import { AppState } from 'react-native';

import { api } from '@/api/client';
import type { ClientWorkout, Schedule } from '@/api/types';

import { notify, OUTBOX_KEY } from './bus';
import { readCache, writeCache } from './db';
import { overlaySchedule, overlayWorkout, pendingEvents, removeEvents, type OutboxRow } from './outbox';
import { call } from './request';
import { SCHEDULE_KEY, workoutKey } from './keys';
import { SYNCED_KEY } from './use-resource';

const BATCH = 500; // the server's per-request limit

let flushing: Promise<void> | null = null;

/** Send queued changes to the server. Safe to call any time, as often as you like. */
export function flush() {
  flushing ??= doFlush().finally(() => {
    flushing = null;
  });
  return flushing;
}

async function doFlush() {
  let sent = false;
  for (;;) {
    const rows = await pendingEvents(BATCH);
    if (rows.length === 0) break;
    const result = await call(api.POST('/api/v1/sync/', { body: { events: rows.map((row) => row.event) } }));
    // Offline or a server error: keep everything queued and try again later.
    if (!result.ok) break;
    const accepted = new Set(
      result.data.results.filter((r) => r.status === 'applied' || r.status === 'duplicate').map((r) => r.id)
    );
    // Fold accepted changes into the cached server copies before dropping
    // them, so screens don't flicker back while they refetch.
    await foldIntoCache(rows.filter((row) => accepted.has(row.event.id)));
    // Every status means "done with this event"; stale/rejected ones are
    // corrected by the refetch below.
    await removeEvents(result.data.results.map((r) => r.id));
    sent = true;
    if (rows.length < BATCH) break;
  }
  if (sent) {
    notify(OUTBOX_KEY);
    notify(SYNCED_KEY);
  }
}

async function foldIntoCache(rows: OutboxRow[]) {
  if (rows.length === 0) return;
  const workoutKeys = new Set(rows.map((row) => workoutKey(row.workoutId, row.event.log_date)));
  for (const key of workoutKeys) {
    const cached = await readCache<ClientWorkout>(key);
    if (cached) await writeCache(key, overlayWorkout(cached.data, rows));
  }
  const schedule = await readCache<Schedule>(SCHEDULE_KEY);
  if (schedule) await writeCache(SCHEDULE_KEY, overlaySchedule(schedule.data, rows));
}

/** Flush now, whenever the app returns to the foreground, and on reconnect. */
export function startSync() {
  flush();
  const appState = AppState.addEventListener('change', (next) => {
    if (next === 'active') flush();
  });
  const network = Network.addNetworkStateListener((state) => {
    if (state.isConnected) flush();
  });
  return () => {
    appState.remove();
    network.remove();
  };
}
