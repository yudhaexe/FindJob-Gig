import type { Health, JobsPage, RegionsResponse, SourcesResponse } from "./types";

export type Params = Record<string, string | number | boolean | undefined>;

async function get<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const url = qs.size ? `${path}?${qs}` : path;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/api/health"),
  jobs: (params: Params, signal?: AbortSignal) => get<JobsPage>("/api/jobs", params, signal),
  regions: (params: { include_worldwide: boolean; hide_unclear: boolean }, signal?: AbortSignal) =>
    get<RegionsResponse>("/api/regions", params, signal),
  sources: () => get<SourcesResponse>("/api/sources"),
};
