// Results area (DESIGN-UIUX.md §2.1, §2.4, §3): toolbar with chips + sort, table (≥768px), cards (mobile).
import { type ReactNode, useState } from "react";
import { SourceBadge, logoKey } from "./SourceBadge";
import type { SearchState } from "../hooks/useUrlState";
import {
  CATEGORY_LABEL, MODE_LABEL, SENIORITY_LABEL, TYPE_LABEL, duration, fullDate, locationLabel, money, relTime, typeKey,
} from "../lib/format";
import type { JobSummary, Sort } from "../lib/types";

export interface Labels {
  region: (code: string) => string;
  source: (name: string) => string;
  country: (cc: string) => string;
}

const TYPE_VAR: Record<string, string> = {
  fulltime: "--t-fulltime", parttime: "--t-parttime", contract: "--t-contract", freelance: "--t-freelance",
  gig: "--t-gig", internship: "--t-internship", temporary: "--t-contract", unknown: "--t-unknown",
};

function CompanyLogo({ job }: { job: JobSummary }) {
  const [broken, setBroken] = useState(false);
  if (!job.company_logo || broken) return null;
  return (
    <img
      src={job.company_logo}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
      className="mr-1.5 inline-block h-5 w-5 shrink-0 rounded object-contain align-text-bottom"
    />
  );
}

export function TypeBadge({ job }: { job: JobSummary }) {
  const key = typeKey(job);
  if (key === "unknown") return <span className="text-muted">—</span>;
  const color = `var(${TYPE_VAR[key]})`;
  return (
    <span
      className="inline-block whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium"
      style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
    >
      {TYPE_LABEL[key]}
    </span>
  );
}

function Money({ job }: { job: JobSummary }) {
  const m = money(job.salary, job.budget);
  if (!m) return <span className="text-muted">—</span>;
  return (
    <span className="whitespace-nowrap tabular-nums" title={m.hint}>
      {m.text}
    </span>
  );
}

function Posted({ job }: { job: JobSummary }) {
  const iso = job.posted_at ?? job.first_seen_at;
  const rel = relTime(iso);
  if (!rel) return <span className="text-muted">—</span>;
  return (
    <time dateTime={iso!} title={`${job.posted_at ? "Posted" : "First seen"} ${fullDate(iso)}`} className="whitespace-nowrap">
      {rel}
    </time>
  );
}

function SourceCell({ job, labels }: { job: JobSummary; labels: Labels }) {
  return (
    <span className="whitespace-nowrap text-muted">
      {labels.source(job.source)}
      {job.duplicate_count > 0 && (
        <span title={`Also on ${job.duplicate_count} other source(s)`} className="ml-1 text-xs">
          +{job.duplicate_count}
        </span>
      )}
    </span>
  );
}

function jobHref(id: string): string {
  const p = new URLSearchParams(location.search);
  p.set("job", id);
  return `?${p}`;
}

/** Opens the drawer; a real link so middle-click / copy-link still work. */
function Title({ job, onOpen }: { job: JobSummary; onOpen: (id: string) => void }) {
  return (
    <a
      href={jobHref(job.id)}
      onClick={(e) => {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        onOpen(job.id);
      }}
      className="font-semibold hover:text-accent hover:underline"
      title={job.title}
    >
      {job.title}
    </a>
  );
}

export interface RowProps {
  items: JobSummary[];
  labels: Labels;
  openId: string;
  cursor: number;
  onOpen: (id: string) => void;
  onUpdateStatus?: (id: string, status: "keep" | "removed" | null) => void;
}

const rowState = (j: JobSummary, i: number, openId: string, cursor: number) =>
  j.id === openId ? "bg-accent/10" : i === cursor ? "bg-surface outline outline-1 -outline-offset-1 outline-accent/40" : "";

function Skills({ job }: { job: JobSummary }) {
  if (!job.skills.length) return null;
  return (
    <span className="truncate text-[13px] text-muted">
      {job.skills.slice(0, 3).join(" · ")}
      {job.skills.length > 3 && ` +${job.skills.length - 3}`}
    </span>
  );
}

export interface ColumnDef {
  id: string;
  label: string;
  weight: number; // relative width
  required?: boolean; // always shown, cannot be hidden
  render: (j: JobSummary, labels: Labels, onOpen: (id: string) => void) => ReactNode;
  cellClass?: string;
}

