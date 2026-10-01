import { useEffect, useState } from 'react';

import { OUTBOX_KEY, subscribe } from './bus';
import { pendingCount } from './outbox';

/** How many changes are queued for the server. */
export function usePendingCount() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const read = () => {
      pendingCount().then(setCount, () => undefined);
    };
    read();
    return subscribe(OUTBOX_KEY, read);
  }, []);
  return count;
}
