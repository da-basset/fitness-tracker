import { router } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { describeFailure, type Fetched } from '@/data/request';

/**
 * State for a save/delete form: busy flag, field errors from the API, and a
 * general message. `run` returns true when the request succeeded.
 */
export function useSubmit() {
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);

  async function run<T>(request: () => Promise<Fetched<T>>, after?: (data: T) => Promise<void> | void) {
    setBusy(true);
    setMessage(null);
    setFields({});
    const result = await request();
    if (result.ok) {
      await after?.(result.data);
      setBusy(false);
      return true;
    }
    if (result.kind !== 'offline') setFields(result.fields);
    setMessage(describeFailure(result));
    setBusy(false);
    return false;
  }

  return { busy, fields, message, run };
}

/** Native confirm sheet for anything that deletes. */
export function confirmDelete(what: string, detail: string, onConfirm: () => void) {
  Alert.alert(`Delete ${what}?`, detail, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: onConfirm },
  ]);
}

export function close() {
  if (router.canGoBack()) router.back();
}
