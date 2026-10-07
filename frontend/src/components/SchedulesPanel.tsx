// Schedules panel (DESIGN-UIUX.md §2.6): list, run now, pause/resume, change interval, delete.
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { relTime } from "../lib/format";
import type { Schedule } from "../lib/types";

export const INTERVALS = ["30m", "1h", "6h", "12h", "1d"];

const inFuture = (iso: string | null) => {
  if (!iso) return "-";
  const ms = Date.parse(iso) - Date.now();
  return ms <= 0 ? "due" : `in ${relTime(new Date(Date.now() - ms).toISOString()) ?? "?"}`;
};

const STATUS: Record<string, string> = { done: "✔ done", partial: "⚠ partial", failed: "✖ failed", running: "⟳ running", queued: "… queued" };

export function useSchedules(version = 0) {
  const [items, setItems] = useState<Schedule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    api.schedules().then(setItems).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  useEffect(reload, [reload, version]);
  return { items, error, reload };
}

export function SchedulesPanel({ items, error, reload, onClose }: {
  items: Schedule[];
  error: string | null;
  reload: () => void;
  onClose: () => void;
}) {
  const [task, setTask] = useState<string | null>(null);
  const [help, setHelp] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.taskStatus().then((r) => setTask(r.status)).catch(() => setTask(null));
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const act = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
    reload();
  };

  const btn = "h-7 rounded-ui border border-border px-2 text-xs hover:bg-surface";

  return (
    <div data-modal className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <section role="dialog" aria-modal="true" aria-label="Schedules" className="relative flex max-h-[85dvh] w-full max-w-2xl flex-col rounded-t-xl bg-bg shadow-xl sm:rounded-xl">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <h2 className="font-semibold">Schedules</h2>
          <button type="button" onClick={onClose} className="ml-auto h-8 rounded-ui px-2 hover:bg-surface" aria-label="Close">✕</button>
        </header>

        <div className="flex-1 space-y-2 overflow-y-auto p-4">
          {(err || error) && <p role="alert" className="rounded-ui border border-danger/30 bg-danger/10 px-3 py-2 text-danger">{err ?? error}</p>}
          {items.length === 0 && (
            <p className="py-6 text-center text-muted">No schedules yet. Open Scrape and tick “Save as schedule”.</p>
          )}
          {items.map((s) => (
            <article key={s.id} className="rounded-ui border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className={s.enabled ? "text-success" : "text-muted"} aria-hidden>{s.enabled ? "●" : "○"}</span>
                <strong className="min-w-0 truncate">{s.name}</strong>
                <select
                  value={INTERVALS.includes(s.every) ? s.every : ""}
                  onChange={(e) => act(() => api.patchSchedule(s.id, { every: e.target.value }))}
                  aria-label={`Interval for ${s.name}`}
                  className="h-7 rounded-ui border border-border bg-surface px-1 text-xs"
                >
                  {!INTERVALS.includes(s.every) && <option value="">{s.every}</option>}
                  {INTERVALS.map((i) => <option key={i} value={i}>every {i}</option>)}
                </select>
                <span className="text-xs text-muted">{s.query.region} · {s.query.keywords.join(", ") || "all keywords"}</span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {s.paused_reason
                  ? <span className="text-warning">{s.paused_reason}</span>
                  : <>Last: {s.last_run_at ? `${relTime(s.last_run_at)} ago ${STATUS[s.last_status ?? ""] ?? ""}` : "never"} · Next: {s.enabled ? inFuture(s.next_run_at) : "paused"}</>}
              </p>
              <div className="mt-2 flex gap-2">
                <button type="button" className={btn} onClick={() => act(() => api.runSchedule(s.id))}>Run now</button>
                <button type="button" className={btn} onClick={() => act(() => api.patchSchedule(s.id, { enabled: !s.enabled }))}>
                  {s.enabled ? "⏸ Pause" : "Resume"}
                </button>
                <button
                  type="button"
                  className={`${btn} ml-auto text-danger`}
                  onClick={() => confirm(`Delete schedule “${s.name}”?`) && act(() => api.deleteSchedule(s.id))}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>

        <footer className="border-t border-border px-4 py-3 text-xs">
          <p>
            <strong>When the app is closed:</strong> Windows Task Scheduler{" "}
            {task === "registered" ? "✔ registered (every 30 min)" : task === "not-supported" ? "is not available on this OS" : "is not set up"}
            {task === "not-registered" && (
              <button type="button" className="ml-2 text-accent hover:underline" onClick={() => setHelp((h) => !h)}>How to set up</button>
            )}
          </p>
          {help && (
            <pre className="mt-2 overflow-x-auto rounded-ui bg-surface p-2">powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1</pre>
          )}
        </footer>
      </section>
    </div>
  );
}
