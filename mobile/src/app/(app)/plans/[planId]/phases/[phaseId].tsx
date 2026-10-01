import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActionSheetIOS, Alert, Platform } from 'react-native';

import { api } from '@/api/client';
import { WEEKDAYS, type Phase, type PlanDetail, type Week, type Weekday } from '@/api/types';
import { confirmDelete, useSubmit } from '@/components/forms';
import { Banner, Button, Card, ColorDot, EmptyState, Field, Icon, Loading, Row, Screen, Section } from '@/components/ui';
import { revalidatePlan, usePlan } from '@/data/manage';
import { call } from '@/data/request';

export default function PhaseEditorScreen() {
  const params = useLocalSearchParams<{ planId: string; phaseId: string }>();
  const planId = Number(params.planId);
  const plan = usePlan(planId);
  const phase = plan.data?.phases.find((p) => p.id === Number(params.phaseId));

  if (!plan.data || !phase) {
    return <Screen>{plan.loading ? <Loading /> : <EmptyState title="Phase not found" message="It may have been deleted." />}</Screen>;
  }
  return <Editor key={phase.id} plan={plan.data} phase={phase} />;
}

function Editor({ plan, phase }: { plan: PlanDetail; phase: Phase }) {
  const planId = plan.id;
  const [form, setForm] = useState({ title: phase.title, note: phase.note, order: String(phase.order) });
  const save = useSubmit();
  const weeks = useSubmit();
  const dirty = form.title !== phase.title || form.note !== phase.note || form.order !== String(phase.order);
  const phasePath = { params: { path: { plan_id: planId, phase_id: phase.id } } };


  function saveDetails() {
    save.run(
      () =>
        call<Phase>(
          api.PATCH('/api/v1/plans/{plan_id}/phases/{phase_id}/', {
            ...phasePath,
            body: { title: form.title.trim(), note: form.note, order: Number(form.order) || phase.order },
          })
        ),
      () => revalidatePlan(planId)
    );
  }

  function removePhase() {
    confirmDelete(`the "${phase.title}" phase`, "Later phases' week numbers shift to fill the gap.", () =>
      save.run(
        () => call(api.DELETE('/api/v1/plans/{plan_id}/phases/{phase_id}/', phasePath)),
        async () => {
          await revalidatePlan(planId);
          router.back();
        }
      )
    );
  }

  function addWeek() {
    weeks.run(() => call<Week>(api.POST('/api/v1/plans/{plan_id}/phases/{phase_id}/weeks/', phasePath)), () => revalidatePlan(planId));
  }

  function removeWeek(week: Week) {
    confirmDelete(week.label, 'Later weeks shift down to fill the gap.', () =>
      weeks.run(
        () =>
          call(api.DELETE('/api/v1/plans/{plan_id}/weeks/{week_id}/', { params: { path: { plan_id: planId, week_id: week.id } } })),
        () => revalidatePlan(planId)
      )
    );
  }

  function setDay(week: Week, weekday: Weekday, workoutId: number | null) {
    weeks.run(
      () =>
        call<Week>(
          api.PATCH('/api/v1/plans/{plan_id}/weeks/{week_id}/', {
            params: { path: { plan_id: planId, week_id: week.id } },
            body: { days: { [weekday]: workoutId } },
          })
        ),
      () => revalidatePlan(planId)
    );
  }

  function pickWorkout(week: Week, weekday: Weekday) {
    const options = [...plan.workouts.map((w) => w.name), 'Rest day', 'Cancel'];
    const choose = (index: number) => {
      if (index < plan.workouts.length) setDay(week, weekday, plan.workouts[index].id);
      else if (index === plan.workouts.length) setDay(week, weekday, null);
    };
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        { title: `${week.label} · ${weekday}`, options, cancelButtonIndex: options.length - 1 },
        choose
      );
    } else {
      Alert.alert(`${week.label} · ${weekday}`, undefined, [
        ...options.slice(0, -1).map((text, index) => ({ text, onPress: () => choose(index) })),
        { text: 'Cancel', style: 'cancel' as const },
      ]);
    }
  }

  const workoutsById = new Map(plan.workouts.map((w) => [w.id, w]));
  const atWeekLimit = phase.weeks.length >= plan.limits.max_weeks_per_phase;

  return (
    <Screen>
      <Stack.Screen options={{ title: phase.title }} />
      {save.message ? <Banner tone="error">{save.message}</Banner> : null}

      <Section title="Details">
        <Field
          label="Title"
          value={form.title}
          onChangeText={(title) => setForm({ ...form, title })}
          placeholder="e.g. Ramp-In, Build, Deload"
          error={save.fields.title}
        />
        <Field
          label="Position"
          value={form.order}
          onChangeText={(order) => setForm({ ...form, order: order.replace(/[^0-9]/g, '') })}
          keyboardType="number-pad"
          hint="Phases are shown in this order."
          error={save.fields.order}
        />
        <Field
          label="Note for the client"
          value={form.note}
          onChangeText={(note) => setForm({ ...form, note })}
          multiline
          error={save.fields.note}
        />
        <Button title="Save details" onPress={saveDetails} busy={save.busy} disabled={!dirty || !form.title.trim()} />
      </Section>

      {weeks.message ? <Banner tone="error">{weeks.message}</Banner> : null}
      {plan.workouts.length === 0 && <Banner>Add workouts to this plan before scheduling days.</Banner>}

      {phase.weeks.map((week) => (
        <Section
          key={week.id}
          title={week.label}
          action={
            phase.weeks.length > 1 ? (
              <Button title="Remove" variant="plain" compact onPress={() => removeWeek(week)} />
            ) : undefined
          }>
          <Card style={{ padding: 0, gap: 0, overflow: 'hidden' }}>
            {WEEKDAYS.map((weekday) => {
              const workout = week.days[weekday] != null ? workoutsById.get(week.days[weekday]!) : undefined;
              return (
                <Row
                  key={weekday}
                  leading={workout ? <ColorDot color={workout.color} /> : <Icon name="moon.zzz" size={12} />}
                  title={`${weekday} · ${workout ? workout.name : 'Rest'}`}
                  disabled={weeks.busy || plan.workouts.length === 0}
                  onPress={() => pickWorkout(week, weekday)}
                  accessory={<Icon name="chevron.up.chevron.down" size={12} />}
                />
              );
            })}
          </Card>
        </Section>
      ))}

      <Button
        title={atWeekLimit ? `${plan.limits.max_weeks_per_phase} weeks is the limit` : 'Add week'}
        icon="plus"
        variant="secondary"
        disabled={atWeekLimit}
        busy={weeks.busy}
        onPress={addWeek}
      />
      <Button title="Delete phase" variant="destructive" onPress={removePhase} />
    </Screen>
  );
}
