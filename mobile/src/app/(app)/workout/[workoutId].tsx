import * as Haptics from 'expo-haptics';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { ClientExercise, ClientWorkout, Segment } from '@/api/types';
import { SEGMENTS } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import {
  Banner,
  Button,
  Card,
  EmptyState,
  Icon,
  Loading,
  ResourceStatus,
  Screen,
  Section,
  useWorkoutColor,
} from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { formatDuration, formatLongDate, localToday } from '@/data/dates';
import { overlayWorkout } from '@/data/outbox';
import { fetchWorkout, toggleSet, toggleWorkoutComplete, workoutKey } from '@/data/training';
import { useResource } from '@/data/use-resource';
import { useTheme } from '@/hooks/use-theme';

export default function WorkoutScreen() {
  const params = useLocalSearchParams<{ workoutId: string; weekId?: string }>();
  const workoutId = Number(params.workoutId);
  const weekId = params.weekId ? Number(params.weekId) : null;
  // Check-offs always land on today's date on this phone.
  const [date] = useState(localToday);
  const workout = useResource<ClientWorkout>(
    workoutKey(workoutId, date),
    () => fetchWorkout(workoutId, date),
    overlayWorkout
  );
  const [rest, setRest] = useState<{ endsAt: number; total: number } | null>(null);
  const accent = useWorkoutColor(workout.data?.color);
  const data = workout.data;

  async function onToggleSet(exercise: ClientExercise, setNumber: number) {
    if (!data) return;
    Haptics.selectionAsync();
    const nowDone = await toggleSet(data, exercise, setNumber);
    if (nowDone && exercise.rest_seconds) {
      setRest({ endsAt: Date.now() + exercise.rest_seconds * 1000, total: exercise.rest_seconds });
    }
  }

  async function onToggleComplete() {
    if (!data || weekId == null) return;
    const completed = await toggleWorkoutComplete(data, weekId);
    if (completed) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  }

  if (!data) {
    return (
      <Screen refreshing={workout.refreshing} onRefresh={workout.refresh}>
        <Stack.Screen options={{ title: 'Workout' }} />
        {workout.loading ? (
          <Loading />
        ) : workout.notFound ? (
          <EmptyState title="Workout not found" message="It may have been removed from your plan." />
        ) : (
          <ResourceStatus offline={workout.offline} error={workout.error} fetchedAt={null} hasData={false} />
        )}
      </Screen>
    );
  }

  const bySegment = SEGMENTS.map((segment) => ({
    segment,
    exercises: data.exercises.filter((e) => e.segment === segment),
  })).filter((group) => group.exercises.length > 0);

  return (
    <View style={{ flex: 1 }}>
      <Stack.Screen options={{ title: data.name }} />
      <Screen refreshing={workout.refreshing} onRefresh={workout.refresh} contentStyle={rest ? styles.roomForTimer : null}>
        <View style={styles.header}>
          <View style={[styles.stripe, { backgroundColor: accent }]} />
          <View style={{ flex: 1, gap: 2 }}>
            {data.sub ? <ThemedText type="smallBold">{data.sub}</ThemedText> : null}
            <ThemedText type="small" themeColor="textSecondary">
              Logging for {formatLongDate(data.date)}
            </ThemedText>
          </View>
        </View>
        {data.flavor ? <Banner>{data.flavor}</Banner> : null}
        <ResourceStatus offline={workout.offline} error={workout.error} fetchedAt={workout.fetchedAt} hasData />

        {bySegment.length === 0 && <EmptyState title="No exercises yet" message="Your trainer hasn't added any." />}
        {bySegment.map((group) => (
          <Section key={group.segment} title={segmentTitle(group.segment)}>
            {group.exercises.map((exercise) => (
              <ExerciseCard key={exercise.id} exercise={exercise} accent={accent} onToggle={onToggleSet} />
            ))}
          </Section>
        ))}

        {weekId == null ? (
          <Banner>Open this workout from the Today tab to mark it complete.</Banner>
        ) : data.workout_completed ? (
          <Card style={styles.doneCard}>
            <Icon name="checkmark.seal.fill" size={28} color={accent} />
            <ThemedText type="smallBold">Workout complete</ThemedText>
            <Button title="Undo" variant="plain" compact onPress={onToggleComplete} />
          </Card>
        ) : (
          <Button title="Mark workout complete" onPress={onToggleComplete} icon="checkmark" />
        )}
      </Screen>
      {rest && <RestTimer {...rest} onDone={() => setRest(null)} onAdd={(s) => setRest({ ...rest, endsAt: rest.endsAt + s * 1000, total: rest.total + s })} />}
    </View>
  );
}

