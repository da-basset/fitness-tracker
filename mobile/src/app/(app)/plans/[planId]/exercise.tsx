import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api/client';
import { SEGMENTS, type Exercise, type Segment } from '@/api/types';
import { confirmDelete, useSubmit } from '@/components/forms';
import { ThemedText } from '@/components/themed-text';
import { Banner, Button, Choice, Field, Screen, Section } from '@/components/ui';
import { revalidatePlan, usePlan } from '@/data/manage';
import { call } from '@/data/request';

/** Create (no exerciseId) or edit one exercise row in a workout. */
export default function ExerciseScreen() {
  const params = useLocalSearchParams<{ planId: string; workoutId: string; exerciseId?: string }>();
  const planId = Number(params.planId);
  const workoutId = Number(params.workoutId);
  const exerciseId = params.exerciseId ? Number(params.exerciseId) : null;
  const plan = usePlan(planId);
  const existing = plan.data?.workouts.find((w) => w.id === workoutId)?.exercises.find((e) => e.id === exerciseId);

  if (exerciseId != null && !existing) return <Screen />;
  return <ExerciseForm planId={planId} workoutId={workoutId} existing={existing} />;
}

function ExerciseForm({ planId, workoutId, existing }: { planId: number; workoutId: number; existing?: Exercise }) {
  const [form, setForm] = useState({
    name: existing?.name ?? '',
    segment: (existing?.segment ?? 'Main') as Segment,
    sets_count: existing?.sets_count?.toString() ?? '',
    reps_text: existing?.reps_text ?? '',
    rest_seconds: existing?.rest_seconds?.toString() ?? '',
    time_text: existing?.time_text ?? '',
  });
  const { busy, fields, message, run } = useSubmit();
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  function body() {
    return {
      name: form.name.trim(),
      segment: form.segment,
      sets_count: form.sets_count ? Number(form.sets_count) : null,
      reps_text: form.reps_text.trim(),
      rest_seconds: form.rest_seconds ? Number(form.rest_seconds) : null,
      time_text: form.time_text.trim(),
    };
  }

  async function done() {
    await revalidatePlan(planId);
    router.back();
  }

  function save() {
    run(
      () =>
        existing
          ? call<Exercise>(
              api.PATCH('/api/v1/plans/{plan_id}/exercises/{exercise_id}/', {
                params: { path: { plan_id: planId, exercise_id: existing.id } },
                body: body(),
              })
            )
          : call<Exercise>(
              api.POST('/api/v1/plans/{plan_id}/workouts/{workout_id}/exercises/', {
                params: { path: { plan_id: planId, workout_id: workoutId } },
                body: body(),
              })
            ),
      done
    );
  }

  function remove() {
    if (!existing) return;
    confirmDelete(`"${existing.name}"`, 'It disappears from this workout for the client.', () =>
      run(
        () =>
          call(
            api.DELETE('/api/v1/plans/{plan_id}/exercises/{exercise_id}/', {
              params: { path: { plan_id: planId, exercise_id: existing.id } },
            })
          ),
        done
      )
    );
  }

  const numeric = (value: string) => value.replace(/[^0-9]/g, '');

  return (
    <Screen>
      <Stack.Screen options={{ title: existing ? 'Edit exercise' : 'New exercise' }} />
      {message && !Object.keys(fields).length ? <Banner tone="error">{message}</Banner> : null}
      <Field label="Name" value={form.name} onChangeText={set('name')} placeholder="e.g. Bench press" error={fields.name} />
      <Section>
        <ThemedText type="smallBold">Segment</ThemedText>
        <Choice options={SEGMENTS.map((s) => ({ value: s, label: s }))} value={form.segment} onChange={(segment) => setForm({ ...form, segment })} />
        {fields.segment ? <Banner tone="error">{fields.segment}</Banner> : null}
      </Section>
      <Field
        label="Sets"
        value={form.sets_count}
        onChangeText={(v) => set('sets_count')(numeric(v))}
        keyboardType="number-pad"
        placeholder="Leave empty for a single checkbox (cardio, stretch)"
        error={fields.sets_count}
        hint="1 to 20. Each set gets its own checkbox."
      />
      <Field label="Reps" value={form.reps_text} onChangeText={set('reps_text')} placeholder="e.g. 8-10" error={fields.reps_text} />
      <Field
        label="Rest (seconds)"
        value={form.rest_seconds}
        onChangeText={(v) => set('rest_seconds')(numeric(v))}
        keyboardType="number-pad"
        placeholder="e.g. 90"
        error={fields.rest_seconds}
        hint="Starts the rest timer after each set."
      />
      <Field label="Time" value={form.time_text} onChangeText={set('time_text')} placeholder="e.g. 20 min" error={fields.time_text} />
      <Button title={existing ? 'Save exercise' : 'Add exercise'} onPress={save} busy={busy} disabled={!form.name.trim()} />
      {existing && <Button title="Delete exercise" variant="destructive" onPress={remove} />}
    </Screen>
  );
}
