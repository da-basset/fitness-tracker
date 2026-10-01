import { router } from 'expo-router';

import { api } from '@/api/client';
import type { ClientSummary } from '@/api/types';
import { AccountForm } from '@/components/account-form';
import { revalidateClients } from '@/data/manage';
import { call } from '@/data/request';

export default function NewClientScreen() {
  return (
    <AccountForm
      intro="Creates a login for your new client. They sign in to this app with it."
      submitLabel="Create client"
      onSubmit={async (body) => {
        const result = await call<ClientSummary>(api.POST('/api/v1/clients/', { body }));
        if (result.ok) {
          await revalidateClients();
          router.replace({ pathname: '/clients/[clientId]', params: { clientId: result.data.id } });
        }
        return result;
      }}
    />
  );
}
