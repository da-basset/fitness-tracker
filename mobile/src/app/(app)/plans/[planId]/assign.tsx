import { router, useLocalSearchParams } from 'expo-router';
import { Alert } from 'react-native';

import { api } from '@/api/client';
import type { Assignment } from '@/api/types';
import { useSubmit } from '@/components/forms';
import { Banner, EmptyState, Loading, ResourceStatus, Row, Screen, Section } from '@/components/ui';
import { revalidateClient, revalidateClients, useClients, usePlan } from '@/data/manage';
import { call } from '@/data/request';

export default function AssignPlanScreen() {
  const planId = Number(useLocalSearchParams<{ planId: string }>().planId);
  const plan = usePlan(planId);
  const clients = useClients();
  const { busy, message, run } = useSubmit();
  // Only the plan's own trainer's clients can receive it, as on the web.
  const eligible = (clients.data ?? []).filter((c) => c.trainer_id === plan.data?.trainer_id);

  function assign(clientId: number, name: string, current: string | undefined) {
    Alert.alert(
      `Assign to ${name}?`,
      `${name} gets their own copy of "${plan.data?.name}".${current ? ` "${current}" moves to their past plans.` : ''}`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Assign',
          onPress: () =>
            run(
              () =>
                call<Assignment>(
                  api.POST('/api/v1/plans/{plan_id}/assign/', {
                    params: { path: { plan_id: planId } },
                    body: { client_id: clientId },
                  })
                ),
              async () => {
                await Promise.all([revalidateClients(), revalidateClient(clientId)]);
                router.dismiss();
                router.push({ pathname: '/clients/[clientId]', params: { clientId } });
              }
            ),
        },
      ]
    );
  }

  return (
    <Screen refreshing={clients.refreshing} onRefresh={clients.refresh}>
      <ResourceStatus offline={clients.offline} error={clients.error} fetchedAt={clients.fetchedAt} hasData={!!clients.data} />
      {message ? <Banner tone="error">{message}</Banner> : null}
      {clients.loading && !clients.data ? (
        <Loading />
      ) : eligible.length === 0 ? (
        <EmptyState title="No clients to assign to" message="Add a client for this plan's trainer first." />
      ) : (
        <Section title="Choose a client">
          {eligible.map((client) => (
            <Row
              key={client.id}
              title={client.name}
              detail={client.active_plan ? `Current plan: ${client.active_plan.plan_name}` : 'No plan assigned'}
              disabled={busy}
              onPress={() => assign(client.id, client.name, client.active_plan?.plan_name)}
            />
          ))}
        </Section>
      )}
    </Screen>
  );
}