export const COLUMNS: ColumnDef[] = [
  {
    id: "title", label: "Title", weight: 32, required: true,
    render: (j, _l, onOpen) => (
      <div className="flex flex-col">
        <span className="truncate"><CompanyLogo job={j} /><Title job={j} onOpen={onOpen} /></span>
        <Skills job={j} />
      </div>
    ),
  },
  {
    id: "company", label: "Company", weight: 16, cellClass: "truncate",
    render: (j) => j.company ?? <span className="text-muted">{j.category === "gig" ? "(individual)" : "—"}</span>,
  },
  { id: "pay", label: "Salary / Budget", weight: 14, render: (j) => <Money job={j} /> },
  { id: "type", label: "Type", weight: 9, render: (j) => <TypeBadge job={j} /> },
  {
    id: "duration", label: "Duration", weight: 7, cellClass: "whitespace-nowrap",
    render: (j) => duration(j.duration) ?? <span className="text-muted">—</span>,
  },
  {
    id: "where", label: "Location · Source · Posted", weight: 20,
    render: (j, labels) => (
      <div className="flex flex-col">
        <span className="truncate" title={j.location.raw ?? j.remote_scope?.raw ?? undefined}>
          {locationLabel(j, labels.region)}
        </span>
        <span className="flex gap-2 text-[13px]">
          <SourceCell job={j} labels={labels} />
          <span className="text-muted">·</span>
          <span className="text-muted"><Posted job={j} /></span>
        </span>
      </div>
    ),
  },
  {
    id: "location", label: "Location", weight: 12, cellClass: "truncate",
    render: (j, labels) => locationLabel(j, labels.region),
  },
  { id: "source", label: "Source", weight: 10, render: (j, labels) => <SourceCell job={j} labels={labels} /> },
  { id: "posted", label: "Posted", weight: 8, cellClass: "whitespace-nowrap", render: (j) => <Posted job={j} /> },
  {
    id: "seniority", label: "Seniority", weight: 8, cellClass: "whitespace-nowrap",
    render: (j) => (j.seniority !== "unknown" ? SENIORITY_LABEL[j.seniority] : <span className="text-muted">—</span>),
  },
];

/** Columns the table starts with (the rest are opt-in from the Columns menu). */
export const DEFAULT_COLUMNS = ["title", "company", "pay", "type", "duration", "where"];

