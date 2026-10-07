import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { JobsPage, RegionsResponse, SourcesResponse } from "../lib/types";
import { toApiParams, type SearchState } from "./useUrlState";

export function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

interface Fetched<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Fetch on key change, abort the stale request, keep the previous data while loading. */
function useFetch<T>(key: string, load: (signal: AbortSignal) => Promise<T>, retry: number): Fetched<T> {
  const [state, setState] = useState<Fetched<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    load(ctrl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setState((s) => ({ ...s, error: e instanceof Error ? e.message : String(e), loading: false }));
      });
    return () => ctrl.abort();
    // `load` is derived from `key`; refetch only when the key (or retry counter) changes.
  }, [key, retry]);
  return state;
}

export function useJobs(s: SearchState, pageSize: number, retry: number) {
  const params = toApiParams(s, pageSize);
  const key = JSON.stringify(params);
  return useFetch<JobsPage>(key, (signal) => api.jobs(params, signal), retry);
}

export function useRegions(includeWorldwide: boolean, hideUnclear: boolean, retry: number) {
  const params = { include_worldwide: includeWorldwide, hide_unclear: hideUnclear };
  return useFetch<RegionsResponse>(JSON.stringify(params), (signal) => api.regions(params, signal), retry);
}

export function useSources(retry: number) {
  return useFetch<SourcesResponse>("sources", () => api.sources(), retry);
}
