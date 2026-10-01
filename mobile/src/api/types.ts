import type { components } from './schema';

type Schemas = components['schemas'];

export type Me = Schemas['Me'];
export type Role = Schemas['RolesEnum'];
export type Schedule = Schemas['Schedule'];
export type SchedulePhase = Schemas['SchedulePhase'];
export type ScheduleWeek = Schemas['ScheduleWeek'];
export type ScheduleDay = Schemas['ScheduleDay'];
export type Weekday = Schemas['WeekdayEnum'];
export type WorkoutSummary = Schemas['WorkoutSummary'];
export type ClientWorkout = Schemas['ClientWorkout'];
export type ClientExercise = Schemas['ClientExercise'];
export type WeekTally = Schemas['WeekTally'];
export type Note = Schemas['Note'];
export type SyncResult = Schemas['SyncResult'];

export type Trainer = Schemas['Trainer'];
export type ClientSummary = Schemas['ClientSummary'];
export type ClientDetail = Schemas['ClientDetail'];
export type Assignment = Schemas['Assignment'];
export type PlanSummary = Schemas['PlanSummary'];
export type PlanDetail = Schemas['PlanDetail'];
export type Workout = Schemas['WorkoutDetail'];
/** A workout without its exercises, as create/update return it. */
export type WorkoutFields = Schemas['Workout'];
export type Exercise = Schemas['Exercise'];
export type Phase = Schemas['Phase'];
export type Week = Schemas['Week'];
export type Nutrient = Schemas['Nutrient'];
export type Supplement = Schemas['Supplement'];
export type WorkoutColor = Schemas['ColorEnum'];
export type Segment = Schemas['SegmentEnum'];
export type AccountCreate = Schemas['AccountCreateRequest'];

export const WEEKDAYS: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const SEGMENTS: Segment[] = ['Main', 'Core', 'Cardio', 'Stretch'];
export const WORKOUT_COLORS: WorkoutColor[] = ['red', 'blue', 'green', 'amber', 'violet', 'teal', 'rose'];

/** One queued change for POST /api/v1/sync/ (validated per event server-side). */
export type SyncEvent =
  | {
      id: string;
      type: 'set_completed' | 'set_cleared';
      log_date: string;
      occurred_at: string;
      exercise_id: number;
      set_number: number;
    }
  | {
      id: string;
      type: 'workout_completed' | 'workout_cleared';
      log_date: string;
      occurred_at: string;
      workout_id: number;
      week_id: number | null;
      started_at?: string | null;
      ended_at?: string | null;
    };
