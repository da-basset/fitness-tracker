import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { api } from '@/api/client';
import type { PlanSummary } from '@/api/types';
import { useSubmit } from '@/components/forms';
import { Banner, Button, Field, Screen } from '@/components/ui';
import { revalidateLibrary } from '@/data/manage';
import { call } from '@/data/request';

export default function NewPlanScreen() {
  const trainerId = Number(useLocalSearchParams<{ trainerId: string }>().trainerId);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const { busy, fields, message, run } = useSubmit();

  function save() {
    run(
      () =>
        call<PlanSummary>(
          api.POST('/api/v1/trainers/{trainer_id}/plans/', {
            params: { path: { trainer_id: trainerId } },
            body: { name: name.trim(), description },
          })
        ),
      async (plan) => {
        await revalidateLibrary(trainerId);
        router.replace({ pathname: '/plans/[planId]', params: { planId: plan.id } });
      }
    );
  }

  return (
    <Screen>
      <Field label="Name" value={name} onChangeText={setName} placeholder="e.g. Beginner Strength" error={fields.name} />
      <Field
        label="Description"
        value={description}
        onChangeText={setDescription}
        placeholder="Optional. Only trainers see this."
        multiline
        error={fields.description}
      />
      {message && !fields.name ? <Banner tone="error">{message}</Banner> : null}
      <Button title="Create plan" onPress={save} busy={busy} disabled={!name.trim()} />
    </Screen>
  );
}
