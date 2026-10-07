import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { FilterSidebar } from "./components/FilterSidebar";
import { RegionSelect, regionLabel } from "./components/RegionSelect";
import {
  Chips, Pagination, ResultsCards, ResultsTable, SkeletonRows, SortSelect, activeChips, type Labels,
} from "./components/Results";
import { useDebounced, useJobs, useRegions, useSources } from "./hooks/useApi";
import { DEFAULTS, activeFilterCount, useUrlState, type SearchState } from "./hooks/useUrlState";
import { relTime } from "./lib/format";

const PAGE_SIZE = 50;

export default function App() {
  const [s, update] = useUrlState();
  const [retry, setRetry] = useState(0);
  const [sheet, setSheet] = useState(false);
  const jobs = useJobs(s, PAGE_SIZE, retry);
  const regions = useRegions(s.include_worldwide, s.hide_unclear, retry);
  const sources = useSources(retry);

  const sourceNames = useMemo(
    () => Object.fromEntries((sources.data?.sources ?? []).map((x) => [x.name, x.display_name])),
    [sources.data],
  );
  const labels: Labels = {
    region: (c) => regionLabel(regions.data, c),
    source: (n) => sourceNames[n] ?? n,
    country: (cc) => regions.data?.countries[cc]?.name ?? cc,
  };

  const page = jobs.data;
  const pages = page ? Math.ceil(page.total / page.page_size) : 0;
  const chips = activeChips(s, labels);
  const reset = () => update({ ...DEFAULTS, q: s.q, region: s.region });
  const nothingStored = sources.data?.total === 0;

  useEffect(() => {
    if (page && s.page > 1 && s.page > pages) update({ page: Math.max(1, pages) });
  }, [page, pages, s.page, update]);

  return (
    <div className="flex h-dvh flex-col">
      <Header s={s} update={update} regions={regions.data} lastFetched={sources.data?.last_fetched ?? null} />

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
            <span className="ml-auto">
              <SortSelect s={s} effective={page?.sort ?? (s.sort || "newest")} update={update} />
            </span>
          </div>

          <div className={jobs.loading && page ? "opacity-60 transition-opacity" : ""}>
            {!page && jobs.loading ? (
              <SkeletonRows />
            ) : nothingStored ? (
              <Empty title="No jobs yet. Run your first scrape.">
                <p className="text-muted">
                  Scraping from the UI arrives in M3. For now run{" "}
                  <code className="rounded bg-surface px-1 font-mono">npm run fjg -- scrape --preset creative</code>
                </p>
              </Empty>
            ) : page && page.total === 0 ? (
              <NoResults s={s} update={update} labels={labels} />
            ) : page ? (
              <>
                <div className="hidden md:block">
                  <ResultsTable items={page.items} labels={labels} />
                </div>
                <div className="md:hidden">
                  <ResultsCards items={page.items} labels={labels} />
                </div>
                <Pagination page={s.page} pages={pages} onPage={(p) => update({ page: p }, { push: true })} />
              </>
            ) : null}
          </div>
        </main>
      </div>

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
}: {
  s: SearchState;
  update: (p: Partial<SearchState>, opts?: { push?: boolean }) => void;
  regions: Parameters<typeof RegionSelect>[0]["data"];
  lastFetched: string | null;
}) {
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
        disabled
        title="Scrape from the UI arrives in M3"
        className="h-9 rounded-ui bg-accent px-3 font-medium text-accent-fg opacity-50"
      >
        ⟳ Scrape
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

function NoResults({ s, update, labels }: { s: SearchState; update: (p: Partial<SearchState>) => void; labels: Labels }) {
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
      </div>
    </Empty>
  );
}
