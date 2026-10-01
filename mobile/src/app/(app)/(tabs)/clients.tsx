import { router } from 'expo-router';

import type { ClientSummary } from '@/api/types';
import { Button, EmptyState, Loading, PageTitle, ResourceStatus, Row, Screen, Section } from '@/components/ui';
import { useClients } from '@/data/manage';
import { hasRole, useMe } from '@/data/me';

export default function ClientsScreen() {
  const clients = useClients();
  const { data: me } = useMe();
  const canAdd = hasRole(me, 'trainer');
  const list = clients.data ?? [];

  // An owner sees every trainer's clients, grouped like the web dashboard.
  const groups = new Map<string, ClientSummary[]>();
  for (const client of list) {
    const label = client.trainer_id === me?.trainer_id ? 'Your clients' : `${client.trainer_name}'s clients`;
    groups.set(label, [...(groups.get(label) ?? []), client]);
  }

  return (
    <Screen refreshing={clients.refreshing} onRefresh={clients.refresh}>
      <PageTitle title="Clients" />
      <ResourceStatus offline={clients.offline} error={clients.error} fetchedAt={clients.fetchedAt} hasData={!!clients.data} />
      {canAdd && <Button title="Add client" icon="person.badge.plus" variant="secondary" onPress={() => router.push('/clients/new')} />}
      {clients.loading && !clients.data ? (
        <Loading />
      ) : list.length === 0 ? (
        <EmptyState
          title="No clients yet"
          message={canAdd ? 'Add a client to give them a login and assign a plan.' : 'Your trainers have no clients yet.'}
        />
      ) : (
        [...groups].map(([label, members]) => (
          <Section key={label} title={label}>
            {members.map((client) => (
              <Row
                key={client.id}
                title={client.name}
                detail={client.active_plan ? client.active_plan.plan_name : 'No plan assigned'}
                onPress={() => router.push({ pathname: '/clients/[clientId]', params: { clientId: client.id } })}
              />
            ))}
          </Section>
        ))
      )}
    </Screen>
  );
}
