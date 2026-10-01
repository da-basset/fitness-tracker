import * as Crypto from 'expo-crypto';

import { api } from '@/api/client';
import type { ClientExercise, ClientWorkout, Schedule } from '@/api/types';

import { notify, OUTBOX_KEY } from './bus';
import { localToday } from './dates';
import { readCache, writeCache } from './db';
import { SCHEDULE_KEY, startedKey, workoutKey } from './keys';
import { enqueue } from './outbox';
import { call } from './request';
import { flush } from './sync';

export { SCHEDULE_KEY, workoutKey };

export function fetchSchedule() {
  return call<Schedule>(api.GET('/api/v1/plans/active/schedule/', { params: { query: { date: localToday() } } }));
}

export function fetchWorkout(workoutId: number, date: string) {
  return call<ClientWorkout>(
    api.GET('/api/v1/workouts/{workout_id}/', { params: { path: { workout_id: workoutId }, query: { date } } })
  );
}

// Every check-off goes through the outbox, online or not: one write path,
// instant UI, and the server orders changes by when they were tapped.

async function record(row: Parameters<typeof enqueue>[0]) {
  await enqueue(row);
  notify(OUTBOX_KEY);
  flush();
}

/** `workout` is what's on screen (server copy with pending changes applied). */
export async function toggleSet(workout: ClientWorkout, exercise: ClientExercise, setNumber: number) {
  const done = exercise.completed_set_numbers.includes(setNumber);
  const now = new Date().toISOString();
  if (!done) {
    // Remember when the workout started, for Apple Health later.
    const key = startedKey(workout.id, workout.date);
    if (!(await readCache<string>(key))) await writeCache(key, now);
  }
  await record({
    event: {
      id: Crypto.randomUUID(),
      type: done ? 'set_cleared' : 'set_completed',
      log_date: workout.date,
      occurred_at: now,
      exercise_id: exercise.id,
      set_number: setNumber,
    },
    workoutId: workout.id,
    tallyWeekId: null,
    tallyDelta: 0,
  });
  return !done;
}

export async function toggleWorkoutComplete(workout: ClientWorkout, weekId: number) {
  const completing = !workout.workout_completed;
  const now = new Date().toISOString();
  const started = completing ? (await readCache<string>(startedKey(workout.id, workout.date)))?.data : null;
  await record({
    event: completing
      ? {
          id: Crypto.randomUUID(),
          type: 'workout_completed',
          log_date: workout.date,
          occurred_at: now,
          workout_id: workout.id,
          week_id: weekId,
          started_at: started ?? null,
          ended_at: now,
        }
      : {
          id: Crypto.randomUUID(),
          type: 'workout_cleared',
          log_date: workout.date,
          occurred_at: now,
          workout_id: workout.id,
          week_id: weekId,
        },
    workoutId: workout.id,
    tallyWeekId: weekId,
    tallyDelta: completing ? 1 : -1,
  });
  return completing;
}
