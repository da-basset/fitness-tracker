import { useEffect, useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/api/client';
import { useSession } from '@/auth/session';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';

type Me = { username: string; first_name: string; timezone: string; today: string };

// Placeholder until the schedule screen lands; proves the auth round trip.
export default function HomeScreen() {
  const { signOut } = useSession();
  const [me, setMe] = useState<Me | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .GET('/api/v1/me/')
      .then(({ data }) => (data ? setMe(data as unknown as Me) : setFailed(true)))
      .catch(() => setFailed(true));
  }, []);

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedText type="subtitle">
          {me ? `Hi, ${me.first_name || me.username}` : failed ? 'Offline' : 'Loading…'}
        </ThemedText>
        {me && (
          <ThemedText themeColor="textSecondary">
            Today is {me.today} ({me.timezone})
          </ThemedText>
        )}
        <Pressable onPress={signOut} accessibilityRole="button">
          <ThemedText type="linkPrimary">Sign out</ThemedText>
        </Pressable>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  safeArea: {
    flex: 1,
    maxWidth: MaxContentWidth,
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
    paddingBottom: BottomTabInset + Spacing.three,
    gap: Spacing.three,
  },
});
