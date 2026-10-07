// The scrape run in progress, polled every second (DESIGN-UIUX.md §2.5). Lives above the modal so
// closing the modal keeps the header indicator going; the id survives a reload via localStorage.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Run, ScrapeQuery } from "../lib/types";

const KEY = "fjg.run";

function readId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function writeId(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: progress just won't survive a reload */
  }
}

export const isActive = (r: Run | null) => !!r && (r.status === "queued" || r.status === "running");

/** A run still "running" after an hour was cut off by a server stop; don't poll it forever. */
const stale = (r: Run) => !!r.started_at && Date.now() - Date.parse(r.started_at) > 3600_000;

export function runProgress(r: Run): { done: number; total: number; newJobs: number } {
  const all = Object.values(r.sources);
  return {
    done: all.filter((s) => s.status === "done" || s.status === "error" || s.status === "skipped").length,
    total: all.length,
    newJobs: all.reduce((n, s) => n + s.new, 0),
  };
}

/** `onFinish` fires once when a run this tab watched goes from active to finished. */
export function useScrapeRun(onFinish: (run: Run) => void) {
  const [run, setRun] = useState<Run | null>(null);
  const [id, setId] = useState<string | null>(readId);
  const finish = useRef(onFinish);
  finish.current = onFinish;

  useEffect(() => {
    if (!id) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    let wasActive = false;
    let failures = 0;
    const tick = async () => {
      try {
        const r = await api.run(id);
        if (stop) return;
        failures = 0;
        setRun(r);
        if (isActive(r) && !stale(r)) {
          wasActive = true;
          timer = setTimeout(tick, 1000);
        } else {
          writeId(null);
          if (wasActive) finish.current(r);
        }
      } catch {
        if (stop) return;
        // Server restarting (uvicorn --reload) or run file gone: retry a few times, then give up.
        if (++failures < 5) timer = setTimeout(tick, 3000);
        else writeId(null);
      }
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [id]);

  const start = useCallback(async (q: ScrapeQuery) => {
    const { run_id } = await api.startScrape(q);
    writeId(run_id);
    setRun(null);
    setId(run_id);
  }, []);

  const stop = useCallback(async () => {
    if (id) await api.stopRun(id);
  }, [id]);

  const dismiss = useCallback(() => {
    writeId(null);
    setId(null);
    setRun(null);
  }, []);

  return { run, start, stop, dismiss };
}
