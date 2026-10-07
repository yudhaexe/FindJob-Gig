// Header region focus picker (DESIGN-UIUX.md §2.2): search, tree with counts, countries on expand.
import { useEffect, useMemo, useRef, useState } from "react";
import type { RegionsResponse } from "../lib/types";

const SPECIAL = ["ALL", "GLOBAL_REMOTE"];
const ICON: Record<string, string> = { ALL: "🌐", GLOBAL_REMOTE: "🌍" };

export function regionLabel(regions: RegionsResponse | null, code: string): string {
  if (!regions) return code;
  return regions.regions.find((r) => r.code === code)?.label ?? regions.countries[code]?.name ?? code;
}

interface Row {
  code: string;
  label: string;
  count: number;
  depth: number;
  hasKids: boolean;
}

function buildRows(data: RegionsResponse, expanded: Set<string>, query: string): Row[] {
  const byCode = new Map(data.regions.map((r) => [r.code, r]));
  const childCodes = new Set(data.regions.flatMap((r) => r.children));
  const q = query.trim().toLowerCase();

  if (q) {
    // Flat list of every region and country whose label or code matches.
    const regionRows = data.regions
      .filter((r) => r.label.toLowerCase().includes(q) || r.code.toLowerCase() === q)
      .map((r) => ({ code: r.code, label: r.label, count: r.count, depth: 0, hasKids: false }));
    const countryRows = Object.entries(data.countries)
      .filter(([code, c]) => c.name.toLowerCase().includes(q) || code.toLowerCase() === q)
      .map(([code, c]) => ({ code, label: c.name, count: c.count, depth: 0, hasKids: false }));
    return [...regionRows, ...countryRows];
  }

  const rows: Row[] = [];
  const walk = (code: string, depth: number) => {
    const r = byCode.get(code);
    if (!r) return;
    const kids = r.children.length ? r.children : r.countries;
    rows.push({ code, label: r.label, count: r.count, depth, hasKids: kids.length > 0 });
    if (!expanded.has(code)) return;
    if (r.children.length) r.children.forEach((c) => walk(c, depth + 1));
    else
      r.countries
        .map((cc) => ({ cc, c: data.countries[cc] }))
        .filter(({ c }) => c)
        .sort((a, b) => b.c.count - a.c.count || a.c.name.localeCompare(b.c.name))
        .forEach(({ cc, c }) => rows.push({ code: cc, label: c.name, count: c.count, depth: depth + 1, hasKids: false }));
  };
  SPECIAL.forEach((c) => walk(c, 0));
  data.regions.filter((r) => !SPECIAL.includes(r.code) && !childCodes.has(r.code)).forEach((r) => walk(r.code, 0));
  return rows;
}

export function RegionSelect({
  value,
  data,
  onChange,
}: {
  value: string;
  data: RegionsResponse | null;
  onChange: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(["APAC"]));
  const box = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const rows = useMemo(() => (data ? buildRows(data, expanded, query) : []), [data, expanded, query]);

  const pick = (code: string) => {
    onChange(code);
    setOpen(false);
    setQuery("");
  };
  const toggle = (code: string) =>
    setExpanded((s) => {
      const n = new Set(s);
      if (n.has(code)) n.delete(code);
      else n.add(code);
      return n;
    });

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex h-9 max-w-48 items-center gap-1.5 rounded-ui border border-border bg-surface px-3 hover:border-muted"
      >
        <span aria-hidden>{ICON[value] ?? "🌏"}</span>
        <span className="truncate">{regionLabel(data, value)}</span>
        <span aria-hidden className="text-muted">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 w-72 rounded-ui border border-border bg-bg shadow-lg">
          <div className="border-b border-border p-2">
            <input
              ref={input}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search region / country"
              aria-label="Search region or country"
              className="h-8 w-full rounded-ui border border-border bg-surface px-2"
            />
          </div>
          <ul role="listbox" aria-label="Region focus" className="max-h-96 overflow-y-auto py-1">
            {rows.length === 0 && <li className="px-3 py-2 text-muted">No match</li>}
            {rows.map((r) => (
              <li key={r.code} role="option" aria-selected={r.code === value} className="flex items-center">
                <span style={{ width: 8 + r.depth * 14 }} className="shrink-0" />
                {r.hasKids ? (
                  <button
                    type="button"
                    onClick={() => toggle(r.code)}
                    aria-label={`${expanded.has(r.code) ? "Collapse" : "Expand"} ${r.label}`}
                    className="w-5 shrink-0 text-xs text-muted hover:text-fg"
                  >
                    {expanded.has(r.code) ? "▾" : "▸"}
                  </button>
                ) : (
                  <span className="w-5 shrink-0" />
                )}
                <button
                  type="button"
                  onClick={() => pick(r.code)}
                  className={`flex min-w-0 flex-1 items-center justify-between gap-2 py-1.5 pr-3 text-left hover:bg-surface ${
                    r.code === value ? "font-semibold text-accent" : ""
                  } ${r.depth === 0 && !SPECIAL.includes(r.code) ? "font-medium" : ""}`}
                >
                  <span className="truncate">
                    {ICON[r.code] ? `${ICON[r.code]} ` : ""}
                    {r.label}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-muted">{r.count.toLocaleString("en-US")}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
