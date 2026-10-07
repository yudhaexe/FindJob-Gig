import { useEffect, useState } from "react";
import { api } from "./lib/api";
import type { JobsPage } from "./lib/types";

type Conn = "checking" | "ok" | "down";

// M0 shell: header + empty state. Filters, table and drawer arrive in M2–M3.
export default function App() {
  const [conn, setConn] = useState<Conn>("checking");
  const [page, setPage] = useState<JobsPage | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => {
        setConn("ok");
        return api.jobs({ region: "ALL" }).then(setPage);
      })
      .catch(() => setConn("down"));
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 font-semibold">
          <img src="/favicon.svg" alt="" className="h-6 w-6" />
          FindJob&amp;Gig
        </div>
        <button
          disabled
          className="rounded-ui border border-border bg-surface px-3 py-1.5 text-muted"
          title="Region focus (M2)"
        >
          🌐 All regions ▾
        </button>
        <input
          disabled
          placeholder='Search jobs… e.g. react -wordpress "senior"'
          className="min-w-0 flex-1 rounded-ui border border-border bg-surface px-3 py-1.5"
        />
        <button
          disabled
          className="rounded-ui bg-accent px-3 py-1.5 font-medium text-accent-fg opacity-60"
          title="Scrape (M3)"
        >
          ⟳ Scrape
        </button>
        <ConnBadge conn={conn} />
      </header>

      <main className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
        {conn === "down" ? (
          <>
            <p className="font-medium text-danger">Couldn't reach the API.</p>
            <p className="text-muted">
              Start the backend: <code className="font-mono">uvicorn app.main:app --reload</code>
            </p>
          </>
        ) : page && page.total === 0 ? (
          <>
            <p className="text-lg font-medium">No jobs yet.</p>
            <p className="text-muted">Run your first scrape — available from milestone M1.</p>
          </>
        ) : (
          <p className="text-muted">Loading…</p>
        )}
      </main>
    </div>
  );
}

function ConnBadge({ conn }: { conn: Conn }) {
  const label = { checking: "API…", ok: "API ok", down: "API down" }[conn];
  const color = { checking: "text-muted", ok: "text-success", down: "text-danger" }[conn];
  return <span className={`text-xs ${color}`}>● {label}</span>;
}
