// All search state lives in the URL so a view can be bookmarked or shared (DESIGN-UIUX.md §1.5).
import { useCallback, useEffect, useRef, useState } from "react";
import type { Sort } from "../lib/types";

export interface SearchState {
  q: string;
  region: string;
  category: string; // "" | "job" | "gig"
  type: string[];
  mode: string[];
  source: string[];
  country: string[];
  seniority: string[];
  currency: string; // single currency: salary sort/filter needs exactly one
  salary_min: string;
  salary_period: string;
  has_salary: boolean;
  posted_within: string; // hours, "" = any
  include_worldwide: boolean;
  hide_unclear: boolean;
  sort: Sort | "";
  page: number;
  job: string; // id of the job open in the drawer, "" = closed
}

export const DEFAULTS: SearchState = {
  q: "", region: "ALL", category: "", type: [], mode: [], source: [], country: [], seniority: [],
  currency: "", salary_min: "", salary_period: "month", has_salary: false, posted_within: "",
  include_worldwide: true, hide_unclear: false, sort: "", page: 1, job: "",
};

const LIST_KEYS = ["type", "mode", "source", "country", "seniority"] as const;
const REGION_PREF = "fjg.region";

function readRegionPref(): string | null {
  try {
    return localStorage.getItem(REGION_PREF);
  } catch {
    return null;
  }
}

function fromUrl(search: string): SearchState {
  const p = new URLSearchParams(search);
  const s: SearchState = { ...DEFAULTS };
  s.q = p.get("q") ?? "";
  s.region = (p.get("region") ?? readRegionPref() ?? "ALL").toUpperCase();
  s.category = p.get("category") ?? "";
  for (const k of LIST_KEYS) s[k] = (p.get(k) ?? "").split(",").filter(Boolean);
  s.currency = p.get("currency") ?? "";
  s.salary_min = p.get("salary_min") ?? "";
  s.salary_period = p.get("salary_period") ?? "month";
  s.has_salary = p.get("has_salary") === "1";
  s.posted_within = p.get("posted_within") ?? "";
  s.include_worldwide = p.get("include_worldwide") !== "0";
  s.hide_unclear = p.get("hide_unclear") === "1";
  s.sort = (p.get("sort") as Sort | null) ?? "";
  s.page = Math.max(1, Number(p.get("page")) || 1);
  s.job = p.get("job") ?? "";
  return s;
}

function toUrl(s: SearchState): string {
  const p = new URLSearchParams();
  const set = (k: string, v: string) => v && p.set(k, v);
  set("q", s.q.trim());
  if (s.region !== "ALL") p.set("region", s.region);
  set("category", s.category);
  for (const k of LIST_KEYS) set(k, s[k].join(","));
  set("currency", s.currency);
  set("salary_min", s.currency ? s.salary_min : "");
  if (s.currency && s.salary_min && s.salary_period !== "month") p.set("salary_period", s.salary_period);
  if (s.has_salary) p.set("has_salary", "1");
  set("posted_within", s.posted_within);
  if (!s.include_worldwide) p.set("include_worldwide", "0");
  if (s.hide_unclear) p.set("hide_unclear", "1");
  set("sort", s.sort);
  if (s.page > 1) p.set("page", String(s.page));
  set("job", s.job);
  const qs = p.toString();
  return qs ? `?${qs}` : location.pathname;
}

/** API params for /api/jobs (the server ignores salary_min without a currency). */
export function toApiParams(s: SearchState, pageSize: number): Record<string, string | number | boolean | undefined> {
  return {
    q: s.q.trim() || undefined,
    region: s.region,
    include_worldwide: s.include_worldwide ? undefined : false,
    hide_unclear: s.hide_unclear || undefined,
    category: s.category || undefined,
    type: s.type.join(",") || undefined,
    mode: s.mode.join(",") || undefined,
    source: s.source.join(",") || undefined,
    country: s.country.join(",") || undefined,
    seniority: s.seniority.join(",") || undefined,
    currency: s.currency || undefined,
    salary_min: s.currency && s.salary_min ? s.salary_min : undefined,
    salary_period: s.currency && s.salary_min ? s.salary_period : undefined,
    has_salary: s.has_salary || undefined,
    posted_within: s.posted_within || undefined,
    sort: s.sort || undefined,
    page: s.page,
    page_size: pageSize,
  };
}

export function activeFilterCount(s: SearchState): number {
  return (
    (s.category ? 1 : 0) + LIST_KEYS.reduce((n, k) => n + s[k].length, 0) + (s.currency ? 1 : 0) +
    (s.currency && s.salary_min ? 1 : 0) + (s.has_salary ? 1 : 0) + (s.posted_within ? 1 : 0) +
    (s.hide_unclear ? 1 : 0) + (s.include_worldwide ? 0 : 1)
  );
}

/** State + updater. Any change other than `page` / `job` resets to page 1. */
export function useUrlState() {
  const [state, setState] = useState<SearchState>(() => fromUrl(location.search));

  useEffect(() => {
    const onPop = () => setState(fromUrl(location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const current = useRef(state);
  current.current = state;

  const update = useCallback((patch: Partial<SearchState>, opts: { push?: boolean } = {}) => {
    const next = { ...current.current, ...patch };
    if (!("page" in patch) && Object.keys(patch).some((k) => k !== "job")) next.page = 1;
    history[opts.push ? "pushState" : "replaceState"](null, "", toUrl(next));
    if (patch.region) {
      try {
        localStorage.setItem(REGION_PREF, patch.region);
      } catch {
        /* storage unavailable: the URL still holds the region */
      }
    }
    current.current = next;
    setState(next);
  }, []);

  return [state, update] as const;
}
