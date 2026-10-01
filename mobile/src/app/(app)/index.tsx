import { Redirect } from 'expo-router';
import { View } from 'react-native';

import { Button, EmptyState, Loading } from '@/components/ui';
import { hasRole, useMe } from '@/data/me';
import { useTheme } from '@/hooks/use-theme';

/** Sends each account to its first tab: clients log, trainers and owners manage. */
export default function Start() {
  const me = useMe();
  const theme = useTheme();

  if (me.data) {
    const home = hasRole(me.data, 'client') ? '/today' : hasRole(me.data, 'trainer') || hasRole(me.data, 'owner') ? '/clients' : '/profile';
    return <Redirect href={home} />;
  }
  return (
    <View style={{ flex: 1, justifyContent: 'center', backgroundColor: theme.background, padding: 24 }}>
      {me.loading || me.refreshing ? (
        <Loading />
      ) : (
        <EmptyState
          title="Couldn't load your account"
          message={me.offline ? "You're offline. Connect and try again." : (me.error ?? undefined)}
          action={<Button title="Try again" onPress={me.refresh} compact />}
        />
      )}
    </View>
  );
}
