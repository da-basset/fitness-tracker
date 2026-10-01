import type { SyncEvent } from '@/api/types';

import { getDb } from './db';
import type { OutboxRow } from './overlay';

export type { OutboxRow };
export { overlaySchedule, overlayWorkout } from './overlay';

export async function enqueue(row: OutboxRow) {
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO outbox (id, event, occurred_at, workout_id, tally_week_id, tally_delta) VALUES (?, ?, ?, ?, ?, ?)',
    row.event.id,
    JSON.stringify(row.event),
    row.event.occurred_at,
    row.workoutId,
    row.tallyWeekId,
    row.tallyDelta
  );
}

export async function pendingEvents(limit = 10_000): Promise<OutboxRow[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<{
    event: string;
    workout_id: number;
    tally_week_id: number | null;
    tally_delta: number;
  }>(
    'SELECT event, workout_id, tally_week_id, tally_delta FROM outbox ORDER BY occurred_at, rowid LIMIT ?',
    limit
  );
  return rows.map((row) => ({
    event: JSON.parse(row.event) as SyncEvent,
    workoutId: row.workout_id,
    tallyWeekId: row.tally_week_id,
    tallyDelta: row.tally_delta,
  }));
}

export async function pendingCount() {
  const db = await getDb();
  const row = await db.getFirstAsync<{ n: number }>('SELECT COUNT(*) AS n FROM outbox');
  return row?.n ?? 0;
}

export async function removeEvents(ids: string[]) {
  if (ids.length === 0) return;
  const db = await getDb();
  await db.runAsync(`DELETE FROM outbox WHERE id IN (${ids.map(() => '?').join(',')})`, ...ids);
}
