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

export type LoginResult = 'ok' | 'invalid' | 'unreachable';

export async function login(username: string, password: string): Promise<LoginResult> {
  let result;
  try {
    result = await authClient.POST('/api/v1/auth/token/', { body: { username, password } });
  } catch {
    return 'unreachable';
  }
  if (!result.data) return result.response.status === 401 ? 'invalid' : 'unreachable';
  setAccessToken(result.data.access);
  await setRefreshToken(result.data.refresh);
  // The caller announces the sign-in once local data is ready for this user.
  return 'ok';
}

export function announceSignedIn() {
  emitAuthChange(true);
}

/** The user id inside a SimpleJWT access token, read without a network call. */
export function currentUserId(): number | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const claims = JSON.parse(atob(payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=')));
    return typeof claims.user_id === 'number' ? claims.user_id : Number(claims.user_id) || null;
  } catch {
    return null;
  }
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
  // Return undefined to keep the response. openapi-fetch checks a returned
  // value with `instanceof Response`, and on React Native fetch() resolves
  // to a different Response class than the global one, so handing back the
  // original (or a raw fetch result) throws.
  async onResponse({ id, response }) {
    const original = pending.get(id);
    pending.delete(id);
    if (response.status !== 401 || !original) return undefined;
    const token = await refreshAccessToken();
    if (!token) return undefined;
    original.headers.set('Authorization', `Bearer ${token}`);
    const retried = await fetch(original);
    return new Response(await retried.text(), {
      status: retried.status,
      statusText: retried.statusText,
      headers: retried.headers,
    });
  },
  onError({ id }) {
    pending.delete(id);
  },
};

api.use(authMiddleware);
