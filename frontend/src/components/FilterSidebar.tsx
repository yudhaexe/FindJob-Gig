// Filter sidebar (DESIGN-UIUX.md §2.1). Facet counts come from /api/jobs and ignore their own group.
import { type ReactNode, useEffect, useState } from "react";
import type { SearchState } from "../hooks/useUrlState";
import { api } from "../lib/api";
import { MODE_LABEL, SENIORITY_LABEL, TYPE_LABEL } from "../lib/format";
import type { RegionsResponse, Run } from "../lib/types";

type Facets = Record<string, Record<string, number>>;
type ListKey = "type" | "mode" | "source" | "country" | "seniority";

const POSTED = [
  ["24", "24h"],
  ["72", "3d"],
  ["168", "7d"],
  ["720", "30d"],
  ["", "Any"],
] as const;

const PERIODS = [
  ["hour", "/hr"],
  ["day", "/day"],
  ["week", "/wk"],
  ["month", "/mo"],
  ["year", "/yr"],
  ["fixed", "fixed"],
] as const;

function Group({ title, children, open = true }: { title: string; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group border-b border-border py-3 last:border-0">
      <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
        <span aria-hidden className="transition-transform group-open:rotate-90">▸</span>
      </summary>
      <div className="mt-2 space-y-1">{children}</div>
    </details>
  );
}

function Check({
  label,
  checked,
  onChange,
  count,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
  count?: number;
}) {
  return (
    <label className="flex min-h-7 cursor-pointer items-center gap-2 rounded px-1 hover:bg-surface">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="accent-accent" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {count !== undefined && <span className="text-xs tabular-nums text-muted">{count.toLocaleString("en-US")}</span>}
    </label>
  );
}

function formatRunLabel(run: Run): string {
  const dt = run.started_at ? new Date(run.started_at) : null;
  const timeStr = dt
    ? dt.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) +
      " " +
      dt.toLocaleDateString("id-ID", { day: "2-digit", month: "short" })
    : run.id;
  const totalNew = Object.values(run.sources).reduce((acc, s) => acc + (s.new || 0), 0);
  const totalFetched = Object.values(run.sources).reduce((acc, s) => acc + (s.fetched || 0), 0);
  const statusIcon = run.status === "failed" ? "❌ " : run.status === "partial" ? "⚠️ " : "";
  return `${statusIcon}${timeStr} (${totalNew} new / ${totalFetched} fetched)`;
}

