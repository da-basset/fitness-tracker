import { createContext, use, useEffect, useState, type PropsWithChildren } from 'react';

import { announceSignedIn, currentUserId, login, logout, onAuthChange, type LoginResult } from '@/api/client';
import { getRefreshToken } from '@/api/tokens';
import { notifyAll } from '@/data/bus';
import { clearLocalData, readCache, writeCache } from '@/data/db';
import { OWNER_KEY } from '@/data/keys';
import { startSync } from '@/data/sync';

type Session = {
  isLoading: boolean;
  isSignedIn: boolean;
  signIn: (username: string, password: string) => Promise<LoginResult>;
  /** Signs out and erases this device's local data, including unsynced changes. */
  signOut: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function useSession() {
  const value = use(SessionContext);
  if (!value) throw new Error('useSession must be used inside <SessionProvider>');
  return value;
}

/**
 * Local data belongs to whoever signed in last. A different account signing
 * in starts from a clean store so it never sees, or syncs, someone else's data.
 */
async function claimLocalData() {
  const userId = currentUserId();
  const owner = await readCache<number>(OWNER_KEY);
  if (owner?.data !== userId) {
    await clearLocalData();
    if (userId != null) await writeCache(OWNER_KEY, userId);
    notifyAll();
  }
}

async function signIn(username: string, password: string) {
  const result = await login(username, password);
  if (result === 'ok') {
    await claimLocalData();
    announceSignedIn();
  }
  return result;
}

async function signOut() {
  await logout();
  await clearLocalData();
  notifyAll();
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [isLoading, setIsLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthChange(setIsSignedIn);
    // A stored refresh token is enough to open the app, even offline; the
    // client signs us out if the server later rejects it. An expired session
    // keeps local data so the same user's unsynced changes survive re-login.
    getRefreshToken()
      .then((token) => setIsSignedIn(!!token))
      .catch(() => setIsSignedIn(false))
      .finally(() => setIsLoading(false));
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (isSignedIn) return startSync();
  }, [isSignedIn]);

  return (
    <SessionContext value={{ isLoading, isSignedIn, signIn, signOut }}>{children}</SessionContext>
  );
}
