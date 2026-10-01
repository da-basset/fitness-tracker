import { router } from 'expo-router';

import { Button, EmptyState, Loading, PageTitle, ResourceStatus, Row, Screen, Section } from '@/components/ui';
import { useTrainers } from '@/data/manage';
import { useMe } from '@/data/me';

export default function TrainersScreen() {
  const trainers = useTrainers();
  const { data: me } = useMe();
  const list = trainers.data ?? [];

  return (
    <Screen refreshing={trainers.refreshing} onRefresh={trainers.refresh}>
      <PageTitle title="Trainers" subtitle="Accounts at your gym" />
      <ResourceStatus offline={trainers.offline} error={trainers.error} fetchedAt={trainers.fetchedAt} hasData={!!trainers.data} />
      <Button title="Add trainer" icon="person.badge.plus" variant="secondary" onPress={() => router.push('/trainers/new')} />
      {trainers.loading && !trainers.data ? (
        <Loading />
      ) : list.length === 0 ? (
        <EmptyState title="No trainers yet" message="Add a trainer to give them a login." />
      ) : (
        <Section>
          {list.map((trainer) => (
            <Row
              key={trainer.id}
              title={trainer.user_id === me?.id ? `${trainer.name} (you)` : trainer.name}
              detail={`@${trainer.username} · ${trainer.client_count} ${trainer.client_count === 1 ? 'client' : 'clients'}`}
            />
          ))}
        </Section>
      )}
    </Screen>
  );
}
