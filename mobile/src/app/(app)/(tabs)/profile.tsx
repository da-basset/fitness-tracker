import { useState } from 'react';
import { Alert } from 'react-native';

import { useSession } from '@/auth/session';
import { ThemedText } from '@/components/themed-text';
import { Banner, Button, Card, PageTitle, ResourceStatus, Screen, Section } from '@/components/ui';
import { useMe } from '@/data/me';
import { flush } from '@/data/sync';
import { usePendingCount } from '@/data/use-pending';

const ROLE_LABELS = { owner: 'Gym owner', trainer: 'Trainer', client: 'Client' } as const;

export default function ProfileScreen() {
  const me = useMe();
  const { signOut } = useSession();
  const pending = usePendingCount();
  const [syncing, setSyncing] = useState(false);
  const user = me.data;

  async function syncNow() {
    setSyncing(true);
    await flush();
    setSyncing(false);
  }

  function confirmSignOut() {
    const warning =
      pending > 0
        ? `${pending === 1 ? '1 change hasn’t' : `${pending} changes haven’t`} synced yet and will be lost.`
        : undefined;
    Alert.alert('Sign out?', warning, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: () => signOut() },
    ]);
  }

  const name = user ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username : '';

  return (
    <Screen refreshing={me.refreshing} onRefresh={me.refresh}>
      <PageTitle title="Profile" subtitle={user ? `@${user.username}` : null} />
      <ResourceStatus offline={me.offline} error={me.error} fetchedAt={me.fetchedAt} hasData={!!user} />
      {user && (
        <Card>
          <ThemedText type="smallBold">{name}</ThemedText>
          {user.email ? (
            <ThemedText type="small" themeColor="textSecondary">
              {user.email}
            </ThemedText>
          ) : null}
          <ThemedText type="small" themeColor="textSecondary">
            {user.roles.map((role) => ROLE_LABELS[role]).join(' · ') || 'No role yet'}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Time zone: {user.timezone}
          </ThemedText>
        </Card>
      )}

      <Section title="Sync">
        {pending > 0 ? (
          <Banner tone="info">
            {pending === 1 ? '1 change is' : `${pending} changes are`} waiting to be sent to the server.
          </Banner>
        ) : (
          <ThemedText type="small" themeColor="textSecondary">
            Everything on this phone has been synced.
          </ThemedText>
        )}
        {pending > 0 && <Button title="Sync now" variant="secondary" onPress={syncNow} busy={syncing} />}
      </Section>

      <Button title="Sign out" variant="destructive" onPress={confirmSignOut} />
    </Screen>
  );
}
