import createClient, { type Middleware } from 'openapi-fetch';

import type { paths } from './schema';
import { clearTokens, getAccessToken, getRefreshToken, setAccessToken, setRefreshToken } from './tokens';

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

// Unauthenticated client for the token endpoints, so refreshing never
// recurses through the auth middleware.
const authClient = createClient<paths>({ baseUrl: API_BASE_URL });

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

type AuthListener = (signedIn: boolean) => void;
const listeners = new Set<AuthListener>();

export function onAuthChange(listener: AuthListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function emitAuthChange(signedIn: boolean) {
  listeners.forEach((listener) => listener(signedIn));
}

export async function login(username: string, password: string) {
  const { data, error } = await authClient.POST('/api/v1/auth/token/', { body: { username, password } });
  if (error || !data) return false;
  setAccessToken(data.access);
  await setRefreshToken(data.refresh);
  emitAuthChange(true);
  return true;
}

export async function logout() {
  const refresh = await getRefreshToken();
  await clearTokens();
  emitAuthChange(false);
  if (refresh) {
    // Best effort: blacklist server-side, but sign out locally regardless.
    await authClient.POST('/api/v1/auth/logout/', { body: { refresh } }).catch(() => undefined);
  }
}

// Refresh tokens rotate and the old one is blacklisted, so two concurrent
// refreshes would sign the user out. Share a single in-flight refresh.
let refreshing: Promise<string | null> | null = null;

export function refreshAccessToken() {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function doRefresh(): Promise<string | null> {
  const refresh = await getRefreshToken();
  if (!refresh) return null;
  let result;
  try {
    result = await authClient.POST('/api/v1/auth/token/refresh/', { body: { refresh } });
  } catch {
    // Offline: keep the refresh token so we can retry once reconnected.
    return null;
  }
  if (!result.data) {
    if (result.response.status === 401) {
      await clearTokens();
      emitAuthChange(false);
    }
    return null;
  }
  setAccessToken(result.data.access);
  await setRefreshToken(result.data.refresh);
  return result.data.access;
}

// Untouched copies of in-flight requests, so a 401 can be replayed once with
// a fresh token after the original body has been consumed.
const pending = new Map<string, Request>();

const authMiddleware: Middleware = {
  async onRequest({ id, request }) {
    const token = getAccessToken() ?? (await refreshAccessToken());
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    pending.set(id, request.clone());
    return request;
  },
  async onResponse({ id, response }) {
    const original = pending.get(id);
    pending.delete(id);
    if (response.status !== 401 || !original) return response;
    const token = await refreshAccessToken();
    if (!token) return response;
    original.headers.set('Authorization', `Bearer ${token}`);
    return fetch(original);
  },
  onError({ id }) {
    pending.delete(id);
  },
};

api.use(authMiddleware);
