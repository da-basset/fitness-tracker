import { Stack } from 'expo-router';

// Tabs at the bottom; everything you drill into is pushed over them.
export default function AppLayout() {
  return (
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
  );
}
