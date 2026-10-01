import { Redirect } from 'expo-router';

import { hasRole, useMe } from '@/data/me';

/** Sends each account to its first tab: clients log, trainers and owners manage. */
export default function Start() {
  const { data: me } = useMe();
  if (hasRole(me, 'client')) return <Redirect href="/today" />;
  if (hasRole(me, 'trainer') || hasRole(me, 'owner')) return <Redirect href="/clients" />;
  return <Redirect href="/profile" />;
}
