import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ColumnMenu, useColumns } from "./components/ColumnMenu";
import { FilterSidebar } from "./components/FilterSidebar";
import { JobDrawer } from "./components/JobDrawer";
import { RegionSelect, regionLabel } from "./components/RegionSelect";
import {
  Chips, Pagination, ResultsCards, ResultsTable, SkeletonRows, SortSelect, activeChips, type Labels,
} from "./components/Results";
import { SchedulesPanel, useSchedules } from "./components/SchedulesPanel";
import { ScrapeModal } from "./components/ScrapeModal";
import { useDebounced, useJobs, useRegions, useSources } from "./hooks/useApi";
import { isActive, runProgress, useScrapeRun } from "./hooks/useScrapeRun";
import { DEFAULTS, activeFilterCount, toApiParams, useUrlState, type SearchState } from "./hooks/useUrlState";
import { api, exportUrl } from "./lib/api";
import { relTime } from "./lib/format";
import type { Run, Schedule, ScrapeQuery } from "./lib/types";

const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable);

/** Positive words of the search box, as scrape keywords. */
const queryKeywords = (q: string) =>
  [...q.matchAll(/(-?)"([^"]+)"|(-?)(\S+)/g)]
    .filter((m) => !m[1] && !m[3])
    .map((m) => (m[2] ?? m[4]).replace(/\*+$/, ""))
    .filter(Boolean);

const PAGE_SIZE = 50;

