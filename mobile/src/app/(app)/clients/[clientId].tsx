import { router, Stack, useLocalSearchParams } from 'expo-router';
import { Alert, StyleSheet, View } from 'react-native';

import { api } from '@/api/client';
import type { Assignment } from '@/api/types';
import { useSubmit } from '@/components/forms';
import { ThemedText } from '@/components/themed-text';
import { Banner, Button, Card, EmptyState, Loading, ResourceStatus, Row, Screen, Section } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { revalidateClient, revalidateClients, useClient } from '@/data/manage';
import { call } from '@/data/request';

export default function ClientDetailScreen() {
  const clientId = Number(useLocalSearchParams<{ clientId: string }>().clientId);
  const client = useClient(clientId);
  const { busy, message, run } = useSubmit();
  const data = client.data;

  async function refreshAll() {
    await Promise.all([revalidateClient(clientId), revalidateClients()]);
  }

  function assign(planId: number, planName: string) {
    const replacing = data?.active_assignment
      ? ` This replaces "${data.active_assignment.plan_name}", which moves to past plans.`
      : '';
    Alert.alert(`Assign "${planName}"?`, `${data?.name} gets their own copy of this plan.${replacing}`, [
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
            refreshAll
          ),
      },
    ]);
  }

  function unassign(assignmentId: number) {
    Alert.alert('Unassign this plan?', 'The client keeps it in their past plans and stops seeing it in the app.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Unassign',
        style: 'destructive',
        onPress: () =>
          run(
            () =>
              call<Assignment>(
                api.POST('/api/v1/assignments/{assignment_id}/unassign/', {
                  params: { path: { assignment_id: assignmentId } },
                })
              ),
            refreshAll
          ),
      },
    ]);
  }

  if (!data) {
    return (
      <Screen refreshing={client.refreshing} onRefresh={client.refresh}>
        {client.loading ? (
          <Loading />
        ) : client.notFound ? (
          <EmptyState title="Client not found" message="You may not have access to this client." />
        ) : (
          <ResourceStatus offline={client.offline} error={client.error} fetchedAt={null} hasData={false} />
        )}
      </Screen>
    );
  }

  const active = data.active_assignment;

  return (
    <Screen refreshing={client.refreshing} onRefresh={client.refresh}>
      <Stack.Screen options={{ title: data.name }} />
      <ResourceStatus offline={client.offline} error={client.error} fetchedAt={client.fetchedAt} hasData />
      {message ? <Banner tone="error">{message}</Banner> : null}

      <Card>
        <ThemedText type="smallBold">{data.name}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          @{data.username}
          {data.email ? ` · ${data.email}` : ''}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Trainer: {data.trainer_name}
        </ThemedText>
      </Card>

      <Section title="Active plan">
        {active ? (
          <Card>
            <ThemedText type="smallBold">{active.plan_name}</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Assigned {new Date(active.assigned_at).toLocaleDateString()}
            </ThemedText>
            {data.stats && (
              <ThemedText type="small" themeColor="textSecondary">
                {data.stats.all_time_completed} workouts completed
                {data.stats.last_completed_at
                  ? `, last on ${new Date(`${data.stats.last_completed_at}T00:00`).toLocaleDateString()}`
                  : ''}
              </ThemedText>
            )}
            <View style={styles.actions}>
              <Button
                title="Edit plan"
                compact
                onPress={() => router.push({ pathname: '/plans/[planId]', params: { planId: active.plan_id } })}
              />
              <Button
                title="Client view"
                variant="secondary"
                compact
                onPress={() => router.push({ pathname: '/plans/[planId]/preview', params: { planId: active.plan_id } })}
              />
              <Button title="Unassign" variant="destructive" compact busy={busy} onPress={() => unassign(active.id)} />
            </View>
          </Card>
        ) : (
          <ThemedText type="small" themeColor="textSecondary">
            No plan assigned. Pick a template below.
          </ThemedText>
        )}
      </Section>

      <Section title={active ? 'Assign a different plan' : 'Assign a plan'}>
        {data.templates.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            The plan library is empty. Create a template in the Plans tab first.
          </ThemedText>
        ) : (
          data.templates.map((template) => (
            <Row
              key={template.id}
              title={template.name}
              detail={template.description || null}
              disabled={busy}
              onPress={() => assign(template.id, template.name)}
              accessory={<ThemedText type="linkPrimary">Assign</ThemedText>}
            />
          ))
        )}
      </Section>

      {data.past_assignments.length > 0 && (
        <Section title="Past plans">
          {data.past_assignments.map((past) => (
            <Row
              key={past.id}
              title={past.plan_name}
              detail={`Assigned ${new Date(past.assigned_at).toLocaleDateString()}`}
              onPress={() => router.push({ pathname: '/plans/[planId]/preview', params: { planId: past.plan_id } })}
            />
          ))}
        </Section>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.two, marginTop: Spacing.one },
});