export function FilterSidebar({
  s,
  update,
  facets,
  regions,
  sourceNames,
  retryRuns = 0,
  onReset,
}: {
  s: SearchState;
  update: (patch: Partial<SearchState>) => void;
  facets: Facets;
  regions: RegionsResponse | null;
  sourceNames: Record<string, string>;
  retryRuns?: number;
  onReset: () => void;
}) {
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    let cancel = false;
    api
      .runs(40)
      .then((res) => {
        if (!cancel) setRuns(res);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [retryRuns]);

  const toggle = (key: ListKey, value: string, on: boolean) =>
    update({ [key]: on ? [...s[key], value] : s[key].filter((v) => v !== value) });

  /** Facet values (most common first) plus any selected value that currently has no hits. */
  const values = (key: ListKey | "currency", limit = 50): [string, number][] => {
    const f = facets[key] ?? {};
    const selected = key === "currency" ? (s.currency ? [s.currency] : []) : s[key];
    const entries = Object.entries(f).slice(0, limit);
    for (const v of selected) if (!(v in f)) entries.push([v, 0]);
    return entries;
  };

  const list = (key: ListKey, label: (v: string) => string, limit?: number) =>
    values(key, limit).map(([v, n]) => (
      <Check key={v} label={label(v)} count={n} checked={s[key].includes(v)} onChange={(on) => toggle(key, v, on)} />
    ));

  const regionCountries = regions?.regions.find((r) => r.code === s.region)?.countries;
  const countryName = (cc: string) => regions?.countries[cc]?.name ?? cc;
  const countryList = values("country").filter(([cc]) => !regionCountries || regionCountries.includes(cc) || s.country.includes(cc));
  const salaryDisabled = !s.currency;

  return (
    <div className="text-sm">
      <div className="flex items-center justify-between pb-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide">Filters</h2>
        <button type="button" onClick={onReset} className="text-xs text-accent hover:underline">
          Reset
        </button>
      </div>

      <Group title="Status (Keep / Remove)">
        <div className="flex flex-wrap gap-1">
          {[
            ["", "Active"],
            ["keep", "★ Kept"],
            ["removed", "✕ Removed"],
            ["all", "All"],
          ].map(([val, label]) => (
            <button
              key={val}
              type="button"
              onClick={() => update({ user_status: val })}
              className={`h-7 rounded-ui border px-2 text-xs transition-colors ${
                s.user_status === val
                  ? "border-accent bg-accent text-accent-fg font-medium"
                  : "border-border hover:bg-surface"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </Group>

      <Group title="Scan History (Jam Scraping)" open={!!s.scan_run_id || runs.length > 0}>
        <div className="space-y-1.5">
          <select
            value={s.scan_run_id}
            onChange={(e) => update({ scan_run_id: e.target.value })}
            className="h-8 w-full rounded-ui border border-border bg-surface px-2 text-xs"
          >
            <option value="">All scans / runs (Semua)</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {formatRunLabel(r)}
              </option>
            ))}
          </select>
          {s.scan_run_id && (
            <div className="flex items-center justify-between text-xs text-muted">
              <span>Filtering by scan run</span>
              <button
                type="button"
                onClick={() => update({ scan_run_id: "" })}
                className="text-accent hover:underline"
              >
                Clear
              </button>
            </div>
          )}
        </div>
      </Group>

      <Group title="Region">
        <Check
          label="Include worldwide remote"
          checked={s.include_worldwide}
          onChange={(v) => update({ include_worldwide: v })}
        />
        <Check label="Hide unclear remote scope" checked={s.hide_unclear} onChange={(v) => update({ hide_unclear: v })} />
      </Group>

      <Group title="Type">{list("type", (v) => (v === "unknown" ? "Not specified" : TYPE_LABEL[v as keyof typeof TYPE_LABEL] ?? v))}</Group>

      <Group title="Work mode">{list("mode", (v) => MODE_LABEL[v] ?? v)}</Group>

      <Group title={s.region === "ALL" ? "Country" : "Country (in region)"} open={s.region !== "ALL"}>
        {countryList.length ? (
          countryList.map(([cc, n]) => (
            <Check
              key={cc}
              label={countryName(cc)}
              count={n}
              checked={s.country.includes(cc)}
              onChange={(on) => toggle("country", cc, on)}
            />
          ))
        ) : (
          <p className="px-1 text-muted">No country data</p>
        )}
      </Group>

      <Group title="Source">{list("source", (v) => sourceNames[v] ?? v)}</Group>

      <Group title="Posted">
        <div role="radiogroup" aria-label="Posted within" className="flex flex-wrap gap-1">
          {POSTED.map(([v, label]) => (
            <button
              key={label}
              type="button"
              role="radio"
              aria-checked={s.posted_within === v}
              onClick={() => update({ posted_within: v })}
              className={`h-7 rounded-ui border px-2 text-xs ${
                s.posted_within === v ? "border-accent bg-accent text-accent-fg" : "border-border hover:bg-surface"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </Group>

      <Group title="Salary / budget">
        <label className="block text-xs text-muted" htmlFor="f-currency">
          Currency
        </label>
        <select
          id="f-currency"
          value={s.currency}
          onChange={(e) => update({ currency: e.target.value, ...(e.target.value ? {} : { sort: s.sort === "salary_desc" ? "" : s.sort }) })}
          className="h-8 w-full rounded-ui border border-border bg-surface px-2"
        >
          <option value="">Any</option>
          {values("currency").map(([c, n]) => (
            <option key={c} value={c}>
              {c} ({n})
            </option>
          ))}
        </select>
        <label className="mt-2 block text-xs text-muted" htmlFor="f-min">
          Min salary
        </label>
        <div className="flex gap-1" title={salaryDisabled ? "Pick a currency to sort/filter by salary" : undefined}>
          <input
            id="f-min"
            type="number"
            min={0}
            inputMode="numeric"
            disabled={salaryDisabled}
            value={s.salary_min}
            onChange={(e) => update({ salary_min: e.target.value })}
            placeholder={salaryDisabled ? "Pick a currency" : "0"}
            className="h-8 min-w-0 flex-1 rounded-ui border border-border bg-surface px-2 disabled:opacity-50"
          />
          <select
            aria-label="Salary period"
            disabled={salaryDisabled}
            value={s.salary_period}
            onChange={(e) => update({ salary_period: e.target.value })}
            className="h-8 rounded-ui border border-border bg-surface px-1 disabled:opacity-50"
          >
            {PERIODS.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <Check label="Has salary / budget" checked={s.has_salary} onChange={(v) => update({ has_salary: v })} />
      </Group>

      <Group title="Seniority" open={s.seniority.length > 0}>
        {list("seniority", (v) => SENIORITY_LABEL[v] ?? v)}
      </Group>
    </div>
  );
}
