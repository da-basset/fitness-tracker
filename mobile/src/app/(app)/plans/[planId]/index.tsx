import { router, Stack, useLocalSearchParams } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import type { Phase, PlanDetail, WorkoutFields } from '@/api/types';
import { confirmDelete, useSubmit } from '@/components/forms';
import { ThemedText } from '@/components/themed-text';
import {
  Banner,
  Button,
  Card,
  ColorDot,
  EmptyState,
  Loading,
  ResourceStatus,
  Row,
  Screen,
  Section,
} from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { revalidateLibrary, revalidatePlan, usePlan } from '@/data/manage';
import { call } from '@/data/request';

export default function PlanScreen() {
  const planId = Number(useLocalSearchParams<{ planId: string }>().planId);
  const plan = usePlan(planId);
  const { busy, message, run } = useSubmit();
  const data = plan.data;

  if (!data) {
    return (
      <Screen refreshing={plan.refreshing} onRefresh={plan.refresh}>
        {plan.loading ? (
          <Loading />
        ) : plan.notFound ? (
          <EmptyState title="Plan not found" message="It may have been deleted, or you don't have access." />
        ) : (
          <ResourceStatus offline={plan.offline} error={plan.error} fetchedAt={null} hasData={false} />
        )}
      </Screen>
    );
  }

  const path = { params: { path: { plan_id: planId } } };

  function addWorkout() {
    run(
      () => call<WorkoutFields>(api.POST('/api/v1/plans/{plan_id}/workouts/', { ...path, body: { name: 'New workout' } })),
      async (workout) => {
        await revalidatePlan(planId);
        router.push({ pathname: '/plans/[planId]/workouts/[workoutId]', params: { planId, workoutId: workout.id } });
      }
    );
  }

  function addPhase() {
    run(
      () => call<Phase>(api.POST('/api/v1/plans/{plan_id}/phases/', { ...path, body: { title: 'New phase' } })),
      async (phase) => {
        await revalidatePlan(planId);
        router.push({ pathname: '/plans/[planId]/phases/[phaseId]', params: { planId, phaseId: phase.id } });
      }
    );
  }

  function deletePlan() {
    confirmDelete(`"${data!.name}"`, 'This permanently removes its workouts, phases and exercises.', () =>
      run(
        () => call(api.DELETE('/api/v1/plans/{plan_id}/', path)),
        async () => {
          await revalidateLibrary(data!.trainer_id);
          router.back();
        }
      )
    );
  }

  return (
    <Screen refreshing={plan.refreshing} onRefresh={plan.refresh}>
      <Stack.Screen options={{ title: data.name }} />
      <ResourceStatus offline={plan.offline} error={plan.error} fetchedAt={plan.fetchedAt} hasData />
      {message ? <Banner tone="error">{message}</Banner> : null}

      <Card>
        <ThemedText type="smallBold">{data.name}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {statusLine(data)}
        </ThemedText>
        {data.description ? <ThemedText type="small">{data.description}</ThemedText> : null}
        <View style={styles.actions}>
          {data.is_template && data.can_manage && (
            <Button
              title="Assign to client"
              compact
              onPress={() => router.push({ pathname: '/plans/[planId]/assign', params: { planId } })}
            />
          )}
          <Button
            title="Client view"
            variant="secondary"
            compact
            onPress={() => router.push({ pathname: '/plans/[planId]/preview', params: { planId } })}
          />
          {data.is_template && data.can_manage && (
            <Button title="Delete" variant="destructive" compact busy={busy} onPress={deletePlan} />
          )}
        </View>
      </Card>

      {!data.can_manage ? (
        <Banner>Only the plan&rsquo;s trainer or gym owner can edit it.</Banner>
      ) : (
        <>
          <Section title="Workouts">
            {data.workouts.map((workout) => (
              <Row
                key={workout.id}
                leading={<ColorDot color={workout.color} />}
                title={workout.name}
                detail={[workout.sub, `${workout.exercises.length} exercises`].filter(Boolean).join(' · ')}
                onPress={() =>
                  router.push({ pathname: '/plans/[planId]/workouts/[workoutId]', params: { planId, workoutId: workout.id } })
                }
              />
            ))}
            <Button title="Add workout" icon="plus" variant="secondary" busy={busy} onPress={addWorkout} />
          </Section>

          <Section title={`Phases (${data.phases.length} of ${data.limits.max_phases})`}>
            {data.phases.map((phase) => (
              <Row
                key={phase.id}
                title={`${phase.number}. ${phase.title}`}
                detail={phaseDetail(phase, data)}
                onPress={() =>
                  router.push({ pathname: '/plans/[planId]/phases/[phaseId]', params: { planId, phaseId: phase.id } })
                }
              />
            ))}
            <Button
              title="Add phase"
              icon="plus"
              variant="secondary"
              busy={busy}
              disabled={data.phases.length >= data.limits.max_phases}
              onPress={addPhase}
            />
          </Section>

          <NoteSection planId={planId} kind="nutrient" title="Nutrients" notes={data.nutrients} />
          <NoteSection planId={planId} kind="supplement" title="Supplements" notes={data.supplements} />
        </>
      )}
    </Screen>
  );
}

function statusLine(plan: PlanDetail) {
  if (plan.is_template) return 'Template in the plan library';
  const who = plan.owning_client?.name ?? 'a client';
  return plan.assignment?.is_active ? `Assigned to ${who}` : `Past plan of ${who}`;
}

function phaseDetail(phase: PlanDetail['phases'][number], plan: PlanDetail) {
  const weeks = phase.weeks;
  const range = weeks.length
    ? weeks.length === 1
      ? `Week ${weeks[0].number}`
      : `Weeks ${weeks[0].number}–${weeks[weeks.length - 1].number}`
    : 'No weeks';
  const names = new Map(plan.workouts.map((w) => [w.id, w.name]));
  const firstWeek = weeks[0];
  const days = firstWeek
    ? Object.values(firstWeek.days).filter((id): id is number => id != null && names.has(id)).length
    : 0;
  return `${range} · ${days} training days/week`;
}

function NoteSection({
  planId,
  kind,
  title,
  notes,
}: {
  planId: number;
  kind: 'nutrient' | 'supplement';
  title: string;
  notes: PlanDetail['nutrients'];
}) {
  return (
    <Section title={title}>
      {notes.map((note) => (
        <Row
          key={note.id}
          title={note.name}
          detail={[note.amount, note.timing].filter(Boolean).join(' · ') || null}
          onPress={() => router.push({ pathname: '/plans/[planId]/note', params: { planId, kind, id: note.id } })}
        />
      ))}
      <Button
        title={`Add ${kind}`}
        icon="plus"
        variant="secondary"
        onPress={() => router.push({ pathname: '/plans/[planId]/note', params: { planId, kind } })}
      />
    </Section>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
});
