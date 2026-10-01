export type Fetched<T> =
  | { ok: true; data: T }
  | { ok: false; kind: 'offline' }
  | { ok: false; kind: 'notFound' | 'error'; status: number; message: string; fields: Record<string, string> };

type ApiCall<T> = Promise<{ data?: T; error?: unknown; response: Response }>;

/** Turn an openapi-fetch call into a result screens can branch on. */
export async function call<T>(promise: ApiCall<T>): Promise<Fetched<T>> {
  let result;
  try {
    result = await promise;
  } catch {
    return { ok: false, kind: 'offline' };
  }
  if (result.response.ok) return { ok: true, data: result.data as T };
  const fields = fieldErrors(result.error);
  return {
    ok: false,
    kind: result.response.status === 404 ? 'notFound' : 'error',
    status: result.response.status,
    fields,
    message: errorMessage(fields, result.response.status),
  };
}

/** DRF errors look like {"detail": "..."} or {"field": ["msg", ...]}. */
function fieldErrors(error: unknown): Record<string, string> {
  if (!error || typeof error !== 'object') return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(error as Record<string, unknown>)) {
    const text = Array.isArray(value) ? value.map(String).join(' ') : typeof value === 'string' ? value : '';
    if (text) out[key] = text;
  }
  return out;
}

function errorMessage(fields: Record<string, string>, status: number) {
  if (fields.detail) return fields.detail;
  if (fields.non_field_errors) return fields.non_field_errors;
  const first = Object.entries(fields)[0];
  if (first) return `${first[0].replace(/_/g, ' ')}: ${first[1]}`;
  return status >= 500 ? 'The server had a problem. Try again.' : `Request failed (${status}).`;
}

export function describeFailure(result: Exclude<Fetched<unknown>, { ok: true }>) {
  return result.kind === 'offline' ? "You're offline. Connect to the internet and try again." : result.message;
}
