import { NativeTabs } from 'expo-router/unstable-native-tabs';

import { hasRole, useMe } from '@/data/me';
import { useTheme } from '@/hooks/use-theme';

// One app for every role: a user who is owner, trainer and client at once
// sees all of these tabs.
export default function TabLayout() {
  const { data: me } = useMe();
  const theme = useTheme();
  const isClient = hasRole(me, 'client');
  const manages = hasRole(me, 'trainer') || hasRole(me, 'owner');

  return (
    <NativeTabs tintColor={theme.accent}>
      <NativeTabs.Trigger name="today" hidden={!isClient}>
        <NativeTabs.Trigger.Label>Today</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'figure.strengthtraining.traditional', selected: 'figure.strengthtraining.traditional' }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="nutrition" hidden={!isClient}>
        <NativeTabs.Trigger.Label>Nutrition</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'leaf', selected: 'leaf.fill' }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="clients" hidden={!manages}>
        <NativeTabs.Trigger.Label>Clients</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'person.2', selected: 'person.2.fill' }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="plans" hidden={!manages}>
        <NativeTabs.Trigger.Label>Plans</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'list.bullet.rectangle', selected: 'list.bullet.rectangle.fill' }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="trainers" hidden={!hasRole(me, 'owner')}>
        <NativeTabs.Trigger.Label>Trainers</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'building.2', selected: 'building.2.fill' }} />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="profile">
        <NativeTabs.Trigger.Label>Profile</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf={{ default: 'person.crop.circle', selected: 'person.crop.circle.fill' }} />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
