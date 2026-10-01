import { createContext, use } from 'react';

import { api } from '@/api/client';
import type { Me } from '@/api/types';

import { deviceTimeZone } from './dates';
import { ME_KEY } from './keys';
import { call } from './request';
import { useResource } from './use-resource';

/**
 * The signed-in user. Also keeps the server's idea of "today" in step with
 * the phone: if the device's time zone differs from the profile's, update it.
 */
async function fetchMe() {
  const result = await call<Me>(api.GET('/api/v1/me/'));
  const zone = deviceTimeZone();
  if (result.ok && zone && result.data.timezone !== zone) {
    const updated = await call<Me>(api.PATCH('/api/v1/me/', { body: { timezone: zone } }));
    if (updated.ok) return updated;
  }
  return result;
}

/** Loads and refreshes the account; only the app shell should call this. */
export function useMeResource() {
  return useResource<Me>(ME_KEY, fetchMe);
}

/**
 * The app shell provides the account before any signed-in screen renders,
 * so roles (and the tabs they decide) are known on the very first frame.
 */
export const MeContext = createContext<ReturnType<typeof useMeResource> | null>(null);

export function useMe() {
  const value = use(MeContext);
  if (!value?.data) throw new Error('useMe must be used inside the signed-in app shell');
  return { ...value, data: value.data };
}

export function hasRole(me: Me | undefined, role: Me['roles'][number]) {
  return !!me?.roles.includes(role);
}
