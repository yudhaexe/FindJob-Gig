// "Columns" popover for the results table: show/hide and reorder; saved per browser.
import { useEffect, useRef, useState } from "react";
import { COLUMNS, DEFAULT_COLUMNS } from "./Results";

const KEY = "fjg.columns";
const valid = (id: unknown): id is string => typeof id === "string" && COLUMNS.some((c) => c.id === id);

export function useColumns(): [string[], (next: string[]) => void] {
  const [cols, setCols] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) ?? "null");
      if (Array.isArray(saved)) {
        const ids = saved.filter(valid);
        if (ids.includes("title")) return ids;
      }
    } catch {
      /* storage unavailable or corrupt: use defaults */
    }
    return DEFAULT_COLUMNS;
  });
  const set = (next: string[]) => {
    setCols(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };
  return [cols, set];
}

export function ColumnMenu({ columns, onChange }: { columns: string[]; onChange: (next: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  // Shown columns in their saved order, then hidden ones.
  const order = [...columns, ...COLUMNS.map((c) => c.id).filter((id) => !columns.includes(id))];
  const move = (id: string, d: -1 | 1) => {
    const i = columns.indexOf(id);
    const j = i + d;
    if (i < 0 || j < 0 || j >= columns.length) return;
    const next = [...columns];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  const toggle = (id: string) => onChange(columns.includes(id) ? columns.filter((c) => c !== id) : [...columns, id]);

  return (
    <div ref={ref} className="relative hidden md:block">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="h-8 rounded-ui border border-border px-2 hover:bg-surface"
      >
        Columns
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-64 rounded-ui border border-border bg-bg p-2 shadow-lg">
          <ul>
            {order.map((id) => {
              const def = COLUMNS.find((c) => c.id === id)!;
              const shown = columns.includes(id);
              const btn = "px-1 text-muted hover:text-accent disabled:opacity-30";
              return (
                <li key={id} className="flex items-center gap-2 py-0.5">
                  <label className="flex flex-1 items-center gap-2">
                    <input type="checkbox" checked={shown} disabled={def.required} onChange={() => toggle(id)} />
                    <span className={shown ? "" : "text-muted"}>{def.label}</span>
                  </label>
                  {shown && (
                    <>
                      <button type="button" aria-label={`Move ${def.label} up`} disabled={columns.indexOf(id) === 0} onClick={() => move(id, -1)} className={btn}>↑</button>
                      <button type="button" aria-label={`Move ${def.label} down`} disabled={columns.indexOf(id) === columns.length - 1} onClick={() => move(id, 1)} className={btn}>↓</button>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
          <button type="button" onClick={() => onChange(DEFAULT_COLUMNS)} className="mt-1 text-xs text-accent hover:underline">
            Reset to default
          </button>
        </div>
      )}
    </div>
  );
}
