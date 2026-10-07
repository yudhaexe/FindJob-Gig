// Scrape modal (DESIGN-UIUX.md §2.5): region-aware form + live progress of the current run.
import { type FormEvent, type KeyboardEvent as ReactKeyboardEvent, useEffect, useRef, useState } from "react";
import { runProgress, isActive } from "../hooks/useScrapeRun";
import { api } from "../lib/api";
import { TYPE_LABEL } from "../lib/format";
import type {
  EmploymentType, RegionsResponse, Run, ScrapeCategory, ScrapePreset, ScrapeQuery, ScrapeSource,
} from "../lib/types";
import { RegionSelect } from "./RegionSelect";

const TYPES: EmploymentType[] = ["fulltime", "parttime", "contract", "freelance", "internship"];

export const QUERY_DEFAULTS: ScrapeQuery = {
  keywords: [], types: [], category: "any", sources: [], region: "ALL", location: null,
  remote_only: false, since_hours: 72, max_per_source: 100,
};

interface Props {
  initial: Partial<ScrapeQuery>;
  regions: RegionsResponse | null;
  run: Run | null;
  sourceLabel: (name: string) => string;
  onStart: (q: ScrapeQuery) => Promise<void>;
  onClose: () => void;
  onViewResults: () => void;
}

export function ScrapeModal({ initial, regions, run, sourceLabel, onStart, onClose, onViewResults }: Props) {
  const [q, setQ] = useState<ScrapeQuery>(() => ({ ...QUERY_DEFAULTS, ...initial }));
  const [draft, setDraft] = useState("");
  const [sources, setSources] = useState<ScrapeSource[] | null>(null);
  const [presets, setPresets] = useState<ScrapePreset[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set(initial.sources ?? []));
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const dialog = useRef<HTMLFormElement>(null);
  const keepPicked = useRef(!!initial.sources?.length);
  const running = isActive(run);

  const set = (patch: Partial<ScrapeQuery>) => setQ((x) => ({ ...x, ...patch }));

  // Sources follow region + category: re-tick the auto selection unless a preset just chose them.
  useEffect(() => {
    const ctrl = new AbortController();
    api
      .scrapeSources({ region: q.region, category: q.category }, ctrl.signal)
      .then((r) => {
        setSources(r.sources);
        setPresets(r.presets);
        if (keepPicked.current) keepPicked.current = false;
        else setPicked(new Set(r.sources.filter((s) => s.selected).map((s) => s.name)));
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        const msg = e instanceof Error ? e.message : String(e);
        // A 404 here means the backend predates the scrape API (uvicorn --reload missed the new route).
        setError(/not found/i.test(msg) ? "The backend is out of date (scrape API not found). Restart `npm start` and try again." : msg);
        setSources([]);
      });
    return () => ctrl.abort();
  }, [q.region, q.category]);

  // Focus inside, Tab stays inside, Esc closes (unless a popover inside is open).
  useEffect(() => {
    const el = dialog.current;
    const prev = document.activeElement as HTMLElement | null;
    el?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (!el) return;
      if (e.key === "Escape") {
        if (el.querySelector('[aria-expanded="true"]')) return;
        e.preventDefault();
        onClose();
      } else if (e.key === "Tab") {
        const items = [...el.querySelectorAll<HTMLElement>("button, input, select, a[href], [tabindex]:not([tabindex='-1'])")]
          .filter((x) => !x.hasAttribute("disabled") && x.offsetParent !== null);
        if (!items.length) return;
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [onClose]);

  const addKeyword = (raw: string) => {
    const words = raw.split(",").map((w) => w.trim()).filter(Boolean);
    if (words.length) setQ((x) => ({ ...x, keywords: [...new Set([...x.keywords, ...words])] }));
    setDraft("");
  };

  const onKeywordKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      if (draft.trim()) {
        e.preventDefault();
        addKeyword(draft);
      } else if (e.key === ",") e.preventDefault();
    } else if (e.key === "Backspace" && !draft && q.keywords.length) {
      set({ keywords: q.keywords.slice(0, -1) });
    }
  };

  const applyPreset = (name: string) => {
    const p = presets.find((x) => x.name === name);
    if (!p) return;
    const next = { ...QUERY_DEFAULTS, region: q.region, ...p.query };
    if (p.query.sources?.length) {
      keepPicked.current = next.region !== q.region || next.category !== q.category;
      setPicked(new Set(p.query.sources));
    }
    setQ(next);
    setDraft("");
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const keywords = draft.trim() ? [...new Set([...q.keywords, ...draft.split(",").map((w) => w.trim()).filter(Boolean)])] : q.keywords;
    setDraft("");
    setQ((x) => ({ ...x, keywords }));
    setError(null);
    setStarting(true);
    try {
      await onStart({ ...q, keywords, location: q.location?.trim() || null, sources: [...picked] });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  const field = "h-9 rounded-ui border border-border bg-surface px-2";
  const label = "w-24 shrink-0 pt-2 text-muted";

  return (
    <div data-modal className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form
        ref={dialog}
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="scrape-title"
        className="relative flex max-h-[95dvh] w-full max-w-2xl flex-col rounded-t-xl bg-bg shadow-2xl sm:rounded-xl"
      >
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <h2 id="scrape-title" className="text-base font-semibold">
            Scrape now
          </h2>
          {presets.length > 0 && (
            <select
              value=""
              onChange={(e) => applyPreset(e.target.value)}
              aria-label="Load preset"
              className="ml-auto h-8 rounded-ui border border-border bg-surface px-2 text-muted"
              disabled={running}
            >
              <option value="">Load preset…</option>
              {presets.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.label}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close (Esc)"
            className={`h-8 min-w-8 rounded-ui px-2 text-muted hover:bg-surface hover:text-fg ${presets.length ? "" : "ml-auto"}`}
          >
            ✕
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
          <fieldset disabled={running} className="space-y-3 disabled:opacity-60">
            <div className="flex gap-3">
              <span className={label}>Keywords</span>
              <div className="flex min-h-9 flex-1 flex-wrap items-center gap-1 rounded-ui border border-border bg-surface px-1.5 py-1">
                {q.keywords.map((k) => (
                  <span key={k} className="flex items-center gap-1 rounded bg-bg px-2 py-0.5 text-[13px]">
                    {k}
                    <button
                      type="button"
                      onClick={() => set({ keywords: q.keywords.filter((x) => x !== k) })}
                      aria-label={`Remove keyword ${k}`}
                      className="text-muted hover:text-fg"
                    >
                      ✕
                    </button>
                  </span>
                ))}
                <input
                  data-autofocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={onKeywordKey}
                  onBlur={() => draft.trim() && addKeyword(draft)}
                  placeholder={q.keywords.length ? "+ add" : "e.g. video editor, photographer (Enter to add)"}
                  aria-label="Add keyword"
                  className="h-7 min-w-32 flex-1 bg-transparent px-1 outline-none"
                />
              </div>
            </div>
            {!q.keywords.length && !draft.trim() && (
              <p className="pl-[6.75rem] text-xs text-muted">No keyword = latest postings from each source.</p>
            )}

            <div className="flex items-center gap-3">
              <span className="w-24 shrink-0 text-muted">Region</span>
              <RegionSelect value={q.region} data={regions} onChange={(region) => set({ region })} />
            </div>

            <label className="flex items-center gap-3">
              <span className="w-24 shrink-0 text-muted">Location</span>
              <input
                value={q.location ?? ""}
                onChange={(e) => set({ location: e.target.value })}
                placeholder="optional city, e.g. Jakarta"
                className={`${field} min-w-0 flex-1`}
              />
            </label>

            <div className="flex items-center gap-3" role="radiogroup" aria-label="Category">
              <span className="w-24 shrink-0 text-muted">Category</span>
              {(
                [
                  ["any", "All"],
                  ["job", "Jobs"],
                  ["gig", "Gigs"],
                ] as [ScrapeCategory, string][]
              ).map(([v, l]) => (
                <label key={v} className="flex items-center gap-1.5">
                  <input type="radio" name="category" checked={q.category === v} onChange={() => set({ category: v })} />
                  {l}
                </label>
              ))}
            </div>

            <div className="flex gap-3">
              <span className="w-24 shrink-0 text-muted">Type</span>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {TYPES.map((t) => (
                  <label key={t} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={q.types.includes(t)}
                      onChange={(e) => set({ types: e.target.checked ? [...q.types, t] : q.types.filter((x) => x !== t) })}
                    />
                    {TYPE_LABEL[t]}
                  </label>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 sm:pl-[6.75rem]">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={q.remote_only} onChange={(e) => set({ remote_only: e.target.checked })} />
                Remote only
              </label>
              <label className="flex items-center gap-1.5" title="Only keep postings from the last N hours (0 = any age)">
                Since
                <input
                  type="number"
                  min={0}
                  value={q.since_hours}
                  onChange={(e) => set({ since_hours: Math.max(0, Number(e.target.value) || 0) })}
                  className={`${field} w-20 tabular-nums`}
                />
                hours
              </label>
              <label className="flex items-center gap-1.5" title="Max items per source for each keyword">
                Max per source
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={q.max_per_source}
                  onChange={(e) => set({ max_per_source: Math.min(1000, Math.max(1, Number(e.target.value) || 1)) })}
                  className={`${field} w-20 tabular-nums`}
                />
              </label>
            </div>

            <div>
              <div className="mb-1.5 text-muted">Sources (auto-selected for region)</div>
              {!sources ? (
                <div className="h-6 w-1/2 animate-pulse rounded bg-surface" />
              ) : (
                <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
                  {sources.map((s) => {
                    const notes = [
                      !s.enabled && "disabled",
                      !s.in_region && "not in region",
                      s.category !== "mixed" && (s.category === "gig" ? "gigs" : "jobs"),
                    ].filter(Boolean);
                    return (
                      <label key={s.name} className="flex items-center gap-1.5" title={`Markets: ${s.markets.join(", ")}`}>
                        <input
                          type="checkbox"
                          checked={picked.has(s.name)}
                          onChange={(e) =>
                            setPicked((p) => {
                              const n = new Set(p);
                              if (e.target.checked) n.add(s.name);
                              else n.delete(s.name);
                              return n;
                            })
                          }
                        />
                        <span className={s.in_region && s.enabled ? "" : "text-muted"}>{s.display_name}</span>
                        {notes.length > 0 && <span className="text-xs text-muted">({notes.join(", ")})</span>}
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="rounded-ui border border-danger/30 bg-danger/10 px-3 py-2 text-danger">
              {error}
            </p>
          )}

          {run && <Progress run={run} sourceLabel={sourceLabel} />}
        </div>

        <div className="flex items-center gap-2 border-t border-border px-4 py-3">
          {run && !running && (
            <button type="button" onClick={onViewResults} className="h-9 rounded-ui px-3 font-medium text-accent hover:bg-surface">
              View results →
            </button>
          )}
          <button type="button" onClick={onClose} className="ml-auto h-9 rounded-ui border border-border px-4 hover:bg-surface">
            {running ? "Run in background" : run ? "Close" : "Cancel"}
          </button>
          <button
            type="submit"
            disabled={running || starting || picked.size === 0}
            title={picked.size === 0 ? "Pick at least one source" : undefined}
            className="h-9 rounded-ui bg-accent px-4 font-medium text-accent-fg hover:opacity-90 disabled:opacity-50"
          >
            {running ? "⟳ Running…" : run ? "▶ Start again" : "▶ Start"}
          </button>
        </div>
      </form>
    </div>
  );
}

const ICON: Record<string, string> = { queued: "…", running: "⟳", done: "✔", error: "✖", skipped: "–" };

function Progress({ run, sourceLabel }: { run: Run; sourceLabel: (name: string) => string }) {
  const { done, total, newJobs } = runProgress(run);
  const entries = Object.entries(run.sources);
  const summary = isActive(run)
    ? `${done}/${total} sources`
    : `${run.status === "done" ? "Finished" : run.status === "partial" ? "Finished with errors" : "Failed"} · ${newJobs} new job${newJobs === 1 ? "" : "s"}`;
  return (
    <section aria-live="polite" className="border-t border-border pt-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted">PROGRESS</h3>
      <ul className="space-y-1">
        {entries.map(([name, r]) => (
          <li key={name} className="grid grid-cols-[8rem_1fr_auto] items-baseline gap-2">
            <span className="truncate">{sourceLabel(name)}</span>
            <span
              className={r.status === "error" ? "text-danger" : r.status === "done" ? "text-success" : "text-muted"}
              title={r.error ?? undefined}
            >
              <span className={r.status === "running" ? "inline-block animate-spin" : ""}>{ICON[r.status]}</span>{" "}
              {r.status === "done"
                ? `${r.fetched} fetched · ${r.new} new${r.updated ? ` · ${r.updated} updated` : ""}`
                : r.status === "error"
                  ? r.error
                  : r.status === "running"
                    ? "running…"
                    : r.status}
              {r.status === "done" && r.error && <span className="text-warning"> · ⚠ {r.error}</span>}
            </span>
            <span className="tabular-nums text-muted">{r.ms != null ? `${(r.ms / 1000).toFixed(1)}s` : ""}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
          <div
            className={`h-full rounded-full transition-[width] ${run.status === "failed" ? "bg-danger" : "bg-accent"}`}
            style={{ width: `${total ? (done / total) * 100 : 0}%` }}
          />
        </div>
        <span className="tabular-nums text-muted">{summary}</span>
      </div>
    </section>
  );
}
