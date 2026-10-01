import type { ClientWorkout, Schedule, SyncEvent } from '@/api/types';

import { weekBounds } from './dates';

/** A queued change plus what the app needs to show it before it syncs. */
export type OutboxRow = {
  event: SyncEvent;
  workoutId: number;
  /** Week whose tally this change moves, and by how much (+1/-1). */
  tallyWeekId: number | null;
  tallyDelta: number;
};

// Show queued changes on top of the last server response.

export function overlayWorkout(workout: ClientWorkout, rows: OutboxRow[]): ClientWorkout {
  const mine = rows.filter((row) => row.workoutId === workout.id && row.event.log_date === workout.date);
  if (mine.length === 0) return workout;
  const sets = new Map(workout.exercises.map((e) => [e.id, new Set(e.completed_set_numbers)]));
  let completed = workout.workout_completed;
  let startedAt = workout.started_at;
  let endedAt = workout.ended_at;
  for (const { event } of mine) {
    if (event.type === 'set_completed') sets.get(event.exercise_id)?.add(event.set_number);
    else if (event.type === 'set_cleared') sets.get(event.exercise_id)?.delete(event.set_number);
    else if (event.type === 'workout_completed') {
      completed = true;
      startedAt = event.started_at ?? startedAt;
      endedAt = event.ended_at ?? endedAt;
    } else completed = false;
  }
  return {
    ...workout,
    workout_completed: completed,
    started_at: startedAt,
    ended_at: endedAt,
    exercises: workout.exercises.map((e) => ({
      ...e,
      completed_set_numbers: [...(sets.get(e.id) ?? [])].sort((a, b) => a - b),
    })),
  };
}

export function overlaySchedule(schedule: Schedule, rows: OutboxRow[]): Schedule {
  const { start, end } = weekBounds(schedule.date);
  const deltas = new Map<number, number>();
  for (const row of rows) {
    const date = row.event.log_date;
    if (row.tallyWeekId == null || !row.tallyDelta || date < start || date > end) continue;
    deltas.set(row.tallyWeekId, (deltas.get(row.tallyWeekId) ?? 0) + row.tallyDelta);
  }
  if (deltas.size === 0) return schedule;
  return {
    ...schedule,
    phases: schedule.phases.map((phase) => ({
      ...phase,
      weeks: phase.weeks.map((week) => {
        const delta = deltas.get(week.id);
        if (!delta) return week;
        const completed = Math.max(0, week.week_tally.completed + delta);
        return {
          ...week,
          week_tally: {
            ...week.week_tally,
            completed,
            week_complete: week.week_tally.total > 0 && completed >= week.week_tally.total,
          },
        };
      }),
    })),
  };
}
