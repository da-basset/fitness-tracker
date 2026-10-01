import { createContext, use, useEffect, useState, type PropsWithChildren } from 'react';

import { login, logout, onAuthChange, type LoginResult } from '@/api/client';
import { getRefreshToken } from '@/api/tokens';

type Session = {
  isLoading: boolean;
  isSignedIn: boolean;
  signIn: (username: string, password: string) => Promise<LoginResult>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function useSession() {
  const value = use(SessionContext);
  if (!value) throw new Error('useSession must be used inside <SessionProvider>');
  return value;
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [isLoading, setIsLoading] = useState(true);
  const [isSignedIn, setIsSignedIn] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthChange(setIsSignedIn);
    // A stored refresh token is enough to open the app, even offline; the
    // client signs us out if the server later rejects it.
    getRefreshToken()
      .then((token) => setIsSignedIn(!!token))
      .catch(() => setIsSignedIn(false))
      .finally(() => setIsLoading(false));
    return unsubscribe;
  }, []);

  return (
    <SessionContext value={{ isLoading, isSignedIn, signIn: login, signOut: logout }}>
      {children}
    </SessionContext>
  );
}
