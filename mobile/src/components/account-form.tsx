import { useState } from 'react';

import type { AccountCreate } from '@/api/types';
import { useSubmit } from '@/components/forms';
import { Banner, Button, Field, Screen } from '@/components/ui';
import type { Fetched } from '@/data/request';

/** New login for a trainer or client; the server applies the web's password rules. */
export function AccountForm({
  intro,
  submitLabel,
  onSubmit,
}: {
  intro: string;
  submitLabel: string;
  onSubmit: (body: AccountCreate) => Promise<Fetched<unknown>>;
}) {
  const [form, setForm] = useState({ username: '', password: '', first_name: '', last_name: '', email: '' });
  const { busy, fields, message, run } = useSubmit();
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));

  return (
    <Screen>
      <Banner>{intro}</Banner>
      <Field label="First name" value={form.first_name} onChangeText={set('first_name')} error={fields.first_name} textContentType="givenName" />
      <Field label="Last name" value={form.last_name} onChangeText={set('last_name')} error={fields.last_name} textContentType="familyName" />
      <Field
        label="Email"
        value={form.email}
        onChangeText={set('email')}
        error={fields.email}
        keyboardType="email-address"
        autoCapitalize="none"
        textContentType="emailAddress"
      />
      <Field
        label="Username"
        value={form.username}
        onChangeText={set('username')}
        error={fields.username}
        autoCapitalize="none"
        autoCorrect={false}
        textContentType="username"
      />
      <Field
        label="Temporary password"
        value={form.password}
        onChangeText={set('password')}
        error={fields.password}
        hint="Share it with them privately. Use at least 8 characters, not just numbers."
        secureTextEntry
        textContentType="newPassword"
      />
      {message && !Object.keys(fields).length ? <Banner tone="error">{message}</Banner> : null}
      <Button
        title={submitLabel}
        busy={busy}
        disabled={!form.username.trim() || !form.password}
        onPress={() => run(() => onSubmit({ ...form, username: form.username.trim() }))}
      />
    </Screen>
  );
}