export function ResultsTable({ items, labels, openId, cursor, onOpen, onUpdateStatus, columns = DEFAULT_COLUMNS }: RowProps & { columns?: string[] }) {
  const cols = columns.map((id) => COLUMNS.find((c) => c.id === id)).filter((c): c is ColumnDef => !!c);
  const total = cols.reduce((n, c) => n + c.weight, 0);
  return (
    <table className="w-full table-fixed border-collapse text-sm">
      <colgroup>
        <col className="w-[52px]" />
        <col className="w-[44px]" />
        {cols.map((c) => (
          <col key={c.id} style={{ width: `${(c.weight / total) * 100}%` }} />
        ))}
      </colgroup>
      <thead className="sticky top-0 z-10 bg-bg text-left text-xs text-muted">
        <tr className="border-b border-border">
          <th className="px-1 py-2 text-center font-medium">Tag</th>
          <th className="px-1 py-2 text-center font-medium" title="Source logo">Src</th>
          {cols.map((c) => (
            <th key={c.id} className="px-3 py-2 font-medium">{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {items.map((j, i) => (
          <tr
            key={j.id}
            data-job-row={i}
            aria-selected={j.id === openId}
            onClick={(e) => !(e.target as Element).closest("a, button") && onOpen(j.id)}
            className={`h-[var(--row-h)] cursor-pointer border-b border-border align-top hover:bg-surface ${rowState(j, i, openId, cursor)}`}
          >
            <td className="px-1 py-2 text-center" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-center gap-1 pt-0.5">
                <button
                  type="button"
                  title={j.user_status === "keep" ? "Remove keep tag" : "Keep (Save) this job"}
                  onClick={() => onUpdateStatus?.(j.id, j.user_status === "keep" ? null : "keep")}
                  className={`text-base leading-none transition-transform active:scale-125 ${
                    j.user_status === "keep" ? "text-amber-500 hover:text-amber-600" : "text-muted/40 hover:text-amber-500"
                  }`}
                >
                  ★
                </button>
                <button
                  type="button"
                  title={j.user_status === "removed" ? "Restore removed job" : "Remove / Hide this job"}
                  onClick={() => onUpdateStatus?.(j.id, j.user_status === "removed" ? null : "removed")}
                  className={`text-xs leading-none transition-colors ${
                    j.user_status === "removed" ? "font-bold text-accent" : "text-muted/40 hover:text-danger"
                  }`}
                >
                  {j.user_status === "removed" ? "↺" : "✕"}
                </button>
              </div>
            </td>
            <td className="px-1 py-2 text-center">
              <div className="flex justify-center pt-0.5">
                <SourceBadge
                  logo={logoKey(j)}
                  label={j.provider && j.source === "jobspy" ? `${labels.source(j.source)} · ${j.provider}` : labels.source(j.source)}
                />
              </div>
            </td>
            {cols.map((c) => (
              <td key={c.id} className={`px-3 py-2 ${c.cellClass ?? ""}`}>
                {c.render(j, labels, onOpen)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ResultsCards({ items, labels, openId, cursor, onOpen, onUpdateStatus }: RowProps) {
  return (
    <ul className="divide-y divide-border">
      {items.map((j, i) => (
        <li
          key={j.id}
          data-job-row={i}
          onClick={(e) => !(e.target as Element).closest("a, button") && onOpen(j.id)}
          className={`cursor-pointer space-y-1 px-4 py-3 ${rowState(j, i, openId, cursor)}`}
        >
          <div className="flex items-start justify-between gap-2 leading-snug">
            <Title job={j} onOpen={onOpen} />
            <div className="flex shrink-0 items-center gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                title={j.user_status === "keep" ? "Remove keep tag" : "Keep (Save) this job"}
                onClick={() => onUpdateStatus?.(j.id, j.user_status === "keep" ? null : "keep")}
                className={`text-lg leading-none ${
                  j.user_status === "keep" ? "text-amber-500" : "text-muted hover:text-amber-500"
                }`}
              >
                ★
              </button>
              <button
                type="button"
                title={j.user_status === "removed" ? "Restore removed job" : "Remove / Hide this job"}
                onClick={() => onUpdateStatus?.(j.id, j.user_status === "removed" ? null : "removed")}
                className={`text-xs ${
                  j.user_status === "removed" ? "font-bold text-accent" : "text-muted hover:text-danger"
                }`}
              >
                {j.user_status === "removed" ? "↺ Restore" : "✕"}
              </button>
            </div>
          </div>
          {j.company && <div className="text-muted">{j.company}</div>}
          {money(j.salary, j.budget) && (
            <div>
              💰 <Money job={j} />
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <TypeBadge job={j} />
            <span className="text-[13px]">{locationLabel(j, labels.region)}</span>
          </div>
          <div className="flex gap-2 text-[13px] text-muted">
            <span>⏱ {duration(j.duration) ?? "—"}</span>·<SourceCell job={j} labels={labels} />·<Posted job={j} />
          </div>
        </li>
      ))}
    </ul>
  );
}

const SORTS: [Sort, string][] = [
  ["relevance", "Relevance"],
  ["newest", "Newest"],
  ["salary_desc", "Salary (high → low)"],
  ["company", "Company A–Z"],
];

export function SortSelect({ s, effective, update }: { s: SearchState; effective: Sort; update: (p: Partial<SearchState>) => void }) {
  return (
    <label className="flex items-center gap-1 text-muted">
      <span className="hidden sm:inline">Sort:</span>
      <select
        value={effective}
        onChange={(e) => update({ sort: e.target.value as Sort })}
        className="h-8 rounded-ui border border-border bg-surface px-2 text-fg"
      >
        {SORTS.map(([v, label]) => (
          <option
            key={v}
            value={v}
            disabled={(v === "salary_desc" && !s.currency) || (v === "relevance" && !s.q.trim())}
            title={v === "salary_desc" && !s.currency ? "Pick a currency to sort/filter by salary" : undefined}
          >
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}

interface Chip {
  key: string;
  label: string;
  clear: Partial<SearchState>;
}

export function activeChips(s: SearchState, labels: Labels): Chip[] {
  const chips: Chip[] = [];
  if (s.region !== "ALL") chips.push({ key: "region", label: `Region: ${labels.region(s.region)}`, clear: { region: "ALL", country: [] } });
  if (s.q.trim()) chips.push({ key: "q", label: s.q.trim(), clear: { q: "" } });
  if (s.category) chips.push({ key: "cat", label: CATEGORY_LABEL[s.category] ?? s.category, clear: { category: "" } });
  const list = (key: "type" | "mode" | "source" | "country" | "seniority", label: (v: string) => string) =>
    s[key].forEach((v) => chips.push({ key: `${key}:${v}`, label: label(v), clear: { [key]: s[key].filter((x) => x !== v) } }));
  list("type", (v) => TYPE_LABEL[v as keyof typeof TYPE_LABEL] ?? v);
  list("mode", (v) => MODE_LABEL[v] ?? v);
  list("country", labels.country);
  list("source", labels.source);
  list("seniority", (v) => SENIORITY_LABEL[v] ?? v);
  if (s.user_status === "keep") chips.push({ key: "st_keep", label: "Status: ★ Kept", clear: { user_status: "" } });
  else if (s.user_status === "removed") chips.push({ key: "st_rem", label: "Status: ✕ Removed", clear: { user_status: "" } });
  else if (s.user_status === "all") chips.push({ key: "st_all", label: "Status: All", clear: { user_status: "" } });
  if (s.scan_run_id) chips.push({ key: "scan_run", label: `Scan run: ${s.scan_run_id.slice(0, 16)}`, clear: { scan_run_id: "" } });
  if (s.posted_within) chips.push({ key: "posted", label: `Posted ≤ ${Number(s.posted_within) >= 48 ? `${Number(s.posted_within) / 24}d` : `${s.posted_within}h`}`, clear: { posted_within: "" } });
  if (s.currency) chips.push({ key: "cur", label: s.currency, clear: { currency: "", salary_min: "", sort: s.sort === "salary_desc" ? "" : s.sort } });
  if (s.currency && s.salary_min) chips.push({ key: "min", label: `≥ ${s.currency} ${Number(s.salary_min).toLocaleString("en-US")}`, clear: { salary_min: "" } });
  if (s.has_salary) chips.push({ key: "has", label: "Has salary", clear: { has_salary: false } });
  if (!s.include_worldwide) chips.push({ key: "iw", label: "No worldwide remote", clear: { include_worldwide: true } });
  if (s.hide_unclear) chips.push({ key: "hu", label: "Hide unclear remote", clear: { hide_unclear: false } });
  return chips;
}

export function Chips({ chips, update }: { chips: Chip[]; update: (p: Partial<SearchState>) => void }) {
  return (
    <>
      {chips.map((c) => (
        <button
          key={c.key}
          type="button"
          onClick={() => update(c.clear)}
          className="flex h-7 max-w-56 items-center gap-1 rounded-full border border-border bg-surface px-2.5 text-xs hover:border-muted"
          aria-label={`Remove filter ${c.label}`}
        >
          <span className="truncate">{c.label}</span>
          <span aria-hidden className="text-muted">✕</span>
        </button>
      ))}
    </>
  );
}

export function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null;
  const nums = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const sorted = [...nums].sort((a, b) => a - b);
  const btn = "h-8 min-w-8 rounded-ui border border-border px-2 tabular-nums hover:bg-surface disabled:opacity-40";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1 py-4">
      <button type="button" className={btn} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
        ←
      </button>
      {sorted.map((n, i) => (
        <span key={n} className="flex items-center gap-1">
          {i > 0 && n - sorted[i - 1] > 1 && <span className="px-1 text-muted">…</span>}
          <button
            type="button"
            className={`${btn} ${n === page ? "border-accent bg-accent text-accent-fg hover:bg-accent" : ""}`}
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
          >
            {n}
          </button>
        </span>
      ))}
      <button type="button" className={btn} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
        →
      </button>
    </nav>
  );
}

export function SkeletonRows({ n = 8 }: { n?: number }) {
  return (
    <div aria-hidden className="divide-y divide-border">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="flex h-[var(--row-h)] items-center gap-4 px-3">
          <div className="h-3 w-1/3 animate-pulse rounded bg-surface" />
          <div className="h-3 w-1/6 animate-pulse rounded bg-surface" />
          <div className="h-3 w-1/6 animate-pulse rounded bg-surface" />
          <div className="h-3 w-1/12 animate-pulse rounded bg-surface" />
        </div>
      ))}
    </div>
  );
}