export default function App() {
  const [s, update] = useUrlState();
  const [columns, setColumns] = useColumns();
  const [retry, setRetry] = useState(0);
  const [sheet, setSheet] = useState(false);
  const jobs = useJobs(s, PAGE_SIZE, retry);
  const regions = useRegions(s.include_worldwide, s.hide_unclear, retry);
  const sources = useSources(retry);
  const [scrapeInit, setScrapeInit] = useState<Partial<ScrapeQuery> | null>(null);
  const [toast, setToast] = useState<Run | null>(null);
  const [cursor, setCursor] = useState(-1);
  const [schedulesOpen, setSchedulesOpen] = useState(false);
  const schedules = useSchedules();

  const onRunFinish = useCallback((run: Run) => {
    setRetry((n) => n + 1);
    setToast(run);
  }, []);
  const scrape = useScrapeRun(onRunFinish);

  const onUpdateStatus = useCallback(async (jobId: string, status: "keep" | "removed" | null) => {
    try {
      await api.updateJobStatus(jobId, status);
      setRetry((n) => n + 1);
    } catch (e) {
      console.error("Failed to update job status", e);
    }
  }, []);

  const sourceNames = useMemo(
    () => Object.fromEntries((sources.data?.sources ?? []).map((x) => [x.name, x.display_name])),
    [sources.data],
  );
  const labels: Labels = useMemo(
    () => ({
      region: (c) => regionLabel(regions.data, c),
      source: (n) => sourceNames[n] ?? n,
      country: (cc) => regions.data?.countries[cc]?.name ?? cc,
    }),
    [regions.data, sourceNames],
  );
  const attribution = useCallback(
    (name: string) => sources.data?.sources.find((x) => x.name === name)?.attribution ?? null,
    [sources.data],
  );

  const page = jobs.data;
  const pages = page ? Math.ceil(page.total / page.page_size) : 0;
  const chips = activeChips(s, labels);
  const reset = () => update({ ...DEFAULTS, q: s.q, region: s.region });
  const nothingStored = sources.data?.total === 0;

  useEffect(() => {
    if (page && s.page > 1 && s.page > pages) update({ page: Math.max(1, pages) });
  }, [page, pages, s.page, update]);

  // ── drawer + keyboard (DESIGN-UIUX.md §4) ──
  const items = useMemo(() => page?.items ?? [], [page]);
  const openIndex = items.findIndex((j) => j.id === s.job);
  // Opening pushes a history entry (Back closes the drawer); switching jobs replaces it.
  const openJob = useCallback((id: string) => update({ job: id }, { push: !s.job }), [s.job, update]);
  const closeJob = useCallback(() => update({ job: "" }), [update]);
  const openScrape = useCallback(
    (init: Partial<ScrapeQuery> = {}) => setScrapeInit({ region: s.region, ...init }),
    [s.region],
  );

  useEffect(() => setCursor(-1), [items]);
  useEffect(() => {
    if (openIndex >= 0) setCursor(openIndex);
  }, [openIndex]);
  useEffect(() => {
    if (cursor < 0) return;
    const rows = [...document.querySelectorAll<HTMLElement>(`[data-job-row="${cursor}"]`)];
    rows.find((r) => r.offsetParent !== null)?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target) || e.ctrlKey || e.metaKey || e.altKey || scrapeInit) return;
      if (e.key === "S" && e.shiftKey) {
        e.preventDefault();
        openScrape();
        return;
      }
      if (s.job) return; // the drawer handles its own keys
      if (e.key === "j" || e.key === "ArrowDown") setCursor((c) => Math.min(items.length - 1, c + 1));
      else if (e.key === "k" || e.key === "ArrowUp") setCursor((c) => Math.max(0, c - 1));
      else if (e.key === "Enter" && items[cursor] && !(e.target instanceof Element && e.target.closest("a, button"))) openJob(items[cursor].id);
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [items, cursor, s.job, scrapeInit, openJob, openScrape]);

  const { run: activeRun, dismiss } = scrape;
  const closeScrape = useCallback(() => {
    setScrapeInit(null);
    if (!isActive(activeRun)) dismiss();
  }, [activeRun, dismiss]);
  const showNewest = useCallback(() => {
    setToast(null);
    closeScrape();
    update({ ...DEFAULTS, region: s.region, sort: "newest" }, { push: true });
  }, [closeScrape, update, s.region]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <div className="flex h-dvh flex-col">
      <Header
        s={s}
        update={update}
        regions={regions.data}
        lastFetched={sources.data?.last_fetched ?? null}
        run={scrape.run}
        onScrape={() => openScrape()}
        schedules={schedules.items}
        onSchedules={() => setSchedulesOpen(true)}
      />

      {jobs.error && (
        <div role="alert" className="flex items-center gap-3 border-b border-danger/30 bg-danger/10 px-4 py-2 text-danger">
          Couldn't load jobs ({jobs.error}).
          <button type="button" onClick={() => setRetry((n) => n + 1)} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-border px-4 py-3 lg:block">
          <FilterSidebar
            s={s}
            update={update}
            facets={page?.facets ?? {}}
            regions={regions.data}
            sourceNames={sourceNames}
            retryRuns={retry}
            onReset={reset}
          />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-border bg-bg px-4 py-2">
            <button
              type="button"
              onClick={() => setSheet(true)}
              className="h-8 rounded-ui border border-border px-3 lg:hidden"
            >
              Filters{activeFilterCount(s) ? ` (${activeFilterCount(s)})` : ""}
            </button>
            <span className="font-medium tabular-nums" aria-live="polite">
              {page ? `${page.total.toLocaleString("en-US")} result${page.total === 1 ? "" : "s"}` : "…"}
            </span>
            <Chips chips={chips} update={update} />
            <span className="ml-auto flex items-center gap-2">
              {page && page.total > 0 && (
                <span className="flex items-center gap-1 text-muted">
                  Export
                  {(["csv", "json"] as const).map((fmt) => (
                    <a
                      key={fmt}
                      href={exportUrl(fmt, toApiParams(s, 0))}
                      download
                      title={`Download all ${page.total.toLocaleString("en-US")} matching results as ${fmt.toUpperCase()}`}
                      className="flex h-8 items-center rounded-ui border border-border px-2 uppercase hover:bg-surface"
                    >
                      {fmt}
                    </a>
                  ))}
                </span>
              )}
              <ColumnMenu columns={columns} onChange={setColumns} />
              <SortSelect s={s} effective={page?.sort ?? (s.sort || "newest")} update={update} />
            </span>
          </div>

          <div className={jobs.loading && page ? "opacity-60 transition-opacity" : ""}>
            {!page && jobs.loading ? (
              <SkeletonRows />
            ) : nothingStored ? (
              <Empty title="No jobs yet. Run your first scrape.">
                <div className="flex flex-wrap justify-center gap-2">
                  {(
                    [
                      ["ALL", "All regions"],
                      ["ID", "Indonesia"],
                      ["SEA", "SEA"],
                    ] as const
                  ).map(([region, label]) => (
                    <button
                      key={region}
                      type="button"
                      onClick={() => openScrape({ region })}
                      className="h-9 rounded-ui border border-border px-3 hover:bg-surface"
                    >
                      ▶ Scrape {label}
                    </button>
                  ))}
                </div>
              </Empty>
            ) : page && page.total === 0 ? (
              <NoResults s={s} update={update} labels={labels} onScrape={openScrape} />
            ) : page ? (
              <>
                <div className="hidden md:block">
                  <ResultsTable
                    items={page.items}
                    labels={labels}
                    openId={s.job}
                    cursor={cursor}
                    onOpen={openJob}
                    onUpdateStatus={onUpdateStatus}
                    columns={columns}
                  />
                </div>
                <div className="md:hidden">
                  <ResultsCards
                    items={page.items}
                    labels={labels}
                    openId={s.job}
                    cursor={cursor}
                    onOpen={openJob}
                    onUpdateStatus={onUpdateStatus}
                  />
                </div>
                <Pagination page={s.page} pages={pages} onPage={(p) => update({ page: p }, { push: true })} />
              </>
            ) : null}
          </div>
        </main>
      </div>

      {s.job && (
        <JobDrawer
          id={s.job}
          q={s.q}
          labels={labels}
          attribution={attribution}
          onClose={closeJob}
          onOpen={(id) => update({ job: id })}
          onPrev={openIndex > 0 ? () => update({ job: items[openIndex - 1].id }) : undefined}
          onNext={openIndex >= 0 && openIndex < items.length - 1 ? () => update({ job: items[openIndex + 1].id }) : undefined}
          onUpdateStatus={onUpdateStatus}
        />
      )}

      {scrapeInit && (
        <ScrapeModal
          initial={scrapeInit}
          regions={regions.data}
          run={scrape.run}
          sourceLabel={labels.source}
          onStart={scrape.start}
          onClose={closeScrape}
          onViewResults={showNewest}
          onScheduleSaved={schedules.reload}
        />
      )}

      {schedulesOpen && (
        <SchedulesPanel items={schedules.items} error={schedules.error} reload={schedules.reload} onClose={() => setSchedulesOpen(false)} />
      )}

      {toast && !scrapeInit && <RunToast run={toast} onView={showNewest} onClose={() => setToast(null)} />}

      {sheet && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSheet(false)} />
          <div className="absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto rounded-t-xl bg-bg px-4 pb-4 pt-2 shadow-xl">
            <div className="sticky top-0 flex justify-end bg-bg py-1">
              <button type="button" onClick={() => setSheet(false)} className="h-10 rounded-ui px-3 font-medium text-accent">
                Done
              </button>
            </div>
            <FilterSidebar
              s={s}
              update={update}
              facets={page?.facets ?? {}}
              regions={regions.data}
              sourceNames={sourceNames}
              retryRuns={retry}
              onReset={reset}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Header({
  s,
  update,
  regions,
  lastFetched,
  run,
  onScrape,
  schedules,
  onSchedules,
}: {
  s: SearchState;
  update: (p: Partial<SearchState>, opts?: { push?: boolean }) => void;
  regions: Parameters<typeof RegionSelect>[0]["data"];
  lastFetched: string | null;
  run: Run | null;
  onScrape: () => void;
  schedules: Schedule[];
  onSchedules: () => void;
}) {
  const paused = schedules.filter((x) => !x.enabled && x.paused_reason).length;
  const [text, setText] = useState(s.q);
  const sent = useRef(s.q);
  const debounced = useDebounced(text, 250);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (debounced !== sent.current) {
      sent.current = debounced;
      update({ q: debounced });
    }
  }, [debounced, update]);

  // External changes (chip removed, back button) overwrite the box.
  useEffect(() => {
    if (s.q !== sent.current) {
      sent.current = s.q;
      setText(s.q);
    }
  }, [s.q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const updated = relTime(lastFetched);

  return (
    <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
      <a href="/" className="flex items-center gap-2 font-semibold">
        <img src="/favicon.svg" alt="" className="h-6 w-6" />
        <span className="hidden sm:inline">FindJob&amp;Gig</span>
      </a>
      <RegionSelect value={s.region} data={regions} onChange={(region) => update({ region, country: [] }, { push: true })} />
      <div className="relative order-last w-full sm:order-none sm:w-auto sm:min-w-0 sm:flex-1">
        <input
          ref={input}
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              sent.current = text;
              update({ q: text });
            }
          }}
          placeholder='Search… e.g. video editor -wedding "after effects" photo*'
          aria-label="Search jobs"
          title={'Words are ANDed · -word excludes · "quoted phrase" · word* matches prefixes · press / to focus'}
          className="h-9 w-full rounded-ui border border-border bg-surface px-3"
        />
      </div>
      <div role="radiogroup" aria-label="Category" className="flex h-9 overflow-hidden rounded-ui border border-border">
        {(
          [
            ["job", "Jobs"],
            ["gig", "Gigs"],
            ["", "All"],
          ] as const
        ).map(([v, label]) => (
          <button
            key={label}
            type="button"
            role="radio"
            aria-checked={s.category === v}
            onClick={() => update({ category: v })}
            className={`px-3 ${s.category === v ? "bg-accent text-accent-fg" : "hover:bg-surface"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {updated && (
        <span className="hidden text-xs text-muted md:inline" title={lastFetched ?? undefined}>
          Updated {updated} ago
        </span>
      )}
      <button
        type="button"
        onClick={onSchedules}
        title="Schedules"
        className={`h-9 rounded-ui border border-border px-3 hover:bg-surface ${paused ? "text-warning" : ""}`}
      >
        ⏱ {paused ? `${paused} paused` : schedules.length}
      </button>
      <button
        type="button"
        onClick={onScrape}
        title="Scrape now (Shift+S)"
        className="h-9 rounded-ui bg-accent px-3 font-medium text-accent-fg hover:opacity-90"
      >
        {run && isActive(run) ? (
          <span className="tabular-nums">
            <span className="inline-block animate-spin">⟳</span> {runProgress(run).done}/{runProgress(run).total}
          </span>
        ) : (
          "⟳ Scrape"
        )}
      </button>
    </header>
  );
}

function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
      <p className="text-lg font-medium">{title}</p>
      {children}
    </div>
  );
}

function NoResults({
  s,
  update,
  labels,
  onScrape,
}: {
  s: SearchState;
  update: (p: Partial<SearchState>) => void;
  labels: Labels;
  onScrape: (init: Partial<ScrapeQuery>) => void;
}) {
  const where = s.region === "ALL" ? "" : ` in ${labels.region(s.region)}`;
  const btn = "h-8 rounded-ui border border-border px-3 hover:bg-surface";
  return (
    <Empty title={s.q.trim() ? `No results for “${s.q.trim()}”${where}.` : `No results${where}.`}>
      <div className="flex flex-wrap justify-center gap-2">
        {s.region !== "ALL" && (
          <button type="button" className={btn} onClick={() => update({ region: "ALL", country: [] })}>
            Search All regions
          </button>
        )}
        {s.posted_within && Number(s.posted_within) < 720 && (
          <button type="button" className={btn} onClick={() => update({ posted_within: "720" })}>
            Extend to 30 days
          </button>
        )}
        {activeFilterCount(s) > 0 && (
          <button type="button" className={btn} onClick={() => update({ ...DEFAULTS, q: s.q, region: s.region })}>
            Clear filters
          </button>
        )}
        {queryKeywords(s.q).length > 0 && (
          <button type="button" className={btn} onClick={() => onScrape({ keywords: queryKeywords(s.q) })}>
            Scrape this keyword
          </button>
        )}
      </div>
    </Empty>
  );
}

function RunToast({ run, onView, onClose }: { run: Run; onView: () => void; onClose: () => void }) {
  const { newJobs } = runProgress(run);
  const failed = Object.values(run.sources).filter((r) => r.status === "error").length;
  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-ui border border-border bg-bg px-4 py-2.5 shadow-xl"
    >
      <span>
        {run.status === "failed" ? "Scrape failed" : `${newJobs} new job${newJobs === 1 ? "" : "s"}`}
        {failed > 0 && run.status !== "failed" && <span className="text-warning"> · {failed} source(s) failed</span>}
      </span>
      {run.status !== "failed" && (
        <button type="button" onClick={onView} className="font-medium text-accent hover:underline">
          View
        </button>
      )}
      <button type="button" onClick={onClose} aria-label="Dismiss" className="text-muted hover:text-fg">
        ✕
      </button>
    </div>
  );
}
