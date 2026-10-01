import { router } from 'expo-router';
import { useState } from 'react';

import { Button, Choice, EmptyState, Loading, PageTitle, ResourceStatus, Row, Screen, Section } from '@/components/ui';
import { useLibrary, useTrainers } from '@/data/manage';
import { useMe } from '@/data/me';

/** The plan library: reusable templates you assign (as a copy) to clients. */
export default function PlansScreen() {
  const { data: me } = useMe();
  const trainers = useTrainers();
  const [picked, setPicked] = useState<number | null>(null);
  const trainerId = picked ?? me?.trainer_id ?? trainers.data?.[0]?.id ?? null;
  const library = useLibrary(trainerId);
  const templates = library.data ?? [];
  const showPicker = (trainers.data?.length ?? 0) > 1;

  return (
    <Screen
      refreshing={library.refreshing}
      onRefresh={() => {
        library.refresh();
        trainers.refresh();
      }}>
      <PageTitle title="Plan library" subtitle="Templates you can assign to clients" />
      {showPicker && trainerId != null && (
        <Section title="Trainer">
          <Choice
            options={trainers.data!.map((t) => ({ value: t.id, label: t.id === me?.trainer_id ? 'You' : t.name }))}
            value={trainerId}
            onChange={setPicked}
          />
        </Section>
      )}
      <ResourceStatus offline={library.offline} error={library.error} fetchedAt={library.fetchedAt} hasData={!!library.data} />
      {trainerId == null ? (
        trainers.loading ? (
          <Loading />
        ) : (
          <EmptyState title="No trainers yet" message="Add a trainer first; plans belong to a trainer." />
        )
      ) : (
        <>
          <Button
            title="New plan"
            icon="plus"
            variant="secondary"
            onPress={() => router.push({ pathname: '/plans/new', params: { trainerId } })}
          />
          {library.loading && !library.data ? (
            <Loading />
          ) : templates.length === 0 ? (
            <EmptyState title="No templates yet" message="Create a plan, build its workouts and phases, then assign it." />
          ) : (
            <Section title="Templates">
              {templates.map((plan) => (
                <Row
                  key={plan.id}
                  title={plan.name}
                  detail={plan.description || null}
                  onPress={() => router.push({ pathname: '/plans/[planId]', params: { planId: plan.id } })}
                />
              ))}
            </Section>
          )}
        </>
      )}
    </Screen>
  );
}
