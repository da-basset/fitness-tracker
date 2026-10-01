// Cache keys shared by the readers, the actions and the sync engine.
export const SCHEDULE_KEY = 'schedule';
export const ME_KEY = 'me';
export const OWNER_KEY = 'owner';

export function workoutKey(workoutId: number, date: string) {
  return `workout:${workoutId}:${date}`;
}

export function startedKey(workoutId: number, date: string) {
  return `started:${workoutId}:${date}`;
}
