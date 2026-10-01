// Tiny pub/sub so screens re-read local data when it changes underneath them.

type Listener = () => void;
const byKey = new Map<string, Set<Listener>>();

/** Fired when a cache key's local data (or the outbox overlaying it) changed. */
export function subscribe(key: string, listener: Listener) {
  let set = byKey.get(key);
  if (!set) byKey.set(key, (set = new Set()));
  set.add(listener);
  return () => {
    set.delete(listener);
  };
}

export function notify(...keys: string[]) {
  for (const key of keys) byKey.get(key)?.forEach((listener) => listener());
}

/** Every key; used when the whole local store changes (sync, sign-out). */
export function notifyAll() {
  byKey.forEach((set) => set.forEach((listener) => listener()));
}

export const OUTBOX_KEY = 'outbox';
