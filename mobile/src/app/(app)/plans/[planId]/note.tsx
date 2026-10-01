import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api/client';
import type { Nutrient } from '@/api/types';
import { confirmDelete, useSubmit } from '@/components/forms';
import { Banner, Button, Field, Screen } from '@/components/ui';
import { revalidatePlan, usePlan } from '@/data/manage';
import { call } from '@/data/request';

type Kind = 'nutrient' | 'supplement';

const COPY = {
  nutrient: { label: 'nutrient', name: 'e.g. Protein', amount: 'e.g. 180g/day', timing: 'e.g. Spread across meals' },
  supplement: { label: 'supplement', name: 'e.g. Creatine', amount: 'e.g. 5g', timing: 'e.g. Morning' },
};

/** Create (no id) or edit a nutrient or supplement on a plan. */
export default function NoteScreen() {
  const params = useLocalSearchParams<{ planId: string; kind: Kind; id?: string }>();
  const planId = Number(params.planId);
  const kind: Kind = params.kind === 'supplement' ? 'supplement' : 'nutrient';
  const id = params.id ? Number(params.id) : null;
  const plan = usePlan(planId);
  const list = kind === 'nutrient' ? plan.data?.nutrients : plan.data?.supplements;
  const existing = list?.find((n) => n.id === id);

  if (id != null && !existing) return <Screen />;
  return <NoteForm planId={planId} kind={kind} existing={existing} />;
}

function NoteForm({ planId, kind, existing }: { planId: number; kind: Kind; existing?: Nutrient }) {
  const copy = COPY[kind];
  const [form, setForm] = useState({
    name: existing?.name ?? '',
    amount: existing?.amount ?? '',
    timing: existing?.timing ?? '',
    notes: existing?.notes ?? '',
  });
  const { busy, fields, message, run } = useSubmit();
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const body = { ...form, name: form.name.trim() };

  async function done() {
    await revalidatePlan(planId);
    router.back();
  }

  function save() {
    run(() => {
      if (kind === 'nutrient') {
        return existing
          ? call(api.PATCH('/api/v1/plans/{plan_id}/nutrients/{nutrient_id}/', { params: { path: { plan_id: planId, nutrient_id: existing.id } }, body }))
          : call(api.POST('/api/v1/plans/{plan_id}/nutrients/', { params: { path: { plan_id: planId } }, body }));
      }
      return existing
        ? call(api.PATCH('/api/v1/plans/{plan_id}/supplements/{supplement_id}/', { params: { path: { plan_id: planId, supplement_id: existing.id } }, body }))
        : call(api.POST('/api/v1/plans/{plan_id}/supplements/', { params: { path: { plan_id: planId } }, body }));
    }, done);
  }

  function remove() {
    if (!existing) return;
    confirmDelete(`"${existing.name}"`, "It's removed from the client's list.", () =>
      run(
        () =>
          kind === 'nutrient'
            ? call(api.DELETE('/api/v1/plans/{plan_id}/nutrients/{nutrient_id}/', { params: { path: { plan_id: planId, nutrient_id: existing.id } } }))
            : call(api.DELETE('/api/v1/plans/{plan_id}/supplements/{supplement_id}/', { params: { path: { plan_id: planId, supplement_id: existing.id } } })),
        done
      )
    );
  }

  return (
    <Screen>
      <Stack.Screen options={{ title: existing ? `Edit ${copy.label}` : `New ${copy.label}` }} />
      {message && !Object.keys(fields).length ? <Banner tone="error">{message}</Banner> : null}
      <Field label="Name" value={form.name} onChangeText={set('name')} placeholder={copy.name} error={fields.name} />
      <Field label="Amount" value={form.amount} onChangeText={set('amount')} placeholder={copy.amount} error={fields.amount} />
      <Field label="Timing" value={form.timing} onChangeText={set('timing')} placeholder={copy.timing} error={fields.timing} />
      <Field label="Notes" value={form.notes} onChangeText={set('notes')} multiline error={fields.notes} />
      <Button title={existing ? 'Save' : `Add ${copy.label}`} onPress={save} busy={busy} disabled={!form.name.trim()} />
      {existing && <Button title={`Delete ${copy.label}`} variant="destructive" onPress={remove} />}
    </Screen>
  );
}
