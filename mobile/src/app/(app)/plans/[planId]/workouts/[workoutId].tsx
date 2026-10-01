import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import { WORKOUT_COLORS, type Exercise, type Workout, type WorkoutFields } from '@/api/types';
import { confirmDelete, useSubmit } from '@/components/forms';
import { ThemedText } from '@/components/themed-text';
import {
  Banner,
  Button,
  Choice,
  ColorDot,
  EmptyState,
  Field,
  Icon,
  Loading,
  Row,
  Screen,
  Section,
} from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { revalidatePlan, usePlan } from '@/data/manage';
import { call } from '@/data/request';
import { useTheme } from '@/hooks/use-theme';

export default function WorkoutEditorScreen() {
  const params = useLocalSearchParams<{ planId: string; workoutId: string }>();
  const planId = Number(params.planId);
  const workoutId = Number(params.workoutId);
  const plan = usePlan(planId);
  const workout = plan.data?.workouts.find((w) => w.id === workoutId);

  if (!workout) {
    return <Screen>{plan.loading ? <Loading /> : <EmptyState title="Workout not found" message="It may have been deleted." />}</Screen>;
  }
  return <Editor key={workout.id} planId={planId} workout={workout} />;
}

function Editor({ planId, workout }: { planId: number; workout: Workout }) {
  const [form, setForm] = useState({ name: workout.name, sub: workout.sub, flavor: workout.flavor, color: workout.color });
  const save = useSubmit();
  const order = useSubmit();
  const dirty =
    form.name !== workout.name || form.sub !== workout.sub || form.flavor !== workout.flavor || form.color !== workout.color;
  const path = { params: { path: { plan_id: planId, workout_id: workout.id } } };


  function saveDetails() {
    save.run(
      () => call<WorkoutFields>(api.PATCH('/api/v1/plans/{plan_id}/workouts/{workout_id}/', { ...path, body: form })),
      () => revalidatePlan(planId)
    );
  }

  function remove() {
    confirmDelete(
      `"${workout.name}"`,
      "This also removes every exercise in it and clears it from any day it's scheduled on.",
      () =>
        save.run(
          () => call(api.DELETE('/api/v1/plans/{plan_id}/workouts/{workout_id}/', path)),
          async () => {
            await revalidatePlan(planId);
            router.back();
          }
        )
    );
  }

  function move(index: number, delta: -1 | 1) {
    const ids = workout.exercises.map((e) => e.id);
    const target = index + delta;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    order.run(
      () =>
        call<Exercise[]>(
          api.POST('/api/v1/plans/{plan_id}/workouts/{workout_id}/exercises/reorder/', { ...path, body: { order: ids } })
        ),
      () => revalidatePlan(planId)
    );
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: workout.name }} />
      {save.message ? <Banner tone="error">{save.message}</Banner> : null}

      <Section title="Details">
        <Field label="Name" value={form.name} onChangeText={(name) => setForm({ ...form, name })} error={save.fields.name} />
        <Field
          label="Focus"
          value={form.sub}
          onChangeText={(sub) => setForm({ ...form, sub })}
          placeholder="e.g. Chest, Shoulders, Triceps"
          error={save.fields.sub}
        />
        <Field
          label="Tip"
          value={form.flavor}
          onChangeText={(flavor) => setForm({ ...form, flavor })}
          placeholder="Optional progression tip shown to the client"
          error={save.fields.flavor}
        />
        <ThemedText type="smallBold">Color</ThemedText>
        <Choice
          options={WORKOUT_COLORS.map((c) => ({ value: c, label: c }))}
          value={form.color}
          onChange={(color) => setForm({ ...form, color })}
          render={(option, selected) => (
            <View style={styles.colorOption}>
              <ColorDot color={option.value} size={16} />
              {selected && <Icon name="checkmark" size={12} />}
            </View>
          )}
        />
        <Button title="Save details" onPress={saveDetails} busy={save.busy} disabled={!dirty || !form.name.trim()} />
      </Section>

      <Section title={`Exercises (${workout.exercises.length})`}>
        {order.message ? <Banner tone="error">{order.message}</Banner> : null}
        {workout.exercises.map((exercise, index) => (
          <Row
            key={exercise.id}
            title={exercise.name}
            detail={exerciseSummary(exercise)}
            onPress={() =>
              router.push({
                pathname: '/plans/[planId]/exercise',
                params: { planId, workoutId: workout.id, exerciseId: exercise.id },
              })
            }
            accessory={
              <View style={styles.reorder}>
                <MoveButton label={`Move ${exercise.name} up`} icon="chevron.up" disabled={index === 0 || order.busy} onPress={() => move(index, -1)} />
                <MoveButton
                  label={`Move ${exercise.name} down`}
                  icon="chevron.down"
                  disabled={index === workout.exercises.length - 1 || order.busy}
                  onPress={() => move(index, 1)}
                />
              </View>
            }
          />
        ))}
        <Button
          title="Add exercise"
          icon="plus"
          variant="secondary"
          onPress={() => router.push({ pathname: '/plans/[planId]/exercise', params: { planId, workoutId: workout.id } })}
        />
      </Section>

      <Button title="Delete workout" variant="destructive" onPress={remove} />
    </Screen>
  );
}

function exerciseSummary(exercise: Exercise) {
  const parts = [
    exercise.segment,
    exercise.sets_count ? `${exercise.sets_count} × ${exercise.reps_text || '—'}` : exercise.reps_text,
    exercise.time_text,
    exercise.rest_seconds ? `rest ${exercise.rest_seconds}s` : '',
  ];
  return parts.filter(Boolean).join(' · ');
}

function MoveButton({
  label,
  icon,
  disabled,
  onPress,
}: {
  label: string;
  icon: 'chevron.up' | 'chevron.down';
  disabled: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={4}
      style={[styles.move, { backgroundColor: theme.backgroundSelected, opacity: disabled ? 0.3 : 1 }]}>
      <Icon name={icon} size={14} color={theme.text} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  colorOption: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  reorder: { flexDirection: 'row', gap: Spacing.one },
  move: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
});
