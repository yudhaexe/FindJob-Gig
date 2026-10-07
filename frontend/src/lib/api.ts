import type {
  Health, Job, JobsPage, RegionsResponse, Run, ScrapeQuery, ScrapeSourcesResponse, SourcesResponse,
} from "./types";

export type Params = Record<string, string | number | boolean | undefined>;

async function ok<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // FastAPI puts the reason in `detail`; show it instead of a bare status line.
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const url = qs.size ? `${path}?${qs}` : path;
  return ok<T>(await fetch(url, { signal }));
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return ok<T>(await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
}

export const api = {
  health: () => get<Health>("/api/health"),
  jobs: (params: Params, signal?: AbortSignal) => get<JobsPage>("/api/jobs", params, signal),
  job: (id: string, signal?: AbortSignal) => get<Job>(`/api/jobs/${encodeURIComponent(id)}`, undefined, signal),
  updateJobStatus: (id: string, status: "keep" | "removed" | null) =>
    post<Job>(`/api/jobs/${encodeURIComponent(id)}/status`, { status }),
  regions: (params: { include_worldwide: boolean; hide_unclear: boolean }, signal?: AbortSignal) =>
    get<RegionsResponse>("/api/regions", params, signal),
  sources: () => get<SourcesResponse>("/api/sources"),
  scrapeSources: (params: { region: string; category: string }, signal?: AbortSignal) =>
    get<ScrapeSourcesResponse>("/api/scrape/sources", params, signal),
  startScrape: (q: ScrapeQuery) => post<{ run_id: string }>("/api/scrape", q),
  runs: (limit = 30) => get<Run[]>("/api/runs", { limit }),
  run: (id: string) => get<Run>(`/api/runs/${encodeURIComponent(id)}`),
};
