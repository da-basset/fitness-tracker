import { api } from '@/api/client';
import type { ClientDetail, ClientSummary, PlanDetail, PlanSummary, Trainer } from '@/api/types';

import { notify } from './bus';
import { writeCache } from './db';
import { call, type Fetched } from './request';
import { useResource } from './use-resource';

// Trainer/owner screens read through the same cache as the client screens,
// so they open instantly and stay readable offline; changes need a
// connection and refetch what they touched.

export const keys = {
  trainers: 'm:trainers',
  clients: 'm:clients',
  client: (id: number) => `m:client:${id}`,
  library: (trainerId: number) => `m:library:${trainerId}`,
  plan: (id: number) => `m:plan:${id}`,
};

export const fetchers = {
  trainers: () => call<Trainer[]>(api.GET('/api/v1/trainers/')),
  clients: () => call<ClientSummary[]>(api.GET('/api/v1/clients/')),
  client: (id: number) =>
    call<ClientDetail>(api.GET('/api/v1/clients/{client_id}/', { params: { path: { client_id: id } } })),
  library: (trainerId: number) =>
    call<PlanSummary[]>(api.GET('/api/v1/trainers/{trainer_id}/plans/', { params: { path: { trainer_id: trainerId } } })),
  plan: (id: number) => call<PlanDetail>(api.GET('/api/v1/plans/{plan_id}/', { params: { path: { plan_id: id } } })),
};

export const useTrainers = () => useResource(keys.trainers, fetchers.trainers);
export const useClients = () => useResource(keys.clients, fetchers.clients);
export const useClient = (id: number) => useResource(keys.client(id), () => fetchers.client(id));
export const useLibrary = (trainerId: number | null) =>
  useResource(trainerId == null ? null : keys.library(trainerId), () => fetchers.library(trainerId!));
export const usePlan = (id: number) => useResource(keys.plan(id), () => fetchers.plan(id));

/** Refetch and store a resource so every screen showing it updates. */
export async function revalidate<T>(key: string, fetcher: () => Promise<Fetched<T>>) {
  const result = await fetcher();
  if (result.ok) {
    await writeCache(key, result.data);
    notify(key);
  }
}

export const revalidatePlan = (id: number) => revalidate(keys.plan(id), () => fetchers.plan(id));
export const revalidateClients = () => revalidate(keys.clients, fetchers.clients);
export const revalidateClient = (id: number) => revalidate(keys.client(id), () => fetchers.client(id));
export const revalidateLibrary = (trainerId: number) =>
  revalidate(keys.library(trainerId), () => fetchers.library(trainerId));
export const revalidateTrainers = () => revalidate(keys.trainers, fetchers.trainers);
