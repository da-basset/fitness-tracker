import { Stack } from 'expo-router';
import { View } from 'react-native';

import { Button, EmptyState, Loading } from '@/components/ui';
import { MeContext, useMeResource } from '@/data/me';
import { useTheme } from '@/hooks/use-theme';

// Tabs at the bottom; everything you drill into is pushed over them.
export default function AppLayout() {
  const me = useMeResource();
  const theme = useTheme();

  // Nothing signed-in renders until we know who this is: the tabs depend on
  // the account's roles, and native tabs reset if they change after mount.
  if (!me.data) {
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

  return (
    <MeContext value={me}>
      <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal' }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="workout/[workoutId]" options={{ title: 'Workout' }} />
        <Stack.Screen name="clients/new" options={{ title: 'New client', presentation: 'modal' }} />
        <Stack.Screen name="clients/[clientId]" options={{ title: 'Client' }} />
        <Stack.Screen name="trainers/new" options={{ title: 'New trainer', presentation: 'modal' }} />
        <Stack.Screen name="plans/new" options={{ title: 'New plan', presentation: 'modal' }} />
        <Stack.Screen name="plans/[planId]/index" options={{ title: 'Plan' }} />
        <Stack.Screen name="plans/[planId]/preview" options={{ title: 'Client view' }} />
        <Stack.Screen name="plans/[planId]/assign" options={{ title: 'Assign plan', presentation: 'modal' }} />
        <Stack.Screen name="plans/[planId]/workouts/[workoutId]" options={{ title: 'Edit workout' }} />
        <Stack.Screen name="plans/[planId]/exercise" options={{ title: 'Exercise', presentation: 'modal' }} />
        <Stack.Screen name="plans/[planId]/phases/[phaseId]" options={{ title: 'Edit phase' }} />
        <Stack.Screen name="plans/[planId]/note" options={{ title: 'Edit', presentation: 'modal' }} />
      </Stack>
    </MeContext>
  );
}
