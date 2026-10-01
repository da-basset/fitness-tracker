import * as SQLite from 'expo-sqlite';

// Local store for offline use:
// - cache: last good API response per key (schedule, workout per day, me...)
// - outbox: completion changes waiting for POST /api/v1/sync/
let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

export function getDb() {
  dbPromise ??= SQLite.openDatabaseAsync('fitness-tracker.db').then(async (db) => {
    await migrate(db);
    return db;
  });
  return dbPromise;
}

const MIGRATIONS = [
  `CREATE TABLE cache (
     key TEXT PRIMARY KEY NOT NULL,
     json TEXT NOT NULL,
     fetched_at TEXT NOT NULL
   );
   CREATE TABLE outbox (
     id TEXT PRIMARY KEY NOT NULL,
     event TEXT NOT NULL,
     occurred_at TEXT NOT NULL,
     workout_id INTEGER NOT NULL,
     tally_week_id INTEGER,
     tally_delta INTEGER NOT NULL DEFAULT 0
   );`,
];

async function migrate(db: SQLite.SQLiteDatabase) {
  await db.execAsync('PRAGMA journal_mode = WAL');
  const row = await db.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  const version = row?.user_version ?? 0;
  for (let next = version; next < MIGRATIONS.length; next++) {
    await db.withTransactionAsync(async () => {
      await db.execAsync(MIGRATIONS[next]);
      await db.execAsync(`PRAGMA user_version = ${next + 1}`);
    });
  }
}

export async function readCache<T>(key: string): Promise<{ data: T; fetchedAt: string } | null> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ json: string; fetched_at: string }>(
    'SELECT json, fetched_at FROM cache WHERE key = ?',
    key
  );
  return row ? { data: JSON.parse(row.json) as T, fetchedAt: row.fetched_at } : null;
}

export async function writeCache(key: string, data: unknown) {
  const db = await getDb();
  await db.runAsync(
    'INSERT OR REPLACE INTO cache (key, json, fetched_at) VALUES (?, ?, ?)',
    key,
    JSON.stringify(data),
    new Date().toISOString()
  );
}

/** Forget everything on sign-out so the next user never sees it. */
export async function clearLocalData() {
  const db = await getDb();
  await db.execAsync('DELETE FROM cache; DELETE FROM outbox;');
}
