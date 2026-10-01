import { router } from 'expo-router';

import { api } from '@/api/client';
import type { Trainer } from '@/api/types';
import { AccountForm } from '@/components/account-form';
import { revalidateTrainers } from '@/data/manage';
import { call } from '@/data/request';

export default function NewTrainerScreen() {
  return (
    <AccountForm
      intro="Creates a trainer login at your gym. They can then add their own clients and plans."
      submitLabel="Create trainer"
      onSubmit={async (body) => {
        const result = await call<Trainer>(api.POST('/api/v1/trainers/', { body }));
        if (result.ok) {
          await revalidateTrainers();
          router.back();
        }
        return result;
      }}
    />
  );
}