function segmentTitle(segment: Segment) {
  return segment === 'Main' ? 'Main lifts' : segment;
}

function ExerciseCard({
  exercise,
  accent,
  onToggle,
}: {
  exercise: ClientExercise;
  accent: string;
  onToggle: (exercise: ClientExercise, setNumber: number) => void;
}) {
  const theme = useTheme();
  const sets = exercise.sets_count ?? 1;
  const done = new Set(exercise.completed_set_numbers);
  const details = [
    exercise.sets_count ? `${exercise.sets_count} × ${exercise.reps_text || '—'}` : exercise.reps_text,
    exercise.time_text,
    exercise.rest_seconds ? `Rest ${restLabel(exercise.rest_seconds)}` : '',
  ].filter(Boolean);

  return (
    <Card>
      <ThemedText type="smallBold">{exercise.name}</ThemedText>
      {details.length > 0 && (
        <ThemedText type="small" themeColor="textSecondary">
          {details.join(' · ')}
        </ThemedText>
      )}
      <View style={styles.sets}>
        {Array.from({ length: sets }, (_, i) => i + 1).map((n) => {
          const checked = done.has(n);
          const label = exercise.sets_count ? `Set ${n}` : 'Done';
          return (
            <Pressable
              key={n}
              onPress={() => onToggle(exercise, n)}
              accessibilityRole="checkbox"
              accessibilityState={{ checked }}
              accessibilityLabel={`${exercise.name} ${label}`}
              hitSlop={6}
              style={[
                styles.set,
                exercise.sets_count ? null : styles.setWide,
                { borderColor: checked ? accent : theme.border, backgroundColor: checked ? accent : 'transparent' },
              ]}>
              {checked ? (
                <Icon name="checkmark" size={16} color={theme.background} />
              ) : (
                <ThemedText type="smallBold" themeColor="textSecondary">
                  {exercise.sets_count ? n : label}
                </ThemedText>
              )}
            </Pressable>
          );
        })}
      </View>
    </Card>
  );
}

function restLabel(seconds: number) {
  return seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds} sec`;
}

function RestTimer({
  endsAt,
  total,
  onDone,
  onAdd,
}: {
  endsAt: number;
  total: number;
  onDone: () => void;
  onAdd: (seconds: number) => void;
}) {
  const theme = useTheme();
  const [now, setNow] = useState(Date.now);
  const remaining = Math.max(0, Math.ceil((endsAt - now) / 1000));

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    if (remaining > 0) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    const hide = setTimeout(onDone, 2500);
    return () => clearTimeout(hide);
  }, [remaining, onDone]);

  return (
    <View
      style={[styles.timer, { backgroundColor: theme.backgroundElement, borderColor: theme.border }]}
      accessibilityLiveRegion="polite">
      <View style={{ flex: 1 }}>
        <ThemedText type="small" themeColor="textSecondary">
          {remaining > 0 ? `Rest · ${formatDuration(total)}` : 'Rest over'}
        </ThemedText>
        <ThemedText type="subtitle" style={{ fontVariant: ['tabular-nums'] }}>
          {remaining > 0 ? formatDuration(remaining) : 'Go'}
        </ThemedText>
      </View>
      <Button title="+30s" variant="secondary" compact onPress={() => onAdd(30)} />
      <Button title="Skip" variant="plain" compact onPress={onDone} />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', gap: Spacing.three, alignItems: 'center' },
  stripe: { width: 6, alignSelf: 'stretch', borderRadius: 3 },
  sets: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
  set: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  setWide: { width: 88 },
  doneCard: { alignItems: 'center' },
  roomForTimer: { paddingBottom: 140 },
  timer: {
    position: 'absolute',
    left: Spacing.three,
    right: Spacing.three,
    bottom: Spacing.five,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    padding: Spacing.three,
    borderRadius: Spacing.four,
    borderWidth: StyleSheet.hairlineWidth,
  },
});
