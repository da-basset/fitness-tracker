import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { WEEKDAYS, type PlanDetail } from '@/api/types';
import { ThemedText } from '@/components/themed-text';
import {
  Banner,
  Card,
  Choice,
  ColorDot,
  EmptyState,
  Icon,
  Loading,
  ResourceStatus,
  Row,
  Screen,
  Section,
} from '@/components/ui';
import { usePlan } from '@/data/manage';

/**
 * Read-only "Client view": what the plan looks like to its client, without
 * checkboxes, so nothing tapped here lands in anyone's logged history. Also
 * used for past plans.
 */
export default function PlanPreviewScreen() {
  const planId = Number(useLocalSearchParams<{ planId: string }>().planId);
  const plan = usePlan(planId);
  const [weekId, setWeekId] = useState<number | null>(null);
  const [openDay, setOpenDay] = useState<string | null>(null);
  const data = plan.data;

  if (!data) {
    return (
      <Screen refreshing={plan.refreshing} onRefresh={plan.refresh}>
        {plan.loading ? <Loading /> : <EmptyState title="Plan not found" message="You may not have access to it." />}
      </Screen>
    );
  }

  const weeks = data.phases.flatMap((phase) => phase.weeks.map((week) => ({ phase, week })));
  const current = weeks.find((entry) => entry.week.id === weekId) ?? weeks[0];
  const workouts = new Map(data.workouts.map((w) => [w.id, w]));

  return (
    <Screen refreshing={plan.refreshing} onRefresh={plan.refresh}>
      <Stack.Screen options={{ title: data.name }} />
      <Banner>Read-only preview. Nothing here is logged.</Banner>
      <ResourceStatus offline={plan.offline} error={plan.error} fetchedAt={plan.fetchedAt} hasData />

      {!current ? (
        <EmptyState title="No phases yet" />
      ) : (
        <>
          <Section title="Phase">
            <Choice
              options={data.phases.map((p) => ({ value: p.id, label: `${p.number}. ${p.title}` }))}
              value={current.phase.id}
              onChange={(phaseId) => setWeekId(data.phases.find((p) => p.id === phaseId)?.weeks[0]?.id ?? null)}
            />
          </Section>
          {current.phase.weeks.length > 1 && (
            <Section title="Week">
              <Choice
                options={current.phase.weeks.map((w) => ({ value: w.id, label: w.label }))}
                value={current.week.id}
                onChange={setWeekId}
              />
            </Section>
          )}
          <Section title={current.week.label}>
            {WEEKDAYS.map((weekday) => {
              const workoutId = current.week.days[weekday];
              const workout = workoutId != null ? workouts.get(workoutId) : undefined;
              const key = `${current.week.id}:${weekday}`;
              if (!workout) {
                return <Row key={weekday} leading={<Icon name="moon.zzz" size={12} />} title={`${weekday} · Rest`} />;
              }
              return (
                <Section key={weekday}>
                  <Row
                    leading={<ColorDot color={workout.color} />}
                    title={`${weekday} · ${workout.name}`}
                    detail={workout.sub || null}
                    onPress={() => setOpenDay(openDay === key ? null : key)}
                    accessory={<Icon name={openDay === key ? 'chevron.up' : 'chevron.down'} size={12} />}
                  />
                  {openDay === key && <WorkoutPreview workout={workout} />}
                </Section>
              );
            })}
          </Section>
        </>
      )}

      {(data.nutrients.length > 0 || data.supplements.length > 0) && (
        <Section title="Nutrition">
          {[...data.nutrients, ...data.supplements].map((note) => (
            <Row key={`${note.id}-${note.name}`} title={note.name} detail={[note.amount, note.timing].filter(Boolean).join(' · ') || null} />
          ))}
        </Section>
      )}
    </Screen>
  );
}

function WorkoutPreview({ workout }: { workout: PlanDetail['workouts'][number] }) {
  return (
    <Card>
      {workout.flavor ? (
        <ThemedText type="small" themeColor="textSecondary">
          {workout.flavor}
        </ThemedText>
      ) : null}
      {workout.exercises.length === 0 ? (
        <ThemedText type="small" themeColor="textSecondary">
          No exercises yet.
        </ThemedText>
      ) : (
        workout.exercises.map((exercise) => (
          <ThemedText key={exercise.id} type="small">
            {exercise.name}
            <ThemedText type="small" themeColor="textSecondary">
              {'  '}
              {[
                exercise.sets_count ? `${exercise.sets_count} × ${exercise.reps_text || '—'}` : exercise.reps_text,
                exercise.time_text,
              ]
                .filter(Boolean)
                .join(' · ')}
            </ThemedText>
          </ThemedText>
        ))
      )}
    </Card>
  );
}
